import { test } from "node:test";
import { randomUUID } from "node:crypto";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { PrismaClient } from "@prisma/client";
import type { V1Secret } from "@kubernetes/client-node";
import { AccountStore } from "../src/lib/account-store";
import { KvRegistry } from "../src/lib/kv-registry";
import { KvNativeEngine } from "../src/lib/kv-native-engine";
import { KvError, KvMutationError, kvConfig } from "../src/lib/kv-contract";
import type { NativeSecretTransport } from "../src/lib/secret-client";
import { CREATED_ANNOTATION, HISTORY_ANNOTATION, STATE_ANNOTATION, encodedValues, exportFields, historyBody, historyValues, parseState, stateBody } from "../src/lib/kv-native-state";
import { SecretError, SecretStore } from "../src/lib/cluster-secrets";
import { flatSecretGuard, requireLegacyPrincipal } from "../src/lib/secret-access";
import { automationRequest, runAutomation } from "../src/lib/kv-automation";
import { KvTransfer, type bundleSchema } from "../src/lib/kv-transfer";
import { KvRotations } from "../src/lib/kv-rotation";
import type { z } from "zod";

const marker = "synthetic-private-other-key";
const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const denied = (status: number) => (error: unknown) => error instanceof KvError && error.status === status;
class NativeFixture implements NativeSecretTransport {
  objects = new Map<string,V1Secret>(); counter = 0; reads = 0; writes = 0;
  replaceMode = "normal"; readOutage = false; createTimeout = false;
  deleteMode = "normal"; deletes: { namespace: string; name: string; uid: string; resourceVersion: string }[] = [];
  malformedReplaceReply = false;
  afterReplace?: () => Promise<void>;
  afterCreate?: () => Promise<void>;
  key(ns: string, name: string) { return ns + "/" + name; }
  seed(ns: string, name: string, data: Record<string,string>, extra: Partial<V1Secret> = {}) {
    const value: V1Secret = { apiVersion: "v1", kind: "Secret", type: "Opaque", ...extra, metadata: { ...extra.metadata, name, namespace: ns, uid: "native-uid-" + ++this.counter, resourceVersion: String(this.counter), creationTimestamp: new Date() }, data: copy(data) };
    this.objects.set(this.key(ns,name), value); return copy(value);
  }
  async read(ns: string, name: string) {
    this.reads++;
    if (this.readOutage) throw { code: 503, body: marker };
    const value = this.objects.get(this.key(ns,name)); if (!value) throw { code: 404 };
    return copy(value);
  }
  async list(ns: string) { return [...this.objects.values()].filter(s=>s.metadata?.namespace===ns).map(copy); }
  async listMetadata(ns: string) { return [...this.objects.values()].filter(s=>s.metadata?.namespace===ns).map(s=>copy(s.metadata!)); }
  async create(ns: string, body: V1Secret) {
    this.writes++;
    if (this.objects.has(this.key(ns,body.metadata!.name!))) throw { code: 409 };
    const result = this.seed(ns, body.metadata!.name!, body.data || {}, body);
    await this.afterCreate?.();
    if (this.createTimeout && ns === "history") { this.createTimeout = false; throw { code: 503, body: marker }; }
    return result;
  }
  async replace(ns: string, name: string, body: V1Secret) {
    this.writes++;
    const current = this.objects.get(this.key(ns,name));
    if (!current) throw { code: 404 };
    if (current.immutable || body.metadata?.resourceVersion !== current.metadata?.resourceVersion) throw { code: 409, body: marker };
    if (body.type === "kubernetes.io/dockerconfigjson" && !Object.hasOwn(body.data || {}, ".dockerconfigjson")) throw { code: 422, body: marker };
    if (this.replaceMode === "before") { this.replaceMode = "normal"; throw { code: 503, body: marker }; }
    const result = copy({ ...body, metadata: { ...body.metadata, uid: current.metadata?.uid, resourceVersion: String(++this.counter) } });
    this.objects.set(this.key(ns,name), result);
    await this.afterReplace?.();
    if (this.replaceMode === "after" || this.replaceMode === "after-outage") {
      if (this.replaceMode === "after-outage") this.readOutage = true;
      this.replaceMode = "normal"; throw { code: 503, body: marker };
    }
    if(this.malformedReplaceReply){this.malformedReplaceReply=false;const reply=copy(result);reply.metadata!.uid="unverifiable-response";return reply;}
    return copy(result);
  }
  async delete(ns: string, name: string, uid: string, resourceVersion: string) {
    this.deletes.push({namespace:ns,name,uid,resourceVersion});
    const current = this.objects.get(this.key(ns,name));
    if (!current) throw { code: 404 };
    if (current.metadata?.uid !== uid || current.metadata.resourceVersion !== resourceVersion) throw { code: 409 };
    if(this.deleteMode==="before"){this.deleteMode="normal";throw {code:503};}
    this.objects.delete(this.key(ns,name));
    if(this.deleteMode==="after"){this.deleteMode="normal";throw {code:503};}
  }
  async probe() {}
}

test("native grouped KV CAS, history isolation, drift, ambiguity and metadata audit recovery", { timeout: 90000 }, async t => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-kv-native-"));
  const url = "file:" + path.join(dir,"test.db").replaceAll("\\","/");
  const env: NodeJS.ProcessEnv = { ...process.env, DATABASE_URL: url }; delete env.RUST_LOG;
  const previousRegistration = process.env.ALLOW_REGISTRATION; process.env.ALLOW_REGISTRATION = "false";
  const db = new PrismaClient({ datasources: { db: { url } } });
  try {
    execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe" });
    const accounts = new AccountStore(db), admin = await accounts.register({ username:"operator", passwordHash:"synthetic-hash" });
    const actor = { id: admin.id, sessionVersion: admin.sessionVersion };
    const registry = new KvRegistry(db, ["apps","history"], kvConfig({ BORTUS_HISTORY_NAMESPACE:"history", BORTUS_KV_GUARDED_ADOPTION:"true" }), async()=>aliases);
    const mount = await registry.createMount(actor, { name:"apps", namespaces:["apps"] });
    const registered = await registry.registerPath(actor, { mountId:mount.id, path:"services/api/credentials", namespace:"apps", name:"imported", fields:[{field:"__proto__",key:"__proto__"},{field:"constructor",key:"constructor"},{field:"toString",key:"toString"}] });
    const native = new NativeFixture();
    const initial = Object.fromEntries([["__proto__",Buffer.from([0,255,128,1]).toString("base64")],["constructor",Buffer.from("first credential").toString("base64")],["toString",""]]);
    const other = Buffer.from(marker).toString("base64");
    native.seed("apps","imported", { ...initial, unrelated:other }, { metadata:{ labels:{app:"preserved"}, annotations:{"kubectl.kubernetes.io/last-applied-configuration":marker}, managedFields:[{manager:marker}], ownerReferences:[{apiVersion:"v1",kind:"ConfigMap",name:"owner",uid:"owner-uid"}] } });
    const aliases = Array.from({length:603},(_,index)=>({alias:"secret_original_underscored_"+index,namespace:"apps",name:"imported",key:index%2?"__proto__":"constructor"}));
    const engine = new KvNativeEngine(registry,native,async()=>aliases);
    const input = async () => { const s = await engine.status(actor,registered.id); return {resourceVersion:s.resourceVersion,expectedHead:s.head}; };

    await t.test("guard and initial administrator approval fail before native mutation", async () => {
      const guarded = new KvNativeEngine(new KvRegistry(db,["apps"],kvConfig({ BORTUS_HISTORY_NAMESPACE:"history" })),native);
      const before = native.writes;
      await assert.rejects(guarded.adopt(actor,registered.id,{...(await input()),legacyAliases:aliases.map(a=>a.alias)}),denied(403));
      const user = await accounts.create(actor,{username:"scoped",passwordHash:"synthetic-hash",role:"write"});
      const current = await db.user.findUniqueOrThrow({where:{id:user.id}}), scoped={id:current.id,sessionVersion:current.sessionVersion};
      await registry.savePolicy(actor,{principal:"user:"+user.id,mountId:mount.id,prefix:"services/api",effect:"allow",actions:["list","read","create","update"]});
      await assert.rejects(engine.adoptionPreview(scoped,registered.id),denied(403));
      await assert.rejects(engine.read(scoped,registered.id),denied(409));
      assert.equal(native.writes,before);
    });
    await t.test("adoption snapshot preserves exact binary/special keys, 603 aliases and unrelated native metadata", async () => {
      const preview = await engine.adoptionPreview(actor,registered.id);
      assert.equal(preview.legacyAliases.length,603); assert(!JSON.stringify(preview).includes(marker));
      await assert.rejects(engine.adopt(actor,registered.id,{resourceVersion:preview.resourceVersion,expectedHead:0,legacyAliases:[]}),denied(409));
      const result = await engine.adopt(actor,registered.id,{resourceVersion:preview.resourceVersion,expectedHead:0,legacyAliases:aliases.map(a=>a.alias)});
      assert.equal(result.head,1); assert.equal(await db.kvLegacyGrant.count(),603);
      const fresh = await new KvNativeEngine(registry,native).read(actor,registered.id);
      assert.deepEqual(fresh.fields,exportFields(initial));
      const canonical = await native.read("apps","imported"); assert.equal(canonical.data!.unrelated,other);
      assert.equal(canonical.metadata!.annotations!["kubectl.kubernetes.io/last-applied-configuration"],marker);
      const history = (await native.list("history"))[0];
      assert.deepEqual(history.data,initial); assert.equal(history.immutable,true); assert(!JSON.stringify(history).includes(marker));
      assert(!history.metadata?.ownerReferences); assert(!history.metadata?.managedFields);
      const audit = await db.kvAudit.findMany(); assert(!JSON.stringify(audit).includes(marker)); assert(!JSON.stringify(audit).includes(other));
      assert(!JSON.stringify(await engine.versions(actor,registered.id)).includes(marker));
    });
    await t.test("static rotation links intent before generation, preserves grouped values and requires explicit current-head acknowledgement", async () => {
      const path=await registry.registerPath(actor,{mountId:mount.id,path:"rotation/static",namespace:"apps",name:"rotation-static",fields:[{field:"__proto__",key:"__proto__"},{field:"other",key:"other"}]});
      await engine.create(actor,path.id,{resourceVersion:"absent",expectedHead:0,fields:[{field:"__proto__",encoding:"utf8",value:"old static string"},{field:"other",encoding:"base64",value:Buffer.from([0,255,128]).toString("base64")}]});
      const created=await accounts.create(actor,{username:"rotation_writer",passwordHash:"synthetic-hash",role:"write"}),user=await db.user.findUniqueOrThrow({where:{id:created.id}}),scoped={id:user.id,sessionVersion:user.sessionVersion};
      await registry.savePolicy(actor,{principal:"user:"+user.id,mountId:mount.id,prefix:"rotation",effect:"allow",actions:["list","rotate"]});
      const rotations=new KvRotations(engine),consumer={kind:"Deployment" as const,namespace:"apps",name:"rotation-consumer"};
      await assert.rejects(rotations.prepare(scoped,{pathId:path.id,pathRevision:path.revision,field:"missing",consumer}),denied(400));
      await assert.rejects(rotations.prepare(scoped,{pathId:path.id,pathRevision:path.revision,field:"__proto__",consumer:{...consumer,namespace:"other"}}),denied(400));
      const row=await rotations.prepare(scoped,{pathId:path.id,pathRevision:path.revision,field:"__proto__",consumer});
      await assert.rejects(rotations.prepare(scoped,{pathId:path.id,pathRevision:path.revision,field:"__proto__",consumer}),denied(409));
      const state=await engine.status(scoped,path.id),before=native.writes;
      await assert.rejects(rotations.generate(scoped,row.id,{revision:row.revision,confirmPath:path.path,resourceVersion:"stale",expectedHead:state.head}),denied(409));assert.equal(native.writes,before);
      let linked=false;
      native.afterCreate=async()=>{const intent=await db.kvRotation.findUniqueOrThrow({where:{id:row.id}});assert.equal(intent.state,"replace-pending");assert(intent.operationId);assert.equal((await db.kvOperation.findUniqueOrThrow({where:{id:intent.operationId}})).outcome,"pending");linked=true;};
      const outcomes=await Promise.allSettled([0,1].map(()=>rotations.generate(scoped,row.id,{revision:row.revision,confirmPath:path.path,resourceVersion:state.resourceVersion,expectedHead:state.head})));
      native.afterCreate=undefined;
      assert.equal(outcomes.filter(r=>r.status==="fulfilled").length,1);assert(linked);
      const committed=await db.kvRotation.findUniqueOrThrow({where:{id:row.id}});assert.equal(committed.state,"awaiting-ack");
      const current=await native.read("apps","rotation-static"),generated=Buffer.from(current.data!["__proto__"],"base64").toString("utf8");
      assert(/^[A-Za-z0-9_-]{43}$/.test(generated));assert.equal(current.data!.other,Buffer.from([0,255,128]).toString("base64"));
      const persisted={intents:await db.kvRotation.findMany(),ops:await db.kvOperation.findMany(),audit:await db.kvAudit.findMany()};
      assert(!JSON.stringify(persisted).includes(generated));assert(!JSON.stringify(outcomes).includes(generated));
      await assert.rejects(engine.read(scoped,path.id),denied(403));
      await assert.rejects(rotations.generate(scoped,row.id,{revision:committed.revision,confirmPath:path.path,resourceVersion:current.metadata!.resourceVersion!,expectedHead:state.head+1}),denied(409));
      await assert.rejects(rotations.cancel(scoped,row.id,committed.revision,path.path),denied(409));
      const ack={revision:committed.revision,confirmPath:path.path,confirmConsumer:"apps/Deployment/rotation-consumer",confirmConsumption:true as const,resourceVersion:current.metadata!.resourceVersion!,expectedHead:state.head+1};
      await assert.rejects(rotations.acknowledge(scoped,row.id,{...ack,confirmConsumer:"wrong"}),denied(400));
      const object=native.objects.get(native.key("apps","rotation-static"))!;const original=object.data!.other;object.data!.other=Buffer.from("external change").toString("base64");
      await assert.rejects(rotations.acknowledge(scoped,row.id,ack),denied(409));object.data!.other=original;
      const acknowledged=await rotations.acknowledge(scoped,row.id,ack);assert.equal(acknowledged.rotation.state,"acknowledged");assert(acknowledged.acknowledgement.includes("operator assertion"));
      assert.equal((await rotations.list(scoped,path.id)).items.length,1);
      const untouched=await rotations.prepare(scoped,{pathId:path.id,pathRevision:path.revision,field:"__proto__",consumer});
      assert.equal((await rotations.cancel(scoped,untouched.id,untouched.revision,path.path)).state,"cancelled");
      const ambiguous=await rotations.prepare(scoped,{pathId:path.id,pathRevision:path.revision,field:"__proto__",consumer}),fresh=await engine.status(scoped,path.id);
      native.replaceMode="after-outage";
      await assert.rejects(rotations.generate(scoped,ambiguous.id,{revision:ambiguous.revision,confirmPath:path.path,resourceVersion:fresh.resourceVersion,expectedHead:fresh.head}),error=>error instanceof KvMutationError&&error.outcome==="ambiguous");
      const unresolved=await db.kvRotation.findUniqueOrThrow({where:{id:ambiguous.id}});assert.equal(unresolved.state,"recovery-required");
      await assert.rejects(rotations.cancel(scoped,ambiguous.id,unresolved.revision,path.path),denied(409));
      native.readOutage=false;const recovered=await rotations.resolve(scoped,ambiguous.id);assert.equal(recovered.rotation.state,"awaiting-ack");
      await assert.rejects(rotations.generate(scoped,ambiguous.id,{revision:recovered.rotation.revision,confirmPath:path.path,resourceVersion:fresh.resourceVersion,expectedHead:fresh.head}),denied(409));
      let consumerState={uid:"consumer-uid",resourceVersion:"consumer-rv",rotationId:undefined as string|undefined},reloads=0;
      const withConsumer=new KvRotations(engine,{inspect:async()=>({...consumerState}),reload:async pending=>{
        reloads++;const reserved=await db.kvRotation.findUniqueOrThrow({where:{id:pending.id}});assert.equal(reserved.state,"reload-pending");assert.equal(reserved.consumerUid,consumerState.uid);
        consumerState={...consumerState,resourceVersion:"changed-rv",rotationId:pending.id};throw new KvError(503,"Synthetic consumer reply timeout");
      }});
      await assert.rejects(withConsumer.consumerPreview(scoped,ambiguous.id),denied(403));
      const preview=await withConsumer.consumerPreview(actor,ambiguous.id),head=await engine.status(actor,path.id);
      const reload={revision:preview.revision,confirmPath:path.path,confirmConsumer:preview.consumer,consumerUid:preview.uid,consumerResourceVersion:preview.resourceVersion,expectedHead:head.head,resourceVersion:head.resourceVersion};
      await assert.rejects(withConsumer.reload(scoped,ambiguous.id,reload),denied(403));assert.equal(reloads,0);
      const requested=await withConsumer.reload(actor,ambiguous.id,reload);assert.equal(requested.rotation.state,"reload-requested");assert.equal(reloads,1);
      await assert.rejects(withConsumer.reload(actor,ambiguous.id,{...reload,revision:requested.rotation.revision}),denied(409));assert.equal(reloads,1);
      await rotations.acknowledge(scoped,ambiguous.id,{revision:requested.rotation.revision,confirmPath:path.path,confirmConsumer:preview.consumer,confirmConsumption:true,resourceVersion:head.resourceVersion,expectedHead:head.head});
      const withdrawn=await rotations.prepare(scoped,{pathId:path.id,pathRevision:path.revision,field:"__proto__",consumer}),pre=await engine.status(scoped,path.id);
      await rotations.generate(scoped,withdrawn.id,{revision:withdrawn.revision,confirmPath:path.path,resourceVersion:pre.resourceVersion,expectedHead:pre.head});
      let withdrawnReloads=0;
      const recovering=new KvRotations(engine,{inspect:async()=>({...consumerState}),reload:async pending=>{
        withdrawnReloads++;consumerState={...consumerState,rotationId:pending.id};await db.user.update({where:{id:actor.id},data:{engineAdmin:false}});throw new KvError(503,"Synthetic timeout after administrator withdrawal");
      }});
      const nextPreview=await recovering.consumerPreview(actor,withdrawn.id),nextHead=await engine.status(scoped,path.id);
      try{
        await assert.rejects(recovering.reload(actor,withdrawn.id,{revision:nextPreview.revision,confirmPath:path.path,confirmConsumer:nextPreview.consumer,consumerUid:nextPreview.uid,consumerResourceVersion:nextPreview.resourceVersion,resourceVersion:nextHead.resourceVersion,expectedHead:nextHead.head}),error=>error instanceof KvMutationError&&error.outcome==="recovery-required");
        assert.equal((await db.kvRotation.findUniqueOrThrow({where:{id:withdrawn.id}})).state,"reload-pending");
        await assert.rejects(recovering.resolve(scoped,withdrawn.id),denied(403));
      }finally{await db.user.update({where:{id:actor.id},data:{engineAdmin:true}});}
      assert.equal((await recovering.resolve(actor,withdrawn.id)).rotation.state,"reload-requested");assert.equal(withdrawnReloads,1);
    });
    await t.test("flat/legacy bridges cannot bypass adopted policies, exact alias grants or history isolation", async () => {
      const raw = new SecretStore(native,["apps"],flatSecretGuard(registry,native,async()=>actor));
      const key={namespace:"apps",name:"imported",key:"constructor"};
      assert.equal((await raw.read(key)).value,"first credential");
      const denyRule=await registry.savePolicy(actor,{principal:"user:"+actor.id,mountId:mount.id,prefix:registered.path,effect:"deny",actions:["read"]});
      await assert.rejects(raw.read(key),denied(403)); await registry.deletePolicy(actor,denyRule.id,denyRule.revision);
      const rv=(await engine.status(actor,registered.id)).resourceVersion;
      await assert.rejects(raw.write({...key,value:"extra-ignored"} as any,"not written","update",rv),denied(409));
      await assert.rejects(raw.deleteKey(key,rv),denied(409));
      const legacy=(alias:string)=>new SecretStore(native,["apps"],flatSecretGuard(registry,native,async()=>null,alias));
      for(const ref of aliases) {
        if(ref.key==="constructor") assert.equal((await legacy(ref.alias).read(ref)).value,"first credential");
        else await assert.rejects(legacy(ref.alias).read(ref),(error:unknown)=>error instanceof SecretError&&error.status===400); // Binary aliases keep the historical text API refusal.
      }
      await assert.rejects(legacy("new-post-adoption-alias").read(key),denied(403));
      await db.kvLegacyGrant.deleteMany({where:{pathId:registered.id,alias:aliases[0].alias}});
      await assert.rejects(legacy(aliases[0].alias).read(aliases[0]),denied(403));
      const legacyRule={principal:"legacy-lookup",mountId:mount.id,prefix:registered.path,effect:"deny" as const,actions:["read" as const]};
      const preview=await registry.previewPolicy(actor,legacyRule);
      const rule=await registry.savePolicy(actor,legacyRule,undefined,undefined,{fingerprint:preview.fingerprint!,aliases:aliases.map(ref=>ref.alias),confirmLegacyImpact:true});
      await assert.rejects(legacy(aliases[2].alias).read(aliases[2]),denied(403));
      const removePreview=await registry.previewPolicy(actor,null,rule.id,rule.revision);
      await registry.deletePolicy(actor,rule.id,rule.revision,{fingerprint:removePreview.fingerprint!,aliases:aliases.map(ref=>ref.alias),confirmLegacyImpact:true});
      await db.kvServicePrincipal.update({where:{id:"legacy-lookup"},data:{enabled:false}});
      await assert.rejects(requireLegacyPrincipal(registry),denied(403));
      await assert.rejects(legacy(aliases[2].alias).read(aliases[2]),denied(403));
      await db.kvServicePrincipal.update({where:{id:"legacy-lookup"},data:{enabled:true}});
      const history=(await native.list("history"))[0];
      const accidental=new SecretStore(native,["apps","history"],flatSecretGuard(registry,native,async()=>actor));
      await assert.rejects(accidental.read({namespace:"history",name:history.metadata!.name!,key:"constructor"}),denied(403));
      const unadopted=native.seed("apps","unadopted",{key:Buffer.from("legacy current").toString("base64")});
      assert.equal((await legacy("original_unadopted_alias").read({namespace:"apps",name:unadopted.metadata!.name!,key:"key"})).value,"legacy current");
      const brokenDb={kvServicePrincipal:db.kvServicePrincipal,kvField:{findUnique:async()=>{throw new Error(marker);}}} as unknown as PrismaClient;
      const broken=new SecretStore(native,["apps"],flatSecretGuard(new KvRegistry(brokenDb,["apps"],registry.config),native,async()=>null,aliases[2].alias));
      await assert.rejects(broken.read(aliases[2]),(error:unknown)=>error instanceof SecretError&&error.status===503&&!error.message.includes(marker));
      await db.kvField.deleteMany({where:{pathId:registered.id,key:"constructor"}});
      await assert.rejects(legacy(aliases[2].alias).read(aliases[2]),denied(503));
      await db.kvField.create({data:{pathId:registered.id,field:"constructor",...key}});
    });
    await t.test("missing/stale prerequisites and concurrent writers cannot overwrite a new head", async () => {
      await assert.rejects(engine.change(actor,registered.id,{fields:[]}),denied(428));
      await assert.rejects(engine.change(actor,registered.id,{resourceVersion:"stale",expectedHead:1,fields:[]}),denied(409));
      const expected = await input();
      const values = [{field:"__proto__",encoding:"base64",value:initial.__proto__},{field:"constructor",encoding:"utf8",value:"changed"},{field:"toString",encoding:"utf8",value:""}];
      const results = await Promise.allSettled([engine.change(actor,registered.id,{...expected,fields:values}),engine.change(actor,registered.id,{...expected,fields:values})]);
      assert.equal(results.filter(r=>r.status==="fulfilled").length,1);
      for(const result of results) if(result.status==="rejected") assert(denied(409)(result.reason));
      assert.equal((await engine.status(actor,registered.id)).head,2);
      assert.equal((await native.read("apps","imported")).data!.unrelated,other);
    });
    await t.test("automation has a distinct scoped audience, native CAS and fresh revocation without initialization authority", async () => {
      const p=await registry.registerPath(actor,{mountId:mount.id,path:"automation/consumer",namespace:"apps",name:"automated",fields:[{field:"binary",key:"key"}]});
      const created=await engine.create(actor,p.id,{resourceVersion:"absent",expectedHead:0,fields:[]});
      const identity=await registry.issueIdentity(actor,{ownerId:actor.id,name:"automated",expiresAt:new Date(Date.now()+60000),scopes:[{mountId:mount.id,prefix:"automation",actions:["list","read","update","create"]}]});
      const token=await registry.authenticateIdentity("Bearer "+identity.credential);
      const current=await runAutomation(engine,token,{operation:"read",pathId:p.id});assert("fields" in current);assert.equal(current.fields.length,0);
      assert.equal((await registry.capabilities(token,p.id)).initializationAllowed,false);
      await assert.rejects(runAutomation(engine,actor,{operation:"read",pathId:p.id}),denied(401));
      await assert.rejects(runAutomation(engine,token,{operation:"read",pathId:registered.id}),denied(403));
      for(const operation of ["create","adopt","shell","identity-issue"]) assert.equal(automationRequest.safeParse({operation,pathId:p.id}).success,false);
      assert.equal(automationRequest.safeParse({operation:"read",pathId:p.id,command:marker}).success,false);
      await assert.rejects(engine.create(token,p.id,{resourceVersion:"absent",expectedHead:0,fields:[]}),denied(403));
      await assert.rejects(runAutomation(engine,token,{operation:"update",pathId:p.id,fields:[]}),denied(428));
      const changed=await runAutomation(engine,token,{operation:"update",pathId:p.id,resourceVersion:created.resourceVersion,expectedHead:1,fields:[{field:"binary",encoding:"base64",value:initial.__proto__}]});
      assert("head" in changed);assert.equal(changed.head,2);
      const historical=await runAutomation(engine,token,{operation:"read",pathId:p.id,version:1});assert("fields" in historical);assert.equal(historical.fields.length,0);
      const tokenAudit=await registry.listAudit(token,{pathId:p.id});assert(tokenAudit.items.some(row=>row.actorId===identity.id));
      assert(!JSON.stringify(tokenAudit).includes(identity.credential));assert(!JSON.stringify(tokenAudit).includes(initial.__proto__));
      await registry.revokeIdentity(actor,identity.id);const before=native.reads;
      await assert.rejects(runAutomation(engine,token,{operation:"read",pathId:p.id}),denied(401));assert.equal(native.reads,before);
    });
    await t.test("protected transfers round-trip binary/empty fields with explicit overwrite, partial outcomes and bounded metadata-only preview", async () => {
      const p=await registry.registerPath(actor,{mountId:mount.id,path:"transfer/source",namespace:"apps",name:"transfer-source",fields:[{field:"binary",key:"__proto__"},{field:"empty",key:"constructor"}]});
      await engine.create(actor,p.id,{resourceVersion:"absent",expectedHead:0,fields:[{field:"binary",encoding:"base64",value:initial.__proto__},{field:"empty",encoding:"utf8",value:""}]});
      const nativeSource=native.objects.get("apps/transfer-source")!;nativeSource.data!.unrelated=other;nativeSource.metadata!.annotations!["last-applied"]=marker;nativeSource.metadata!.resourceVersion=String(++native.counter);
      const transfer=new KvTransfer(engine),bundle=await transfer.export(actor,{confirmCredentials:true,selections:[{pathId:p.id}]});
      assert.equal(bundle.documents[0].sourceVersion,1);assert(!JSON.stringify(bundle).includes(marker));assert(!JSON.stringify(bundle).includes(other));assert.equal(bundle.documents[0].fields.find(field=>field.field==="empty")!.value,"");
      const scopedUser=await db.user.findUniqueOrThrow({where:{username:"scoped"}}),scoped={id:scopedUser.id,sessionVersion:scopedUser.sessionVersion},before=native.reads;
      await assert.rejects(transfer.export(scoped,{confirmCredentials:true,selections:[{pathId:p.id}]}),denied(403));assert.equal(native.reads,before);
      await registry.savePolicy(actor,{principal:"user:"+scoped.id,mountId:mount.id,prefix:"transfer/source",effect:"allow",actions:["export"]});
      await assert.rejects(engine.read(scoped,p.id),denied(403));await transfer.export(scoped,{confirmCredentials:true,selections:[{pathId:p.id}]});
      const restored:z.infer<typeof bundleSchema>={...bundle,documents:bundle.documents.map(doc=>({...doc,path:"transfer/restored",name:"transfer-restored"}))};
      const plans=(preview:Awaited<ReturnType<KvTransfer["preview"]>>,overwrite=false)=>preview.plans.map((p:any)=>({documentIndex:p.documentIndex,pathId:p.pathId,revision:p.revision,resourceVersion:p.resourceVersion,expectedHead:p.expectedHead,overwrite}));
      const preview=await transfer.preview(actor,restored);assert(preview.plans.every(p=>p.outcome==="ready"));assert(!JSON.stringify(preview).includes(initial.__proto__));
      const imported=await transfer.import(actor,{bundle:restored,plans:plans(preview),confirmCredentials:true});assert.equal(imported.success,true);
      const restoredId=imported.outcomes[0].pathId!;assert.deepEqual((await engine.read(actor,restoredId)).fields,bundle.documents[0].fields);assert(!JSON.stringify(await native.read("apps","transfer-restored")).includes(marker));
      const empty={...restored,documents:restored.documents.map(doc=>({...doc,fields:[]}))},updatePreview=await transfer.preview(actor,empty);
      assert.equal((await transfer.import(actor,{bundle:empty,plans:plans(updatePreview),confirmCredentials:true})).outcomes[0].status,409);
      const oldPath=await registry.path(restoredId);await registry.changeRetention(actor,oldPath.id,oldPath.revision,oldPath.retention+1);
      assert.equal((await transfer.import(actor,{bundle:empty,plans:plans(updatePreview,true),confirmCredentials:true})).outcomes[0].status,409);
      const updated=await transfer.import(actor,{bundle:empty,plans:plans(await transfer.preview(actor,empty),true),confirmCredentials:true});assert.equal(updated.success,true);assert.equal((await engine.read(actor,restoredId)).fields.length,0);
      assert.deepEqual((await transfer.export(actor,{selections:[{pathId:restoredId,version:1}],confirmCredentials:true})).documents[0].fields,bundle.documents[0].fields);
      const partial={...restored,documents:[restored.documents[0],{...restored.documents[0],path:"transfer/second",name:"transfer-second"}]},partialPlans=plans(await transfer.preview(actor,partial),true);partialPlans[0].resourceVersion="stale";
      const result=await transfer.import(actor,{bundle:partial,plans:partialPlans,confirmCredentials:true});assert.equal(result.success,false);assert.equal(result.outcomes[0].status,409);assert.equal(result.outcomes[1].outcome,"committed");
      assert.equal((await engine.read(actor,restoredId)).fields.length,0);
      const invalid={...restored,documents:[{...restored.documents[0],fields:[{field:"binary",encoding:"base64" as const,value:"bad="}]}]},reads=native.reads;
      await assert.rejects(transfer.preview(actor,invalid),denied(400));assert.equal(native.reads,reads);
      await assert.rejects(transfer.preview(actor,{...restored,documents:[restored.documents[0],restored.documents[0]]}),denied(400));
      const large={...restored,documents:Array.from({length:4},(_,index)=>({...restored.documents[0],path:"transfer/large-"+index,name:"transfer-large-"+index,fields:[{field:"binary",encoding:"utf8" as const,value:"x".repeat(256*1024)}]}))};
      await assert.rejects(transfer.preview(actor,large),denied(413));
      const oversized=await registry.registerPath(actor,{mountId:mount.id,path:"transfer/oversized",namespace:"apps",name:"transfer-oversized",fields:[{field:"key",key:"key"}]});
      const importedLarge=native.seed("apps","transfer-oversized",{key:Buffer.from("selected").toString("base64"),unrelated:"a".repeat(900*1024)}),writes=native.writes;
      await assert.rejects(engine.adopt(actor,oversized.id,{resourceVersion:importedLarge.metadata!.resourceVersion,expectedHead:0,legacyAliases:[]}),denied(413));assert.equal(native.writes,writes);
      const cancelled=new AbortController();cancelled.abort();await assert.rejects(new KvTransfer(engine,cancelled.signal).export(actor,{confirmCredentials:true,selections:[{pathId:p.id}]}),denied(408));
      assert(!JSON.stringify(await db.kvAudit.findMany()).includes(initial.__proto__));assert(!JSON.stringify(await db.kvOperation.findMany()).includes(initial.__proto__));
    });
    await t.test("confirmed destruction CAS-removes references, retains canonical data and keeps monotonic versions", async()=>{
      const p=await registry.registerPath(actor,{mountId:mount.id,path:"cleanup/destroy",namespace:"apps",name:"destroy",fields:[{field:"key",key:"key"}]});
      await engine.create(actor,p.id,{resourceVersion:"absent",expectedHead:0,fields:[{field:"key",encoding:"utf8",value:"first"}]});
      const current=async()=>{const s=await engine.status(actor,p.id);return {resourceVersion:s.resourceVersion,expectedHead:s.head};};
      native.malformedReplaceReply=true;await engine.change(actor,p.id,{...await current(),fields:[{field:"key",encoding:"utf8",value:"second"}]});
      const source=native.objects.get("apps/destroy")!;source.data!.unrelated=other;source.metadata!.annotations!["private-other-key"]=marker;source.metadata!.resourceVersion=String(++native.counter);
      const before=await current(),old=copy(source),deletes=native.deletes.length,writes=native.writes;
      await assert.rejects(engine.destroy(actor,p.id,{...before,versions:[1],confirmPath:"wrong"}),denied(400));
      await assert.rejects(engine.destroy(actor,p.id,{...before,versions:[1,1],confirmPath:p.path}),denied(400));
      await assert.rejects(engine.destroy(actor,p.id,{...before,versions:[2],confirmPath:p.path}),denied(409));
      await assert.rejects(engine.destroy(actor,p.id,{expectedHead:2,versions:[1],confirmPath:p.path}),denied(428));
      const scopedUser=await db.user.findUniqueOrThrow({where:{username:"scoped"}}),scoped={id:scopedUser.id,sessionVersion:scopedUser.sessionVersion};
      const reads=native.reads;await assert.rejects(engine.destroy(scoped,p.id,{...before,versions:[1],confirmPath:p.path}),denied(403));assert.equal(native.reads,reads);
      const aborted=new AbortController();aborted.abort();await assert.rejects(engine.destroy(actor,p.id,{...before,versions:[1],confirmPath:p.path},aborted.signal),denied(408));
      assert.equal(native.writes,writes);assert.equal(native.deletes.length,deletes);
      const first=parseState(source).paths[0].versions[0],owned=native.objects.get("history/"+first.name)!,saved=copy(owned);
      owned.metadata!.uid="replaced-history";await assert.rejects(engine.destroy(actor,p.id,{...before,versions:[1],confirmPath:p.path}),denied(409));native.objects.set("history/"+first.name,saved);
      native.malformedReplaceReply=true;const result=await engine.destroy(actor,p.id,{...before,versions:[1],confirmPath:p.path});assert.equal(result.cleanupComplete,true);assert.equal(result.head,2);
      assert.deepEqual(result.cleanup.map(c=>c.outcome),["deleted"]);assert.equal(native.deletes.length,deletes+1);assert.equal(native.deletes.at(-1)!.namespace,"history");
      await assert.rejects(native.replace("apps","destroy",old),error=>(error as {code:number}).code===409);
      await assert.rejects(engine.read(actor,p.id,1),denied(404));assert.equal((await engine.read(actor,p.id)).fields[0].value,Buffer.from("second").toString("base64"));
      await engine.change(actor,p.id,await current(),"delete");
      const tombstone=await engine.destroy(actor,p.id,{...await current(),versions:[2,3],confirmPath:p.path});assert.equal(tombstone.head,0);assert.equal(tombstone.cleanupComplete,true);
      assert.deepEqual(native.objects.get("apps/destroy")!.data,{unrelated:other});assert.equal(native.objects.get("apps/destroy")!.metadata!.annotations!["private-other-key"],marker);
      assert.deepEqual((await engine.read(actor,p.id)).fields,[]);assert.equal((await engine.change(actor,p.id,{...await current(),fields:[]})).head,4);
      assert(!JSON.stringify(result).includes(marker));assert(!JSON.stringify(result).includes(other));
    });
    await t.test("destruction audit failures and source replacement retain recoverable history with explicit partial outcomes",async()=>{
      const p=await registry.registerPath(actor,{mountId:mount.id,path:"cleanup/partial",namespace:"apps",name:"partial",fields:[{field:"key",key:"key"}]});
      await engine.create(actor,p.id,{resourceVersion:"absent",expectedHead:0,fields:[]});
      const current=async()=>{const s=await engine.status(actor,p.id);return {resourceVersion:s.resourceVersion,expectedHead:s.head};};
      await engine.change(actor,p.id,{...await current(),fields:[]});
      const ref=parseState(native.objects.get("apps/partial")!).paths[0].versions[0],before=native.writes,deletes=native.deletes.length;
      await db.$executeRawUnsafe("CREATE TRIGGER deny_cleanup BEFORE INSERT ON kv_audit BEGIN SELECT RAISE(ABORT, 'synthetic audit unavailable'); END");
      await assert.rejects(engine.destroy(actor,p.id,{...await current(),versions:[1],confirmPath:p.path}),denied(503));assert.equal(native.writes,before);assert.equal(native.deletes.length,deletes);
      await db.$executeRawUnsafe("DROP TRIGGER deny_cleanup");
      native.afterReplace=async()=>{await db.$executeRawUnsafe("CREATE TRIGGER deny_cleanup BEFORE INSERT ON kv_audit WHEN NEW.action = 'history-delete' BEGIN SELECT RAISE(ABORT, 'synthetic audit unavailable'); END");};
      let result;
      try{result=await engine.destroy(actor,p.id,{...await current(),versions:[1],confirmPath:p.path});}finally{native.afterReplace=undefined;await db.$executeRawUnsafe("DROP TRIGGER deny_cleanup");}
      assert.equal(result.outcome,"committed");assert.equal(result.cleanupComplete,false);assert.equal(result.cleanup[0].status,503);assert(native.objects.has("history/"+ref.name));assert.equal(native.deletes.length,deletes);
      await engine.change(actor,p.id,{...await current(),fields:[]});
      const secondRef=parseState(native.objects.get("apps/partial")!).paths[0].versions[0];
      native.afterReplace=async()=>{await db.$executeRawUnsafe("CREATE TRIGGER deny_cleanup BEFORE INSERT ON kv_audit WHEN NEW.action = 'history-delete' AND NEW.outcome = 'deleted' BEGIN SELECT RAISE(ABORT, 'synthetic audit unavailable'); END");};
      try{result=await engine.destroy(actor,p.id,{...await current(),versions:[secondRef.version],confirmPath:p.path});}finally{native.afterReplace=undefined;await db.$executeRawUnsafe("DROP TRIGGER deny_cleanup");}
      assert.equal(result.cleanupComplete,false);assert.equal(result.cleanup[0].status,503);assert(!native.objects.has("history/"+secondRef.name));const afterDeleted=native.deletes.length;
      const headRef=parseState(native.objects.get("apps/partial")!).paths[0].versions[0];
      await engine.change(actor,p.id,await current(),"delete");
      native.afterReplace=async()=>{const replacement=copy(native.objects.get("apps/partial")!);replacement.metadata!.uid="external-source-replacement";native.objects.set("apps/partial",replacement);};
      try{result=await engine.destroy(actor,p.id,{...await current(),versions:[headRef.version],confirmPath:p.path});}finally{native.afterReplace=undefined;}
      assert.equal(result.cleanupComplete,false);assert.equal(result.cleanup[0].status,409);assert(native.objects.has("history/"+headRef.name));assert.equal(native.deletes.length,afterDeleted);
    });
    await t.test("maximum-size owned histories remain operable through metadata-only GC preview and UID/RV-fenced cleanup",async()=>{
      const p=await registry.registerPath(actor,{mountId:mount.id,path:"cleanup/large",namespace:"apps",name:"large",retention:1,fields:[{field:"blob",key:"blob"}]});
      await engine.create(actor,p.id,{resourceVersion:"absent",expectedHead:0,fields:[{field:"blob",encoding:"base64",value:Buffer.alloc(256*1024,1).toString("base64")}]});
      for(let i=2;i<=25;i++) {
        const status=await engine.status(actor,p.id);
        await engine.change(actor,p.id,{resourceVersion:status.resourceVersion,expectedHead:status.head,fields:[{field:"blob",encoding:"base64",value:Buffer.alloc(256*1024,i).toString("base64")}]});
      }
      const histories=[...native.objects.values()].filter(secret=>secret.metadata?.annotations?.[HISTORY_ANNOTATION]?.includes(p.id));
      assert.equal(histories.length,25);assert(Buffer.byteLength(JSON.stringify({items:histories.slice(0,20)}))>4*1024*1024);
      for(const history of histories) history.metadata!.creationTimestamp=new Date(Date.now()-48*3600000);
      const fullList=native.list.bind(native);native.list=async()=>{throw new Error("Value-bearing history enumeration forbidden");};
      const beforeDeletes=native.deletes.length;
      try {
        const preview=await engine.gcPreview(actor,p.id);assert.equal(preview.eligible,24);assert.equal(preview.items.length,24);assert.equal(preview.retained,1);
        assert(!JSON.stringify(preview).includes(Buffer.alloc(256*1024,25).toString("base64")));
        const selected=preview.items[0], original=native.objects.get("history/"+selected.name)!;
        original.metadata!.resourceVersion=String(++native.counter);
        await assert.rejects(engine.gc(actor,p.id,{...preview,histories:[selected],confirmPath:p.path}),denied(409));assert.equal(native.deletes.length,beforeDeletes);
        const refreshed=await engine.gcPreview(actor,p.id), result=await engine.gc(actor,p.id,{...refreshed,histories:[refreshed.items[0]],confirmPath:p.path});
        assert.equal(result.cleanupComplete,true);assert.equal(native.deletes.length,beforeDeletes+1);
        assert.equal(native.deletes.at(-1)!.uid,refreshed.items[0].uid);assert.equal(native.deletes.at(-1)!.resourceVersion,refreshed.items[0].resourceVersion);
        assert(native.objects.has("apps/large"));assert.equal((await engine.versions(actor,p.id)).items.length,1);
      } finally { native.list=fullList; }
    });

    await t.test("explicit administrator GC checks age/references/identity, fences stale CAS and records timeout read-back",async()=>{
      const p=await registry.registerPath(actor,{mountId:mount.id,path:"cleanup/gc",namespace:"apps",name:"gc",retention:1,fields:[{field:"key",key:"key"}]});
      await engine.create(actor,p.id,{resourceVersion:"absent",expectedHead:0,fields:[{field:"key",encoding:"base64",value:initial.__proto__}]});
      const current=async()=>{const s=await engine.status(actor,p.id);return {resourceVersion:s.resourceVersion,expectedHead:s.head};};
      const oldRef=parseState(native.objects.get("apps/gc")!).paths[0].versions[0];
      await engine.change(actor,p.id,{...await current(),fields:[]});
      const orphan=native.objects.get("history/"+oldRef.name)!;orphan.metadata!.creationTimestamp=new Date(Date.now()-48*3600000);
      const preview=await engine.gcPreview(actor,p.id);assert.equal(preview.items.length,1);assert.equal(preview.minimumAgeHours,24);assert(!JSON.stringify(preview).includes(initial.__proto__));
      const input={...preview,histories:preview.items,confirmPath:p.path},deletes=native.deletes.length,writes=native.writes;
      await assert.rejects(engine.gc(actor,p.id,{...input,histories:[{...preview.items[0],uid:"forged"}]}),denied(409));assert.equal(native.writes,writes);assert.equal(native.deletes.length,deletes);
      await assert.rejects(engine.gc(actor,p.id,{...input,histories:[{...preview.items[0],resourceVersion:"stale"}]}),denied(409));
      await assert.rejects(engine.gc(actor,p.id,{...input,resourceVersion:"stale"}),denied(409));
      orphan.metadata!.creationTimestamp=new Date();await assert.rejects(engine.gc(actor,p.id,input),denied(409));orphan.metadata!.creationTimestamp=new Date(Date.now()-48*3600000);
      const source=native.objects.get("apps/gc")!,state=parseState(source),saved=copy(source);state.paths[0].versions.push(oldRef);source.metadata!.annotations![STATE_ANNOTATION]=JSON.stringify(state);
      await assert.rejects(engine.gc(actor,p.id,input),denied(409));assert.equal((await engine.gcPreview(actor,p.id)).items.length,0);native.objects.set("apps/gc",saved);
      const scopedUser=await db.user.findUniqueOrThrow({where:{username:"scoped"}}),scoped={id:scopedUser.id,sessionVersion:scopedUser.sessionVersion};
      await assert.rejects(engine.gcPreview(scoped,p.id),denied(403));await assert.rejects(engine.gc(scoped,p.id,input),denied(403));
      const guarded=new KvNativeEngine(new KvRegistry(db,["apps"],kvConfig({BORTUS_HISTORY_NAMESPACE:"history"})),native);await assert.rejects(guarded.gc(actor,p.id,input),denied(403));
      native.replaceMode="before";await assert.rejects(engine.gc(actor,p.id,input),denied(503));assert.equal(native.deletes.length,deletes);assert(native.objects.has("history/"+oldRef.name));
      native.afterReplace=async()=>{await db.user.update({where:{id:actor.id},data:{engineAdmin:false}});};
      let revoked;
      try{revoked=await engine.gc(actor,p.id,input);}finally{native.afterReplace=undefined;await db.user.update({where:{id:actor.id},data:{engineAdmin:true}});}
      assert.equal(revoked.cleanupComplete,false);assert.equal(revoked.cleanup[0].status,403);assert.equal(native.deletes.length,deletes);assert(native.objects.has("history/"+oldRef.name));
      const refresh=await engine.gcPreview(actor,p.id);native.replaceMode="after";native.deleteMode="after";
      const result=await engine.gc(actor,p.id,{...refresh,histories:refresh.items,confirmPath:p.path});assert.equal(result.cleanupComplete,true);assert.equal(result.cleanup[0].outcome,"absent");
      assert(!native.objects.has("history/"+oldRef.name));assert.equal(native.deletes.length,deletes+1);assert.equal(native.deletes.at(-1)!.uid,oldRef.uid);
      await assert.rejects(native.replace("apps","gc",saved),error=>(error as {code:number}).code===409);assert.equal((await engine.status(actor,p.id)).head,2);
      assert((await db.kvAudit.findMany({where:{operationId:result.operationId,action:"history-delete"}})).some(a=>a.outcome==="absent"));
      assert(native.deletes.every(d=>d.namespace==="history"));assert(!JSON.stringify(await db.kvAudit.findMany()).includes(initial.__proto__));
      for(let index=0;index<105;index++){
        const operationId=randomUUID(),name="kv-"+p.id.replaceAll("-","")+"-"+operationId.replaceAll("-","").slice(0,24),body=historyBody(await registry.path(p.id),saved.metadata!.uid!,"history",name,3,operationId,{},false);
        native.seed("history",name,{},body);native.objects.get("history/"+name)!.metadata!.creationTimestamp=new Date(Date.now()-48*3600000);
      }
      const bounded=await engine.gcPreview(actor,p.id);assert.equal(bounded.items.length,100);assert.equal(bounded.eligible,105);assert.equal(bounded.complete,false);
      const beforeUnknown=native.deletes.length;await assert.rejects(engine.gc(actor,p.id,{...bounded,histories:[bounded.items[0]],confirmPath:p.path}),denied(409));assert.equal(native.deletes.length,beforeUnknown);
      native.objects.delete("apps/gc");const remaining=(await native.list("history")).length;
      await assert.rejects(engine.gcPreview(actor,p.id),(error:unknown)=>error instanceof SecretError&&error.status===404);assert.equal((await native.list("history")).length,remaining);
    });
    await t.test("external selected-key drift requires reconcile; rollback creates a new immutable version", async () => {
      const changed = native.objects.get("apps/imported")!; changed.data!["constructor"]=Buffer.from("external").toString("base64"); changed.metadata!.resourceVersion=String(++native.counter);
      await assert.rejects(engine.read(actor,registered.id),denied(409));
      await assert.rejects(engine.change(actor,registered.id,{...(await input()),fields:[]}),denied(409));
      assert.equal((await engine.change(actor,registered.id,await input(),"reconcile")).head,3);
      assert.equal((await engine.change(actor,registered.id,{...(await input()),version:1},"rollback")).head,4);
      assert.deepEqual((await engine.read(actor,registered.id)).fields,exportFields(initial));
      assert.deepEqual((await engine.read(actor,registered.id,1)).fields,exportFields(initial));
    });
    await t.test("positive read-back resolves create/replace timeouts; negative or unavailable read-back stays ambiguous", async () => {
      native.createTimeout=true; native.replaceMode="after";
      const result=await engine.change(actor,registered.id,{...(await input()),fields:[]}); assert.equal(result.outcome,"committed");
      native.replaceMode="before";
      let pending:KvMutationError|undefined;
      await assert.rejects(engine.change(actor,registered.id,{...(await input()),fields:[]}),error=>{if(error instanceof KvMutationError) pending=error; return denied(503)(error);});
      assert.equal(pending!.outcome,"ambiguous"); assert.equal((await engine.resolve(actor,pending!.operationId)).outcome,"ambiguous");
      native.replaceMode="after-outage";
      let late:KvMutationError|undefined;
      await assert.rejects(engine.change(actor,registered.id,{...(await input()),fields:[{field:"constructor",encoding:"utf8",value:"late"}]}),error=>{if(error instanceof KvMutationError) late=error; return denied(503)(error);});
      native.readOutage=false;
      assert.equal((await new KvNativeEngine(registry,native).resolve(actor,late!.operationId)).outcome,"committed");
    });
    await t.test("audit failure blocks native writes; post-commit failure retains a resolvable native marker", async () => {
      await db.$executeRawUnsafe("CREATE TRIGGER deny_audit BEFORE INSERT ON kv_audit BEGIN SELECT RAISE(ABORT, 'synthetic audit unavailable'); END");
      const before=native.writes;
      await assert.rejects(engine.change(actor,registered.id,{...(await input()),fields:[]}),denied(503)); assert.equal(native.writes,before);
      await assert.rejects(engine.read(actor,registered.id),denied(503));
      const flat=new SecretStore(native,["apps"],flatSecretGuard(registry,native,async()=>actor));
      await assert.rejects(flat.read({namespace:"apps",name:"imported",key:"constructor"}),denied(503));
      const legacy=new SecretStore(native,["apps"],flatSecretGuard(registry,native,async()=>null,aliases[2].alias));
      await assert.rejects(legacy.read(aliases[2]),denied(503));assert.equal(native.writes,before);
      await db.$executeRawUnsafe("DROP TRIGGER deny_audit");
      native.afterReplace=async()=>{await db.$executeRawUnsafe("CREATE TRIGGER deny_audit BEFORE INSERT ON kv_audit BEGIN SELECT RAISE(ABORT, 'synthetic audit unavailable'); END");};
      let pending:KvMutationError|undefined;
      await assert.rejects(engine.change(actor,registered.id,{...(await input()),fields:[]}),error=>{if(error instanceof KvMutationError) pending=error; return denied(503)(error);});
      assert.equal(pending!.outcome,"recovery-required"); native.afterReplace=undefined;
      await db.$executeRawUnsafe("DROP TRIGGER deny_audit");
      assert.equal((await new KvNativeEngine(registry,native).resolve(actor,pending!.operationId)).outcome,"committed");
    });
    await t.test("concurrent retention metadata changes refuse canonical CAS and retain candidate history for recovery", async()=>{
      const original=await engine.status(actor,registered.id),p=await registry.path(registered.id),histories=(await native.list("history")).length;
      native.afterCreate=async()=>{await registry.changeRetention(actor,p.id,p.revision,p.retention+1);};
      try {await assert.rejects(engine.change(actor,registered.id,{resourceVersion:original.resourceVersion,expectedHead:original.head,fields:[]}),denied(409));}
      finally {native.afterCreate=undefined;}
      const current=await engine.status(actor,registered.id);assert.equal(current.head,original.head);assert.equal(current.resourceVersion,original.resourceVersion);
      assert.equal((await native.list("history")).length,histories+1);
    });
    await t.test("tombstone retains object/unrelated values; retention is bounded without deleting last copies", async()=>{
      const path=await registry.path(registered.id); await registry.changeRetention(actor,path.id,path.revision,2);
      const result=await engine.change(actor,registered.id,await input(),"delete"); assert.equal(result.tombstone,true);
      const canonical=await native.read("apps","imported"); assert.deepEqual(Object.keys(canonical.data!),["unrelated"]);
      assert.equal((await engine.versions(actor,registered.id)).items.length,2); assert((await native.list("history")).length>2);
      assert.equal((await engine.read(actor,registered.id)).fields.length,0);
      await assert.rejects(engine.read(actor,registered.id,1),denied(404));
    });
    await t.test("new creation establishes an owned source UID, keeps empty documents and refuses imported collisions",async()=>{
      const p=await registry.registerPath(actor,{mountId:mount.id,path:"new/empty",namespace:"apps",name:"created",fields:[{field:"__proto__",key:"__proto__"}]});
      const result=await engine.create(actor,p.id,{resourceVersion:"absent",expectedHead:0,fields:[]}); assert.equal(result.head,1);
      const s=await native.read("apps","created"); assert.deepEqual(s.data,{}); assert(s.metadata!.annotations![CREATED_ANNOTATION]);
      assert.equal((await engine.read(actor,p.id)).fields.length,0);
      const collision=await registry.registerPath(actor,{mountId:mount.id,path:"new/collision",namespace:"apps",name:"collision",fields:[{field:"key",key:"key"}]});
      native.seed("apps","collision",{});
      await assert.rejects(engine.create(actor,collision.id,{resourceVersion:"absent",expectedHead:0,fields:[]}),denied(409));
    });
    await t.test("binary encoding, typed/immutable constraints and forged metadata fail without value leakage",async()=>{
      const path=await registry.path(registered.id);
      for(const fields of [[{field:"constructor",encoding:"base64",value:"bad="}],[{field:"constructor",encoding:"utf8",value:"\ud800"}],[{field:"unrelated",encoding:"base64",value:other}]]) assert.throws(()=>encodedValues(fields,path),denied(400));
      assert.throws(()=>encodedValues([{field:"constructor",encoding:"utf8",value:"x".repeat(256*1024+1)}],path),denied(413));
      const typed=await registry.registerPath(actor,{mountId:mount.id,path:"typed/docker",namespace:"apps",name:"typed",fields:[{field:"credentials",key:".dockerconfigjson"}]});
      const original=Buffer.from('{"auths":{}}').toString("base64");
      native.seed("apps","typed",{".dockerconfigjson":original},{type:"kubernetes.io/dockerconfigjson"});
      const typedStatus=await engine.status(actor,typed.id);
      await engine.adopt(actor,typed.id,{resourceVersion:typedStatus.resourceVersion,expectedHead:0,legacyAliases:[]});
      const typedHead=await engine.status(actor,typed.id);
      await assert.rejects(engine.change(actor,typed.id,{resourceVersion:typedHead.resourceVersion,expectedHead:typedHead.head},"delete"),denied(400));
      assert.equal((await engine.status(actor,typed.id)).head,1); assert.equal((await native.read("apps","typed")).data![".dockerconfigjson"],original);
      const s=await native.read("apps","imported"),state=parseState(s);
      (state.paths[0] as any).privateValue=marker;
      assert.throws(()=>parseState(stateBody(s,state,path)),denied(503));
      const history=(await native.list("history"))[0],ref={version:1,name:history.metadata!.name!,uid:history.metadata!.uid!,operationId:JSON.parse(history.metadata!.annotations![HISTORY_ANNOTATION]).operationId,createdAt:new Date().toISOString(),tombstone:false};
      assert.throws(()=>historyValues({...history,data:{...history.data,unrelated:other}},path,s.metadata!.uid!,ref),denied(409));
      const canonical=native.objects.get("apps/imported")!; canonical.immutable=true;
      await assert.rejects(engine.change(actor,registered.id,{...(await input()),fields:[]}),denied(409)); canonical.immutable=false;
      const own=JSON.parse(canonical.metadata!.annotations![STATE_ANNOTATION]); own.paths[0].sourceUid="replaced-source"; canonical.metadata!.annotations![STATE_ANNOTATION]=JSON.stringify(own);
      await assert.rejects(engine.read(actor,registered.id),denied(409));
      delete canonical.metadata!.annotations![STATE_ANNOTATION];
      const flat=new SecretStore(native,["apps"],flatSecretGuard(registry,native,async()=>actor));
      await assert.rejects(flat.read({namespace:"apps",name:"imported",key:"constructor"}),denied(409));
      await assert.rejects(engine.adoptionPreview(actor,registered.id),denied(409));
      native.objects.delete("apps/imported"); const before=native.writes;
      await assert.rejects(engine.create(actor,registered.id,{resourceVersion:"absent",expectedHead:0,fields:[]}),denied(409)); assert.equal(native.writes,before);
      assert(!JSON.stringify(await db.kvOperation.findMany()).includes(marker));
    });
  } finally {
    if(previousRegistration===undefined) delete process.env.ALLOW_REGISTRATION; else process.env.ALLOW_REGISTRATION=previousRegistration;
    await db.$disconnect(); await rm(dir,{recursive:true,force:true});
  }
});
