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
function fixture(c: Row) {
  let account: Row | null = user(c.role, c.admin), credential: Row | null = identity();
  let ownerRules = [grant()], tokenRules = [grant()], metadata = path();
  const reads = { owner: 0, token: 0, joint: 0, account: 0, identity: 0, path: 0 };
  let release!: () => void, entered!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const pending = new Promise<void>(resolve => { entered = resolve; });
  const failures = new Set<string>(), queries: Row[] = [];
  const snapshot = () => {
    for (const k of ["owner", "token"]) if (failures.has(k)) throw new Error("PUBLIC " + k + " UNAVAILABLE");
    return [...ownerRules.map(r => ({...r, principal: "user:" + actor.id})), ...tokenRules.map(r => ({...r, principal: "identity:" + tokenActor.identityId}))];
  };
  const pause = async () => { entered(); await gate; };
  const db = {
    $queryRaw: async (strings: TemplateStringsArray, ...values: unknown[]) => {
      assert.equal(strings.join("?").replace(/\s+/g, " ").trim(), "SELECT u.\"id\", u.\"sessionVersion\", u.\"role\", i.\"id\" AS \"identityId\", i.\"ownerId\", i.\"ownerSessionVersion\", i.\"revokedAt\", i.\"expiresAt\" FROM \"users\" AS u LEFT JOIN \"kv_identities\" AS i ON i.\"id\" = ? WHERE u.\"id\" = ? LIMIT 1");
      assert.deepEqual(plain(values), [tokenActor.identityId, actor.id]);
      reads.account++; reads.identity++;
      if (c.phase === "account") await pause();
      return account ? [{ id: account.id, sessionVersion: account.sessionVersion, role: account.role,
        identityId: credential?.id ?? null, ownerId: credential?.ownerId ?? null,
        ownerSessionVersion: credential?.ownerSessionVersion ?? null, revokedAt: credential?.revokedAt ?? null,
        expiresAt: credential?.expiresAt ?? null }] : [];
    },
    user: { findUnique: async () => { reads.account++; if (c.phase === "account" && reads.account === 2) await pause(); return account && {...account}; } },
    kvIdentity: { findUnique: async () => { reads.identity++; return credential && {...credential}; } },
    kvPolicy: { findMany: async (query: Row) => {
      queries.push(plain(query));
      if (typeof query.where.principal === "object") {
        reads.joint++;
        assert.deepEqual(plain(query), {where:{principal:{in:["user:"+actor.id,"identity:"+tokenActor.identityId]}},take:513});
        if (c.phase === "after") { const captured = snapshot(); await pause(); return captured.slice(0, 513); }
        if (c.phase !== "account") await pause();
        return snapshot().slice(0, 513);
      }
      const kind = query.where.principal === "user:"+actor.id ? "owner" : "token";
      assert.deepEqual(plain(query), {where:{principal:kind === "owner" ? "user:"+actor.id : "identity:"+tokenActor.identityId},take:257});
      reads[kind]++;
      if (kind === "owner" && reads.owner === 2) {
        if (c.phase === "after") { const captured = ownerRules.map(r=>({...r})); await pause(); return captured; }
        if (c.phase !== "account") await pause();
      }
      if (failures.has(kind)) throw new Error("PUBLIC " + kind + " UNAVAILABLE");
      return (kind === "owner" ? ownerRules : tokenRules).slice(0,257).map(r=>({...r}));
    } },
    kvPath: { findUnique: async (query: Row) => { reads.path++; assert.deepEqual(plain(query), {where:{id:"public-path"},include:{fields:true,mount:true}}); return metadata; } },
    $transaction: forbidden,
  };
  const registry = new KvRegistry(db,["public-namespace"],{historyNamespace:"public-history",retention:20,maxRetention:100,guardedAdoption:false});
  return {reads,queries,pending,release,
    setRules:(k:string,v:Row[])=>{if(k === "owner")ownerRules=v;else tokenRules=v;},
    setUser:(v:Row|null)=>{account=v;},setIdentity:(v:Row|null)=>{credential=v;},
    setMetadata:(v:Row)=>{metadata=v;},fail:(k:string)=>failures.add(k),
    run:()=>route.GET(registry,c.automation === false ? actor : tokenActor,{}, {id:"public-path"})};
}
function changedRules(variant: string): Row[] {
  switch (variant) {
    case "removed": return [];
    case "readOnly": return [grant(null, "", "allow", ["read"])];
    case "wrongMount": return [grant("other-mount")];
    case "wrongPrefix": return [grant(null, "other")];
    case "lookalike": return [grant(null, "apps/ap")];
    case "globalDeny": return [grant(), grant(null, "", "deny", ["list"])];
    case "scopedDeny": return [grant(), grant("public-mount", "apps", "deny", ["list"])];
    case "actions": return [{ ...grant(), actions: '["unknown"]' }];
    case "effect": return [grant(null, "", "broken")];
    case "prefix": return [grant(null, "apps//api")];
    case "count": return Array.from({ length: 257 }, () => grant());
    default: throw new Error("Unknown public case");
  }
}
const cases: Row[] = [
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "removed",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "readOnly",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "wrongMount",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "wrongPrefix",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "lookalike",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "globalDeny",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "scopedDeny",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "actions",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "effect",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "prefix",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "count",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "owner",
    "variant": "outage",
    "baselineFail": false
  },
  {
    "kind": "prefix",
    "admin": false,
    "principal": "owner",
    "prefix": ""
  },
  {
    "kind": "prefix",
    "admin": false,
    "principal": "owner",
    "prefix": "apps"
  },
  {
    "kind": "prefix",
    "admin": false,
    "principal": "owner",
    "prefix": "apps/api"
  },
  {
    "kind": "restored",
    "admin": false,
    "principal": "owner",
    "phase": "before"
  },
  {
    "kind": "unrelatedDeny",
    "admin": false,
    "principal": "owner",
    "phase": "before"
  },
  {
    "kind": "afterSnapshot",
    "admin": false,
    "principal": "owner",
    "phase": "after"
  },
  {
    "kind": "maxPolicies",
    "admin": false,
    "principal": "owner",
    "phase": "before"
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "removed",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "readOnly",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "wrongMount",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "wrongPrefix",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "lookalike",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "globalDeny",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "scopedDeny",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "actions",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "effect",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "prefix",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "count",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": false,
    "principal": "token",
    "variant": "outage",
    "baselineFail": true
  },
  {
    "kind": "prefix",
    "admin": false,
    "principal": "token",
    "prefix": ""
  },
  {
    "kind": "prefix",
    "admin": false,
    "principal": "token",
    "prefix": "apps"
  },
  {
    "kind": "prefix",
    "admin": false,
    "principal": "token",
    "prefix": "apps/api"
  },
  {
    "kind": "restored",
    "admin": false,
    "principal": "token",
    "phase": "before"
  },
  {
    "kind": "unrelatedDeny",
    "admin": false,
    "principal": "token",
    "phase": "before"
  },
  {
    "kind": "afterSnapshot",
    "admin": false,
    "principal": "token",
    "phase": "after"
  },
  {
    "kind": "maxPolicies",
    "admin": false,
    "principal": "token",
    "phase": "before"
  },
  {
    "kind": "stable",
    "admin": false,
    "phase": "before"
  },
  {
    "kind": "capturedMetadata",
    "admin": false,
    "phase": "before"
  },
  {
    "kind": "bothMax",
    "admin": false,
    "phase": "before"
  },
  {
    "kind": "nonoverlap",
    "admin": false,
    "phase": "before"
  },
  {
    "kind": "finalMissing",
    "admin": false,
    "phase": "account"
  },
  {
    "kind": "finalSession",
    "admin": false,
    "phase": "account"
  },
  {
    "kind": "finalIdentity",
    "admin": false,
    "phase": "account"
  },
  {
    "kind": "finalExpired",
    "admin": false,
    "phase": "account"
  },
  {
    "kind": "finalDemotion",
    "admin": false,
    "phase": "account"
  },
  {
    "kind": "repromoted",
    "admin": false,
    "phase": "account"
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "removed",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "readOnly",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "wrongMount",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "wrongPrefix",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "lookalike",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "globalDeny",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "scopedDeny",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "actions",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "effect",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "prefix",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "count",
    "baselineFail": false
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "owner",
    "variant": "outage",
    "baselineFail": false
  },
  {
    "kind": "prefix",
    "admin": true,
    "principal": "owner",
    "prefix": ""
  },
  {
    "kind": "prefix",
    "admin": true,
    "principal": "owner",
    "prefix": "apps"
  },
  {
    "kind": "prefix",
    "admin": true,
    "principal": "owner",
    "prefix": "apps/api"
  },
  {
    "kind": "restored",
    "admin": true,
    "principal": "owner",
    "phase": "before"
  },
  {
    "kind": "unrelatedDeny",
    "admin": true,
    "principal": "owner",
    "phase": "before"
  },
  {
    "kind": "afterSnapshot",
    "admin": true,
    "principal": "owner",
    "phase": "after"
  },
  {
    "kind": "maxPolicies",
    "admin": true,
    "principal": "owner",
    "phase": "before"
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "removed",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "readOnly",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "wrongMount",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "wrongPrefix",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "lookalike",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "globalDeny",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "scopedDeny",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "actions",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "effect",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "prefix",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "count",
    "baselineFail": true
  },
  {
    "kind": "withdraw",
    "admin": true,
    "principal": "token",
    "variant": "outage",
    "baselineFail": true
  },
  {
    "kind": "prefix",
    "admin": true,
    "principal": "token",
    "prefix": ""
  },
  {
    "kind": "prefix",
    "admin": true,
    "principal": "token",
    "prefix": "apps"
  },
  {
    "kind": "prefix",
    "admin": true,
    "principal": "token",
    "prefix": "apps/api"
  },
  {
    "kind": "restored",
    "admin": true,
    "principal": "token",
    "phase": "before"
  },
  {
    "kind": "unrelatedDeny",
    "admin": true,
    "principal": "token",
    "phase": "before"
  },
  {
    "kind": "afterSnapshot",
    "admin": true,
    "principal": "token",
    "phase": "after"
  },
  {
    "kind": "maxPolicies",
    "admin": true,
    "principal": "token",
    "phase": "before"
  },
  {
    "kind": "stable",
    "admin": true,
    "phase": "before"
  },
  {
    "kind": "capturedMetadata",
    "admin": true,
    "phase": "before"
  },
  {
    "kind": "bothMax",
    "admin": true,
    "phase": "before"
  },
  {
    "kind": "nonoverlap",
    "admin": true,
    "phase": "before"
  },
  {
    "kind": "finalMissing",
    "admin": true,
    "phase": "account"
  },
  {
    "kind": "finalSession",
    "admin": true,
    "phase": "account"
  },
  {
    "kind": "finalIdentity",
    "admin": true,
    "phase": "account"
  },
  {
    "kind": "finalExpired",
    "admin": true,
    "phase": "account"
  },
  {
    "kind": "finalDemotion",
    "admin": true,
    "phase": "account"
  },
  {
    "kind": "repromoted",
    "admin": true,
    "phase": "account"
  }
];
for (const [index,c] of cases.entries()) test("public selected-path policy snapshot " + index + " " + JSON.stringify(c),async()=>{
  const f=fixture(c), outcome:Promise<Row>=f.run().then((value:Row)=>({value,error:null}),(error:unknown)=>({value:null,error}));
  await f.pending; let status:number|undefined,outage=false;
  if(c.kind === "withdraw") {
    if(c.variant === "outage"){f.fail(c.principal);outage=true;}
    else{f.setRules(c.principal,changedRules(c.variant));status=["actions","effect","prefix","count"].includes(c.variant)?503:403;}
  }
  if(c.kind === "prefix")f.setRules(c.principal,[grant("public-mount",c.prefix)]);
  if(c.kind === "restored"){f.setRules(c.principal,[]);f.setRules(c.principal,[grant()]);}
  if(c.kind === "unrelatedDeny")f.setRules(c.principal,[grant(),grant("other-mount","","deny",["list"]),grant(null,"apps","deny",["read"])]);
  if(c.kind === "afterSnapshot")f.setRules(c.principal,[]);
  if(c.kind === "maxPolicies")f.setRules(c.principal,Array.from({length:256},()=>grant()));
  if(c.kind === "bothMax")for(const k of ["owner","token"])f.setRules(k,Array.from({length:256},()=>grant()));
  if(c.kind === "nonoverlap"){f.setRules("owner",[grant("public-mount","other")]);f.setRules("token",[grant("other-mount","apps")]);status=403;}
  if(c.kind === "capturedMetadata")f.setMetadata({...path(),id:"changed",revision:88,fields:[]});
  if(c.kind === "finalMissing"){f.setUser(null);status=401;}
  if(c.kind === "finalSession"){f.setUser({...user(),sessionVersion:8});status=401;}
  if(c.kind === "finalIdentity"){f.setIdentity({...identity(),revokedAt:new Date(0)});status=401;}
  if(c.kind === "finalExpired"){f.setIdentity({...identity(),expiresAt:new Date(0)});status=401;}
  if(c.kind === "finalDemotion" || c.kind === "repromoted"){f.setUser(user("readonly"));status=401;}
  f.release();const result=await outcome;
  if(outage){assert.equal(result.value,null);assert.match(result.error?.message||"",/PUBLIC .* UNAVAILABLE/);}
  else if(status){assert.equal(result.value,null);assert(denied(status)(result.error));}
  else{assert.equal(result.error,null);assert.deepEqual(plain(result.value),expected());}
  assert.equal(f.reads.path,1);
  // Both finite source variants are measured; behavioral expectations above never depend on variant.
  assert([0,1].includes(f.reads.joint));
  assert.equal(f.reads.owner,f.reads.joint ? 1 : 2);assert.equal(f.reads.token,1);
  assert.equal(f.queries.length,f.reads.joint ? 3 : 3);
  if(c.kind === "repromoted"){
    f.setUser(user("write",c.admin));assert.deepEqual(plain(await f.run()),expected());
    assert.equal(user().sessionVersion,7);assert.equal(identity().revokedAt,null);
  }
});
