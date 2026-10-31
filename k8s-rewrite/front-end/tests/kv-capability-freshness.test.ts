import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// PUBLIC source controls: real registry/current/policy parser with held metadata
// doubles only. No ORM, server, network, native values, credentials or recovery.
type Row = Record<string, any>;
const actor = { id: "public-owner", sessionVersion: 7 };
const automation = { ...actor, identityId: "public-identity" };
const user = (role = "write", engineAdmin = false): Row => ({ ...actor, role, engineAdmin });
const identity = (): Row => ({ id: automation.identityId, ownerId: actor.id, ownerSessionVersion: 7,
  revokedAt: null, expiresAt: new Date("2099-01-01T00:00:00Z") });
const plain = (v: unknown): any => JSON.parse(JSON.stringify(v));
const forbidden = () => { throw new Error("Outside public capability controls"); };
class SecretError extends Error { constructor(readonly status: number, message: string) { super(message); } }
function evaluate(file: string, dependencies: Row) {
  const compiledModule = { exports: {} as any };
  const output = ts.transpileModule(readFileSync(file, "utf8"), { fileName: file, compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
  runInNewContext(output, { module: compiledModule, exports: compiledModule.exports,
    require: (name: string) => { assert(Object.hasOwn(dependencies, name), `Unselected dependency: ${name}`); return dependencies[name]; },
    Buffer, Date, JSON, process: { env: {} },
  }, { filename: file, timeout: 5000 });
  return compiledModule.exports;
}
const cluster = { SecretError, validateTarget: ({ namespace, name, key }: Row) => {
  assert.equal(namespace, "public-namespace"); assert.equal(name, "validation" === name ? "validation" : "public-secret");
  assert(["validation", "public_key"].includes(key));
} };
const contract = evaluate("src/lib/kv-contract.ts", { "./cluster-secrets": cluster });
const revisions = evaluate("src/lib/kv-identity-revision.ts", { "node:crypto": { createHash }, "./kv-contract": contract });
const { KvRegistry } = evaluate("src/lib/kv-registry.ts", {
  "./kv-contract": contract, "./cluster-secrets": cluster, "./kv-identity-revision": revisions,
  "./kv-credentials": { issueCredential: forbidden, hashMatches: forbidden, presentedCredential: forbidden },
  "./kv-legacy-access": Object.fromEntries(["acknowledgeLegacyImpact", "legacyImpact", "legacyImpactPage", "readLegacyAliases"].map(n => [n, forbidden])),
});
const actions = ["list", "read", "create", "update", "delete", "rollback", "reconcile", "destroy", "export", "rotate"];
assert.deepEqual(plain(contract.KV_ACTIONS), actions);
const grant = (mountId: string | null = null, prefix = "", effect = "allow", allowed = actions): Row => ({ mountId, prefix, effect, actions: JSON.stringify(allowed) });
const path = (): Row => ({ id: "public-path", mountId: "public-mount", path: "apps/api", namespace: "public-namespace", name: "public-secret",
  revision: 17, retention: 20, fields: [{ field: "public-field", key: "public_key", namespace: "public-namespace", name: "public-secret" }],
  mount: { namespaces: '["public-namespace"]' } });
const denied = (status: number) => (e: any) => e instanceof contract.KvError && e.status === status;
function fixture(c: Row) {
  let account: Row | null = user(c.role, c.admin), credential: Row | null = identity();
  let ownerRules: Row[] = [grant()], tokenRules: Row[] = [grant()], metadata = path();
  const who = c.automation ? automation : actor;
  const phase = c.phase || (c.principal === "token" ? "tokenFresh" : "ownerFresh");
  const reads = { owner: 0, token: 0, account: 0, identity: 0, path: 0 };
  const failures = new Set<string>(), queries: Row[] = [];
  let release!: () => void, entered!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const pending = new Promise<void>(resolve => { entered = resolve; });
  const hold = async (at: string) => { if (phase === at) { entered(); await gate; } if (failures.has(at)) throw new Error("PUBLIC " + at + " UNAVAILABLE"); };
  const db = {
    user: { findUnique: async ({ where }: Row) => { assert.deepEqual(plain(where), { id: actor.id }); reads.account++; return account && { ...account }; } },
    kvIdentity: { findUnique: async ({ where }: Row) => { assert.deepEqual(plain(where), { id: automation.identityId }); reads.identity++; return credential && { ...credential }; } },
    kvPolicy: { findMany: async (query: Row) => {
      const kind = query.where.principal === "user:" + actor.id ? "owner" : "token";
      assert.deepEqual(plain(query), { where: { principal: kind === "owner" ? "user:" + actor.id : "identity:" + automation.identityId }, take: 257 });
      reads[kind]++; await hold(kind + (reads[kind] === 1 ? "Initial" : "Fresh"));
      return (kind === "owner" ? ownerRules : tokenRules).map(rule => ({ ...rule }));
    } },
    kvPath: { findUnique: async (query: Row) => {
      reads.path++; queries.push(plain(query)); const captured = metadata; await hold("path"); return captured;
    } },
    $transaction: forbidden,
  };
  const registry = new KvRegistry(db, ["public-namespace"], { historyNamespace: "public-history", retention: 20, maxRetention: 100, guardedAdoption: !!c.guarded });
  return { registry, who, reads, queries, pending, release, phase, fail: () => failures.add(phase),
    setUser: (v: Row | null) => { account = v; }, setIdentity: (v: Row | null) => { credential = v; },
    setRules: (principal: string, v: Row[]) => { if (principal === "token") tokenRules = v; else ownerRules = v; },
    setMetadata: (v: Row) => { metadata = v; } };
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
function expected(c: Row, allowed = actions) {
  const permissions = { list: allowed.includes("list"), read: c.role !== "readonly" && allowed.includes("read"),
    create: c.role !== "readonly" && allowed.includes("create"), update: c.role !== "readonly" && allowed.includes("update"),
    delete: c.role !== "readonly" && allowed.includes("delete"), rollback: c.role !== "readonly" && allowed.includes("rollback"),
    reconcile: c.role !== "readonly" && allowed.includes("reconcile"), destroy: c.role !== "readonly" && allowed.includes("destroy"),
    export: c.role !== "readonly" && allowed.includes("export"), rotate: c.role !== "readonly" && allowed.includes("rotate") };
  return { pathId: "public-path", revision: 17, permissions, nativeMutationEnabled: !!c.guarded,
    initializationAllowed: !!c.guarded && !!c.admin && c.role !== "readonly" && !c.automation && allowed.includes("create"),
    supportedActions: ["list", "read", "create", "update", "delete", "rollback", "reconcile", "export", "destroy", "rotate"],
    guardVerification: "operator assertion; external admission/RBAC evidence required" };
}
const cases: Row[] = [
  {
    "kind": "stable",
    "role": "write",
    "admin": false,
    "guarded": false
  },
  {
    "kind": "stable",
    "role": "write",
    "admin": false,
    "guarded": true
  },
  {
    "kind": "stable",
    "role": "write",
    "admin": true,
    "guarded": false
  },
  {
    "kind": "stable",
    "role": "write",
    "admin": true,
    "guarded": true
  },
  {
    "kind": "stable",
    "role": "readonly",
    "admin": false,
    "guarded": false
  },
  {
    "kind": "stable",
    "role": "readonly",
    "admin": false,
    "guarded": true
  },
  {
    "kind": "stable",
    "role": "readonly",
    "admin": true,
    "guarded": false
  },
  {
    "kind": "stable",
    "role": "readonly",
    "admin": true,
    "guarded": true
  },
  {
    "kind": "stable",
    "automation": true,
    "guarded": false
  },
  {
    "kind": "stable",
    "automation": true,
    "guarded": true
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "removed",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "readOnly",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "wrongMount",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "wrongPrefix",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "lookalike",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "globalDeny",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "scopedDeny",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "removed",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "readOnly",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "wrongMount",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "wrongPrefix",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "lookalike",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "globalDeny",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "scopedDeny",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "removed",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "readOnly",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "wrongMount",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "wrongPrefix",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "lookalike",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "globalDeny",
    "baselineFail": true
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "scopedDeny",
    "baselineFail": true
  },
  {
    "kind": "account",
    "automation": false,
    "phase": "path",
    "variant": "missing"
  },
  {
    "kind": "account",
    "automation": false,
    "phase": "path",
    "variant": "session"
  },
  {
    "kind": "account",
    "automation": false,
    "phase": "ownerInitial",
    "variant": "missing"
  },
  {
    "kind": "account",
    "automation": false,
    "phase": "ownerInitial",
    "variant": "session"
  },
  {
    "kind": "account",
    "automation": false,
    "phase": "ownerFresh",
    "variant": "missing"
  },
  {
    "kind": "account",
    "automation": false,
    "phase": "ownerFresh",
    "variant": "session"
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "path",
    "variant": "missing"
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "path",
    "variant": "session"
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "ownerInitial",
    "variant": "missing"
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "ownerInitial",
    "variant": "session"
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "ownerFresh",
    "variant": "missing"
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "ownerFresh",
    "variant": "session"
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "tokenInitial",
    "variant": "missing"
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "tokenInitial",
    "variant": "session"
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "tokenFresh",
    "variant": "missing"
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "tokenFresh",
    "variant": "session"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "path",
    "variant": "missing"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "path",
    "variant": "owner"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "path",
    "variant": "session"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "path",
    "variant": "revoked"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "path",
    "variant": "expired"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "ownerInitial",
    "variant": "missing"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "ownerInitial",
    "variant": "owner"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "ownerInitial",
    "variant": "session"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "ownerInitial",
    "variant": "revoked"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "ownerInitial",
    "variant": "expired"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "ownerFresh",
    "variant": "missing"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "ownerFresh",
    "variant": "owner"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "ownerFresh",
    "variant": "session"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "ownerFresh",
    "variant": "revoked"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "ownerFresh",
    "variant": "expired"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "tokenInitial",
    "variant": "missing"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "tokenInitial",
    "variant": "owner"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "tokenInitial",
    "variant": "session"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "tokenInitial",
    "variant": "revoked"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "tokenInitial",
    "variant": "expired"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "tokenFresh",
    "variant": "missing"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "tokenFresh",
    "variant": "owner"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "tokenFresh",
    "variant": "session"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "tokenFresh",
    "variant": "revoked"
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "tokenFresh",
    "variant": "expired"
  },
  {
    "kind": "roleConflict",
    "role": "write",
    "admin": false,
    "nextrole": "readonly",
    "nextadmin": false
  },
  {
    "kind": "roleConflict",
    "role": "write",
    "admin": true,
    "nextrole": "readonly",
    "nextadmin": true
  },
  {
    "kind": "roleConflict",
    "role": "write",
    "admin": true,
    "nextrole": "write",
    "nextadmin": false
  },
  {
    "kind": "roleConflict",
    "role": "readonly",
    "admin": false,
    "nextrole": "write",
    "nextadmin": false
  },
  {
    "kind": "automationDemotion",
    "automation": true,
    "phase": "ownerFresh"
  },
  {
    "kind": "automationDemotion",
    "automation": true,
    "phase": "tokenFresh"
  },
  {
    "kind": "initialDenied",
    "automation": false,
    "variant": "removed"
  },
  {
    "kind": "initialDenied",
    "automation": false,
    "variant": "globalDeny"
  },
  {
    "kind": "initialDenied",
    "automation": false,
    "variant": "lookalike"
  },
  {
    "kind": "initialDenied",
    "automation": true,
    "variant": "removed"
  },
  {
    "kind": "initialDenied",
    "automation": true,
    "variant": "globalDeny"
  },
  {
    "kind": "initialDenied",
    "automation": true,
    "variant": "lookalike"
  },
  {
    "kind": "malformed",
    "automation": true,
    "principal": "owner",
    "variant": "actions"
  },
  {
    "kind": "malformed",
    "automation": true,
    "principal": "owner",
    "variant": "effect"
  },
  {
    "kind": "malformed",
    "automation": true,
    "principal": "owner",
    "variant": "prefix"
  },
  {
    "kind": "malformed",
    "automation": true,
    "principal": "owner",
    "variant": "count"
  },
  {
    "kind": "malformed",
    "automation": true,
    "principal": "token",
    "variant": "actions"
  },
  {
    "kind": "malformed",
    "automation": true,
    "principal": "token",
    "variant": "effect"
  },
  {
    "kind": "malformed",
    "automation": true,
    "principal": "token",
    "variant": "prefix"
  },
  {
    "kind": "malformed",
    "automation": true,
    "principal": "token",
    "variant": "count"
  },
  {
    "kind": "outage",
    "automation": true,
    "phase": "path"
  },
  {
    "kind": "outage",
    "automation": true,
    "phase": "ownerFresh"
  },
  {
    "kind": "outage",
    "automation": true,
    "phase": "tokenFresh"
  },
  {
    "kind": "partial",
    "automation": false,
    "principal": "owner"
  },
  {
    "kind": "partial",
    "automation": true,
    "principal": "owner"
  },
  {
    "kind": "partial",
    "automation": true,
    "principal": "token"
  },
  {
    "kind": "prefix",
    "prefix": ""
  },
  {
    "kind": "prefix",
    "prefix": "apps"
  },
  {
    "kind": "prefix",
    "prefix": "apps/api"
  },
  {
    "kind": "repromotion"
  },
  {
    "kind": "readonlyBeforeAuthorization"
  },
  {
    "kind": "capturedMetadata"
  },
  {
    "kind": "noAdminBypass"
  },
  {
    "kind": "initializationWithoutCreate"
  },
  {
    "kind": "noMutationOrExtraMetadata"
  }
];
for (const [index, c] of cases.entries()) test("public capability " + index + " " + JSON.stringify(c), async () => {
  const f = fixture(c);
  if (c.kind === "initialDenied" || c.kind === "noAdminBypass") {
    if (c.kind === "noAdminBypass") f.setUser(user("write", true));
    f.setRules("owner", changedRules(c.variant || "removed"));
    f.release(); await assert.rejects(f.registry.capabilities(f.who, "public-path"), denied(403)); return;
  }
  if (c.kind === "prefix") f.setRules("owner", [grant("public-mount", c.prefix)]);
  if (c.kind === "initializationWithoutCreate") { f.setUser(user("write", true)); f.setRules("owner", [grant(null, "", "allow", ["list", "read"])]); }
  const outcome: Promise<Row> = f.registry.capabilities(f.who, "public-path").then((value: Row) => ({ value, error: null }), (error: unknown) => ({ value: null, error }));
  await f.pending;
  assert.equal(f.reads.path, 1);
  let status: number | undefined, allowed = actions;
  switch (c.kind) {
    case "policy": f.setRules(c.principal, changedRules(c.variant)); status = 403; break;
    case "malformed": f.setRules(c.principal, changedRules(c.variant)); status = 503; break;
    case "account": f.setUser(c.variant === "missing" ? null : { ...user(), sessionVersion: 8 }); status = 401; break;
    case "identity": {
      const next = identity();
      if (c.variant === "owner") next.ownerId = "other-owner";
      if (c.variant === "session") next.ownerSessionVersion = 8;
      if (c.variant === "revoked") next.revokedAt = new Date();
      if (c.variant === "expired") next.expiresAt = new Date(0);
      f.setIdentity(c.variant === "missing" ? null : next); status = 401; break;
    }
    case "roleConflict": f.setUser(user(c.nextrole, c.nextadmin)); status = 409; break;
    case "automationDemotion": f.setUser(user("readonly")); status = 401; break;
    case "outage": f.fail(); break;
    case "partial": f.setRules(c.principal, [grant(null, "", "allow", ["list", "read", "update"]), grant(null, "apps", "deny", ["update"])]); allowed = ["list", "read"]; break;
    case "repromotion": f.setUser(user("readonly")); status = 409; break;
    case "readonlyBeforeAuthorization": f.setUser(user("readonly")); status = 409; break;
    case "capturedMetadata": f.setMetadata({ ...path(), id: "other-path", revision: 18 }); break;
  }
  f.release(); const result = await outcome;
  if (c.kind === "outage") { assert.equal(result.value, null); assert.match(result.error.message, /PUBLIC .* UNAVAILABLE/); }
  else if (status) { assert.equal(result.value, null); assert(denied(status)(result.error)); }
  else {
    assert.equal(result.error, null);
    assert.deepEqual(plain(result.value), expected(c.kind === "initializationWithoutCreate" ? { ...c, admin: true } : c, c.kind === "initializationWithoutCreate" ? ["list", "read"] : allowed));
  }
  assert.deepEqual(f.queries, [{ where: { id: "public-path" }, include: { fields: true, mount: true } }]);
  if (c.kind === "repromotion") {
    f.setUser(user()); assert.deepEqual(plain(await f.registry.capabilities(actor, "public-path")), expected({}));
    assert.equal(identity().revokedAt, null); assert.equal(user().sessionVersion, 7);
  }
});
