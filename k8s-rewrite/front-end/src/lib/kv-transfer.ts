import { z } from "zod";
import { KvError, KvMutationError, fieldMapping, logicalPath, requireGuarded, type KvActor } from "./kv-contract";
import type { RegisteredPath } from "./kv-registry";
import type { KvNativeEngine } from "./kv-native-engine";
import { encodedField } from "./kv-schemas";
import { encodedValues, nativeIdentity, ownedPath } from "./kv-native-state";
import { secretFailure } from "./cluster-secrets";

export const KV_TRANSFER_BYTES = 1024 * 1024;
const documentSchema = z.object({
  mountId: z.string().uuid(), path: z.string().max(512), namespace: z.string(), name: z.string(),
  mappings: z.array(z.object({ field: z.string(), key: z.string() }).strict()).min(1).max(64),
  fields: z.array(encodedField).max(64), sourceVersion: z.number().int().positive().optional(),
}).strict();
export const bundleSchema = z.object({ format: z.literal("bortus-kv"), version: z.literal(1), documents: z.array(documentSchema).min(1).max(100) }).strict();
export const importPreviewSchema = z.object({ bundle: bundleSchema }).strict();
const planSchema = z.object({ documentIndex: z.number().int().nonnegative(), pathId: z.string().uuid().nullable(), revision: z.number().int().positive().nullable(),
  resourceVersion: z.string().max(128).optional(), expectedHead: z.number().int().nonnegative().optional(), overwrite: z.boolean() }).strict();
export const importSchema = z.object({ bundle: bundleSchema, plans: z.array(planSchema).min(1).max(100), confirmCredentials: z.literal(true) }).strict();
export const exportSchema = z.object({ selections: z.array(z.object({ pathId: z.string().uuid(), version: z.number().int().positive().optional() }).strict()).min(1).max(100), confirmCredentials: z.literal(true) }).strict();
type Document = z.infer<typeof documentSchema>;
type Bundle = z.infer<typeof bundleSchema>;
const mappingsEqual = (a: Document["mappings"], b: RegisteredPath["fields"]) =>
  JSON.stringify([...a].sort((x,y)=>x.field.localeCompare(y.field))) === JSON.stringify(b.map(({field,key})=>({field,key})).sort((x,y)=>x.field.localeCompare(y.field)));

export class KvTransfer {
  private readonly deadline: number;
  constructor(readonly engine: KvNativeEngine, readonly signal?: AbortSignal, readonly now: () => number = Date.now) { this.deadline = now() + 30000; }
  private checkpoint() { if (this.signal?.aborted || this.now() >= this.deadline) throw new KvError(408, "KV transfer stopped; inspect per-path outcomes before retrying"); }
  private validate(bundle: Bundle) {
    if(!bundleSchema.safeParse(bundle).success)throw new KvError(400,"Invalid KV transfer bundle");
    if (Buffer.byteLength(JSON.stringify(bundle)) > KV_TRANSFER_BYTES) throw new KvError(413, "KV transfer exceeds one MiB");
    const paths=new Set<string>(), targets=new Set<string>();
    for(const doc of bundle.documents) {
      logicalPath(doc.path);fieldMapping(doc.mappings,doc.namespace,doc.name);encodedValues(doc.fields,{fields:doc.mappings} as RegisteredPath);
      const path=doc.mountId+"/"+doc.path,target=doc.namespace+"/"+doc.name;
      if(paths.has(path)||targets.has(target)) throw new KvError(400,"Transfer documents must have distinct paths and native objects");
      paths.add(path);targets.add(target);
    }
  }
  private async describe(actor: KvActor, doc: Document, documentIndex: number) {
    this.checkpoint();const registry=this.engine.registry;
    const found=await registry.db.kvPath.findUnique({where:{mountId_path:{mountId:doc.mountId,path:doc.path}},select:{id:true}});
    const path=found ? await registry.path(found.id) : null;
    await registry.authorize(actor,doc,path ? "update" : "create");
    if(path && (path.namespace!==doc.namespace||path.name!==doc.name||!mappingsEqual(doc.mappings,path.fields))) throw new KvError(409,"Import target or field mapping differs from registered ownership");
    if(!path) {
      await registry.admin(actor);
      const mount=await registry.db.kvMount.findUnique({where:{id:doc.mountId}});if(!mount)throw new KvError(404,"KV mount not found");
      if(!registry.allowedNamespaces(JSON.parse(mount.namespaces)).includes(doc.namespace))throw new KvError(403,"Path namespace is outside its mount");
      if(await registry.db.kvField.count({where:{namespace:doc.namespace,name:doc.name,key:{in:doc.mappings.map(f=>f.key)}}}))throw new KvError(409,"Selected native keys already have registered ownership");
    }
    this.checkpoint();let secret;
    try {secret=await this.engine.transport.read(doc.namespace,doc.name);}
    catch(error) {if(secretFailure(error).status!==404)throw secretFailure(error);}
    const current=secret && path ? ownedPath(secret,path) : undefined;
    if(!current&&path&&await registry.db.kvOperation.count({where:{pathId:path.id,outcome:{in:["committed","pending","ambiguous","recovery-required"]}}}))throw new KvError(409,"Path has prior or unresolved native history; explicit recovery required");
    if(secret&&!current)throw new KvError(409,"Existing native target requires explicit administrator adoption");
    if(!current) {
      await registry.admin(actor);await registry.authorize(actor,doc,"create");
    }
    return { documentIndex,pathId:path?.id??null,revision:path?.revision??null,mode:current ? "update" as const : "create" as const,
      resourceVersion:secret ? nativeIdentity(secret).resourceVersion : "absent",expectedHead:current?.head??0,
      mountId:doc.mountId,path:doc.path,namespace:doc.namespace,name:doc.name,mappings:doc.mappings.map(({field,key})=>({field,key})),requiresOverwrite:!!current };
  }
  async preview(actor: KvActor,bundle: Bundle) {
    this.validate(bundle);const plans=[];
    for(let index=0;index<bundle.documents.length;index++) {
      try {plans.push({...await this.describe(actor,bundle.documents[index],index),outcome:"ready",status:200});}
      catch(error) {const safe=secretFailure(error);plans.push({documentIndex:index,status:safe.status,error:safe.message,outcome:"refused"});}
    }
    return {format:"bortus-kv-import-preview",version:1,containsCredentialValues:false,atomic:false,guardedAdoption:this.engine.registry.config.guardedAdoption,plans};
  }
  async import(actor: KvActor,input: z.infer<typeof importSchema>) {
    if(input.confirmCredentials!==true)throw new KvError(400,"Credential transfer acknowledgement required");
    this.validate(input.bundle);requireGuarded(this.engine.registry.config);
    if(input.plans.length!==input.bundle.documents.length||input.plans.some((p,index)=>p.documentIndex!==index))throw new KvError(400,"Exactly one ordered plan per import document required");
    const outcomes=[];
    for(let index=0;index<input.bundle.documents.length;index++) {
      let pathId:string|null=null;
      try {
        const doc=input.bundle.documents[index],plan=input.plans[index],current=await this.describe(actor,doc,index);pathId=current.pathId;
        if(plan.resourceVersion===undefined||plan.expectedHead===undefined)throw new KvError(428,"Native resourceVersion and expected head required");
        if(plan.pathId!==current.pathId||plan.revision!==current.revision||plan.resourceVersion!==current.resourceVersion||plan.expectedHead!==current.expectedHead)throw new KvError(409,"Import preview changed; refresh before retrying");
        if(current.mode==="update"&&!plan.overwrite)throw new KvError(409,"Explicit overwrite acknowledgement required");
        this.checkpoint();
        let pathRevision=current.revision??undefined;
        if(!pathId){const registered=await this.engine.registry.registerPath(actor,{mountId:doc.mountId,path:doc.path,namespace:doc.namespace,name:doc.name,fields:doc.mappings});pathId=registered.id;pathRevision=registered.revision;}
        this.checkpoint();
        const result=current.mode==="create" ? await this.engine.create(actor,pathId,{...plan,pathRevision,fields:doc.fields}) : await this.engine.change(actor,pathId,{...plan,pathRevision,fields:doc.fields});
        outcomes.push({documentIndex:index,pathId,status:200,...result});
      } catch(error) {
        const safe=secretFailure(error);outcomes.push({documentIndex:index,pathId,status:safe.status,error:safe.message,outcome:error instanceof KvMutationError ? error.outcome : "refused",
          ...(error instanceof KvMutationError ? {operationId:error.operationId} : {})});
      }
    }
    return {format:"bortus-kv-import-result",version:1,atomic:false,success:outcomes.every(result=>result.outcome==="committed"),outcomes};
  }
  async export(actor: KvActor,input: z.infer<typeof exportSchema>): Promise<Bundle> {
    if(!exportSchema.safeParse(input).success)throw new KvError(400,"Invalid KV export selection or acknowledgement");
    if(new Set(input.selections.map(selection=>selection.pathId)).size!==input.selections.length)throw new KvError(400,"Select each export path once");
    const documents:Document[]=[],paths:RegisteredPath[]=[];
    for(const selection of input.selections) {
      this.checkpoint();const path=await this.engine.registry.path(selection.pathId),data=await this.engine.read(actor,path.id,selection.version,"export");
      paths.push(path);documents.push({mountId:path.mountId,path:path.path,namespace:path.namespace,name:path.name,mappings:path.fields.map(({field,key})=>({field,key})),fields:data.fields,...(data.version>0?{sourceVersion:data.version}:{})});
      if(Buffer.byteLength(JSON.stringify({format:"bortus-kv",version:1,documents}))>KV_TRANSFER_BYTES)throw new KvError(413,"KV transfer exceeds one MiB");
    }
    this.checkpoint();for(const path of paths)await this.engine.registry.authorize(actor,path,"export");this.checkpoint();
    return {format:"bortus-kv",version:1,documents};
  }
}
