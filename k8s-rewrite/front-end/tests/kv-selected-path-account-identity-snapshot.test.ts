import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// PUBLIC source controls of the actual selected-path GET callback and registry.
// kvHuman is an inert callback adapter: no HTTP, ORM, server or native execution.
// Automation exercises the lower-level authorization model, not an HTTP route.
type Row = Record<string, any>;
const actor = { id: "public-owner", sessionVersion: 7 };
const tokenActor = { ...actor, identityId: "public-identity" };
const user = (role = "write", engineAdmin = false): Row => ({ ...actor, role, engineAdmin });
const identity = (): Row => ({ id: tokenActor.identityId, ownerId: actor.id, ownerSessionVersion: 7,
  revokedAt: null, expiresAt: new Date("2099-01-01T00:00:00Z") });
const plain = (v: unknown): any => JSON.parse(JSON.stringify(v));
const forbidden = () => { throw new Error("Outside public selected-path controls"); };
class SecretError extends Error { constructor(readonly status: number, message: string) { super(message); } }
function evaluate(file: string, dependencies: Row) {
  const m = { exports: {} as any };
  const output = ts.transpileModule(readFileSync(file, "utf8"), { fileName: file, compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
  runInNewContext(output, { module: m, exports: m.exports,
    require: (name: string) => { assert(Object.hasOwn(dependencies, name), `Unselected dependency: ${name}`); return dependencies[name]; },
    Buffer, Date, JSON, process: { env: {} },
  }, { filename: file, timeout: 5000 });
  return m.exports;
}
const cluster = { SecretError, validateTarget: ({ namespace, name, key }: Row) => {
  assert(["public-namespace", "other-namespace"].includes(namespace)); assert.equal(name, "validation" === name ? "validation" : "public-secret");
  assert(["validation", "public_key", "second_key"].includes(key));
} };
const contract = evaluate("src/lib/kv-contract.ts", { "./cluster-secrets": cluster });
const revisions = evaluate("src/lib/kv-identity-revision.ts", { "node:crypto": { createHash }, "./kv-contract": contract });
const { KvRegistry } = evaluate("src/lib/kv-registry.ts", {
  "./kv-contract": contract, "./cluster-secrets": cluster, "./kv-identity-revision": revisions,
  "./kv-credentials": { issueCredential: forbidden, hashMatches: forbidden, presentedCredential: forbidden },
  "./kv-legacy-access": Object.fromEntries(["acknowledgeLegacyImpact", "legacyImpact", "legacyImpactPage", "readLegacyAliases"].map(n => [n, forbidden])),
});
const route = evaluate("src/app/api/kv/paths/[id]/route.ts", {
  "@/lib/kv-http": { kvHuman: (callback: unknown) => callback, kvBody: forbidden },
  "@/lib/kv-schemas": { pathUpdate: {} }, "@/lib/kv-contract": contract,
});
assert.equal(route.runtime, "nodejs");
const actions = ["list", "read", "create", "update", "delete", "rollback", "reconcile", "destroy", "export", "rotate"];
const grant = (mountId: string | null = null, prefix = "", effect = "allow", allowed = actions): Row => ({ mountId, prefix, effect, actions: JSON.stringify(allowed) });
const path = (): Row => ({ id: "public-path", mountId: "public-mount", path: "apps/api", namespace: "public-namespace",
  name: "public-secret", retention: 20, revision: 17, createdAt: "public-created-at",
  fields: [{ field: "public_field", key: "public_key", namespace: "public-namespace", name: "public-secret" },
    { field: "second_field", key: "second_key", namespace: "public-namespace", name: "public-secret" }],
  mount: { namespaces: '["public-namespace"]' } });
const expected = () => { const p = path(); return { id: p.id, mountId: p.mountId, path: p.path, namespace: p.namespace, name: p.name,
  retention: p.retention, revision: p.revision, createdAt: p.createdAt, fields: p.fields.map(({ field, key }: Row) => ({ field, key })) }; };
const denied = (status: number) => (e: any) => e instanceof contract.KvError && e.status === status;
// These fixtures model a single SQL statement; they do not execute SQL/ORM/HTTP.
const snapshotSQL = 'SELECT u."id", u."sessionVersion", u."role", i."id" AS "identityId", i."ownerId", i."ownerSessionVersion", i."revokedAt", i."expiresAt" FROM "users" AS u LEFT JOIN "kv_identities" AS i ON i."id" = ? WHERE u."id" = ? LIMIT 1';
function fixture(c: Row) {
  let account: Row|null=user(c.human ? c.role : "write",c.admin), credential: Row|null=identity(), metadata=path();
  const reads={account:0,identity:0,snapshot:0,policy:0,path:0};let fail=false;
  let release!:()=>void,entered!:()=>void;
  const gate=new Promise<void>(r=>{release=r;}),pending=new Promise<void>(r=>{entered=r;});
  const pause=async()=>{entered();await gate;};
  const capture=()=>account ? [{id:account.id,sessionVersion:account.sessionVersion,role:account.role,
    identityId:credential?.id??null,ownerId:credential?.ownerId??null,ownerSessionVersion:credential?.ownerSessionVersion??null,
    revokedAt:credential?.revokedAt??null,expiresAt:credential?.expiresAt??null}] : [];
  const db={
    user:{findUnique:async(q:Row)=>{assert.deepEqual(plain(q),{where:{id:actor.id}});reads.account++;
      if(c.human && reads.account===2)await pause();return account&&{...account};}},
    kvIdentity:{findUnique:async(q:Row)=>{assert.deepEqual(plain(q),{where:{id:tokenActor.identityId}});reads.identity++;
      if(reads.identity===2){if(c.phase==="after"){const r=credential&&{...credential};await pause();if(fail)throw Error("PUBLIC AUTHORITY UNAVAILABLE");return r;}await pause();}
      if(fail)throw Error("PUBLIC AUTHORITY UNAVAILABLE");return credential&&{...credential};}},
    $queryRaw:async(strings:TemplateStringsArray,...values:unknown[])=>{
      reads.snapshot++;assert.equal(strings.join("?").replace(/\s+/g," ").trim(),snapshotSQL);
      assert.deepEqual(plain(values),[tokenActor.identityId,actor.id]);
      if(c.phase==="after"){const r=capture();await pause();if(fail)throw Error("PUBLIC AUTHORITY UNAVAILABLE");return r;}
      await pause();if(fail)throw Error("PUBLIC AUTHORITY UNAVAILABLE");return capture();},
    kvPolicy:{findMany:async(q:Row)=>{reads.policy++;
      if(typeof q.where.principal==="object"){
        assert.deepEqual(plain(q),{where:{principal:{in:["user:"+actor.id,"identity:"+tokenActor.identityId]}},take:513});
        return [{...grant(),principal:"user:"+actor.id},{...grant(),principal:"identity:"+tokenActor.identityId}];}
      assert.deepEqual(plain(q),{where:{principal:q.where.principal},take:257});
      assert(["user:"+actor.id,"identity:"+tokenActor.identityId].includes(q.where.principal));return [grant()];}},
    kvPath:{findUnique:async(q:Row)=>{reads.path++;assert.deepEqual(plain(q),{where:{id:"public-path"},include:{fields:true,mount:true}});return metadata;}},
    $transaction:forbidden,
  };
  const registry=new KvRegistry(db,["public-namespace"],{historyNamespace:"public-history",retention:20,maxRetention:100,guardedAdoption:false});
  return {reads,pending,release,run:()=>route.GET(registry,c.human?actor:tokenActor,{}, {id:"public-path"}),
    change:(kind:string)=>{
      if(kind==="missing")account=null;
      if(kind==="session")account={...account,sessionVersion:8};
      if(kind==="demoted")account={...account,role:"readonly"};
      if(kind==="identityMissing")credential=null;
      if(kind==="owner")credential={...credential,ownerId:"other-owner"};
      if(kind==="ownerSession")credential={...credential,ownerSessionVersion:8};
      if(kind==="revoked")credential={...credential,revokedAt:new Date(0)};
      if(kind==="expired")credential={...credential,expiresAt:new Date(0)};
      if(kind==="expiryBoundary")credential={...credential,expiresAt:new Date()};
      if(kind==="restored"){account={...account,role:"readonly"};account={...account,role:"write"};}
      if(kind==="captured")metadata={...path(),id:"replacement",revision:88,fields:[]};
      if(kind==="unrelated")account={...account,username:"changed-public-name",engineAdmin:!c.admin};
      if(kind==="outage")fail=true;
    }, restore:()=>{account=user("write",c.admin);credential=identity();}};
}
const cases: Row[] = [
  {
    "admin": false,
    "kind": "missing",
    "phase": "before",
    "baselineFail": true
  },
  {
    "admin": false,
    "kind": "session",
    "phase": "before",
    "baselineFail": true
  },
  {
    "admin": false,
    "kind": "demoted",
    "phase": "before",
    "baselineFail": true
  },
  {
    "admin": false,
    "kind": "identityMissing",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": false,
    "kind": "owner",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": false,
    "kind": "ownerSession",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": false,
    "kind": "revoked",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": false,
    "kind": "expired",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": false,
    "kind": "expiryBoundary",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": false,
    "kind": "stable",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": false,
    "kind": "restored",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": false,
    "kind": "captured",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": false,
    "kind": "unrelated",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": false,
    "kind": "outage",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": false,
    "kind": "missing",
    "phase": "after"
  },
  {
    "admin": false,
    "kind": "session",
    "phase": "after"
  },
  {
    "admin": false,
    "kind": "demoted",
    "phase": "after"
  },
  {
    "admin": false,
    "kind": "identityMissing",
    "phase": "after"
  },
  {
    "admin": false,
    "kind": "owner",
    "phase": "after"
  },
  {
    "admin": false,
    "kind": "ownerSession",
    "phase": "after"
  },
  {
    "admin": false,
    "kind": "revoked",
    "phase": "after"
  },
  {
    "admin": false,
    "kind": "stable",
    "phase": "after"
  },
  {
    "admin": false,
    "kind": "captured",
    "phase": "after"
  },
  {
    "admin": false,
    "kind": "missing",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": false,
    "kind": "session",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": false,
    "kind": "demoted",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": false,
    "kind": "stable",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": false,
    "kind": "captured",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": false,
    "kind": "unrelated",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": false,
    "kind": "missing",
    "phase": "human",
    "human": true,
    "role": "write"
  },
  {
    "admin": false,
    "kind": "session",
    "phase": "human",
    "human": true,
    "role": "write"
  },
  {
    "admin": false,
    "kind": "demoted",
    "phase": "human",
    "human": true,
    "role": "write"
  },
  {
    "admin": false,
    "kind": "stable",
    "phase": "human",
    "human": true,
    "role": "write"
  },
  {
    "admin": false,
    "kind": "captured",
    "phase": "human",
    "human": true,
    "role": "write"
  },
  {
    "admin": false,
    "kind": "unrelated",
    "phase": "human",
    "human": true,
    "role": "write"
  },
  {
    "admin": true,
    "kind": "missing",
    "phase": "before",
    "baselineFail": true
  },
  {
    "admin": true,
    "kind": "session",
    "phase": "before",
    "baselineFail": true
  },
  {
    "admin": true,
    "kind": "demoted",
    "phase": "before",
    "baselineFail": true
  },
  {
    "admin": true,
    "kind": "identityMissing",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": true,
    "kind": "owner",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": true,
    "kind": "ownerSession",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": true,
    "kind": "revoked",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": true,
    "kind": "expired",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": true,
    "kind": "expiryBoundary",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": true,
    "kind": "stable",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": true,
    "kind": "restored",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": true,
    "kind": "captured",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": true,
    "kind": "unrelated",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": true,
    "kind": "outage",
    "phase": "before",
    "baselineFail": false
  },
  {
    "admin": true,
    "kind": "missing",
    "phase": "after"
  },
  {
    "admin": true,
    "kind": "session",
    "phase": "after"
  },
  {
    "admin": true,
    "kind": "demoted",
    "phase": "after"
  },
  {
    "admin": true,
    "kind": "identityMissing",
    "phase": "after"
  },
  {
    "admin": true,
    "kind": "owner",
    "phase": "after"
  },
  {
    "admin": true,
    "kind": "ownerSession",
    "phase": "after"
  },
  {
    "admin": true,
    "kind": "revoked",
    "phase": "after"
  },
  {
    "admin": true,
    "kind": "stable",
    "phase": "after"
  },
  {
    "admin": true,
    "kind": "captured",
    "phase": "after"
  },
  {
    "admin": true,
    "kind": "missing",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": true,
    "kind": "session",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": true,
    "kind": "demoted",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": true,
    "kind": "stable",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": true,
    "kind": "captured",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": true,
    "kind": "unrelated",
    "phase": "human",
    "human": true,
    "role": "readonly"
  },
  {
    "admin": true,
    "kind": "missing",
    "phase": "human",
    "human": true,
    "role": "write"
  },
  {
    "admin": true,
    "kind": "session",
    "phase": "human",
    "human": true,
    "role": "write"
  },
  {
    "admin": true,
    "kind": "demoted",
    "phase": "human",
    "human": true,
    "role": "write"
  },
  {
    "admin": true,
    "kind": "stable",
    "phase": "human",
    "human": true,
    "role": "write"
  },
  {
    "admin": true,
    "kind": "captured",
    "phase": "human",
    "human": true,
    "role": "write"
  },
  {
    "admin": true,
    "kind": "unrelated",
    "phase": "human",
    "human": true,
    "role": "write"
  }
];
for(const [n,c] of cases.entries()) test("public selected-path account identity snapshot "+n+" "+JSON.stringify(c),async()=>{
  const f=fixture(c),outcome:Promise<Row>=f.run().then((value:Row)=>({value,error:null}),(error:unknown)=>({value:null,error}));
  await f.pending;f.change(c.kind);f.release();const r=await outcome;
  const invalid=c.human ? ["missing","session"].includes(c.kind) : c.phase==="before" && ["missing","session","demoted","identityMissing","owner","ownerSession","revoked","expired","expiryBoundary"].includes(c.kind);
  if(c.kind==="outage"){assert.equal(r.value,null);assert.match(r.error?.message||"",/PUBLIC AUTHORITY UNAVAILABLE/);}
  else if(invalid){assert.equal(r.value,null);assert(denied(401)(r.error));}
  else {assert.equal(r.error,null);assert.deepEqual(plain(r.value),expected());}
  assert.equal(f.reads.path,1);assert.equal(f.reads.policy,c.human?1:3);
  assert.equal(f.reads.account,c.human?2:f.reads.snapshot?1:2);assert.equal(f.reads.identity,c.human?0:f.reads.snapshot?1:2);
  assert.equal(f.reads.snapshot,c.human?0:f.reads.snapshot?1:0);
  if(c.kind==="demoted" && c.phase==="before"){
    f.restore();assert.deepEqual(plain(await f.run()),expected());
    assert.equal(user().sessionVersion,7);assert.equal(identity().revokedAt,null);
  }
});
