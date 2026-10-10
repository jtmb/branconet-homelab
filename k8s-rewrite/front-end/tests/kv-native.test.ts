import { test } from "node:test";
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
import { CREATED_ANNOTATION, HISTORY_ANNOTATION, STATE_ANNOTATION, encodedValues, exportFields, historyValues, parseState, stateBody } from "../src/lib/kv-native-state";

const marker = "synthetic-private-other-key";
const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const denied = (status: number) => (error: unknown) => error instanceof KvError && error.status === status;
class NativeFixture implements NativeSecretTransport {
  objects = new Map<string,V1Secret>(); counter = 0; reads = 0; writes = 0;
  replaceMode = "normal"; readOutage = false; createTimeout = false;
  afterReplace?: () => Promise<void>;
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
  async create(ns: string, body: V1Secret) {
    this.writes++;
    if (this.objects.has(this.key(ns,body.metadata!.name!))) throw { code: 409 };
    const result = this.seed(ns, body.metadata!.name!, body.data || {}, body);
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
    return copy(result);
  }
  async delete(ns: string, name: string, uid: string, resourceVersion: string) {
    const current = this.objects.get(this.key(ns,name));
    if (!current) throw { code: 404 };
    if (current.metadata?.uid !== uid || current.metadata.resourceVersion !== resourceVersion) throw { code: 409 };
    this.objects.delete(this.key(ns,name));
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
    const registry = new KvRegistry(db, ["apps","history"], kvConfig({ BORTUS_HISTORY_NAMESPACE:"history", BORTUS_KV_GUARDED_ADOPTION:"true" }));
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
      await db.$executeRawUnsafe("DROP TRIGGER deny_audit");
      native.afterReplace=async()=>{await db.$executeRawUnsafe("CREATE TRIGGER deny_audit BEFORE INSERT ON kv_audit BEGIN SELECT RAISE(ABORT, 'synthetic audit unavailable'); END");};
      let pending:KvMutationError|undefined;
      await assert.rejects(engine.change(actor,registered.id,{...(await input()),fields:[]}),error=>{if(error instanceof KvMutationError) pending=error; return denied(503)(error);});
      assert.equal(pending!.outcome,"recovery-required"); native.afterReplace=undefined;
      await db.$executeRawUnsafe("DROP TRIGGER deny_audit");
      assert.equal((await new KvNativeEngine(registry,native).resolve(actor,pending!.operationId)).outcome,"committed");
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
      assert(!JSON.stringify(await db.kvOperation.findMany()).includes(marker));
    });
  } finally {
    if(previousRegistration===undefined) delete process.env.ALLOW_REGISTRATION; else process.env.ALLOW_REGISTRATION=previousRegistration;
    await db.$disconnect(); await rm(dir,{recursive:true,force:true});
  }
});
