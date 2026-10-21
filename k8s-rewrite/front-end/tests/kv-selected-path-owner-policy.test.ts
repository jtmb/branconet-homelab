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
  let ownerRules = [grant()], tokenRules = [grant()], metadata: Row | null = path();
  const who = c.automation ? tokenActor : actor;
  const phase = c.phase || (c.principal === "token" ? "token" : "owner");
  const reads = { owner: 0, token: 0, account: 0, identity: 0, path: 0 };
  const queries: Row[] = [], failures = new Set<string>();
  let release!: () => void, entered!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const pending = new Promise<void>(resolve => { entered = resolve; });
  const hold = async (at: string) => { if (phase === at) { entered(); await gate; } if (failures.has(at)) throw new Error("PUBLIC " + at + " UNAVAILABLE"); };
  const db = {
    user: { findUnique: async ({ where }: Row) => { assert.deepEqual(plain(where), { id: actor.id }); reads.account++; return account && { ...account }; } },
    kvIdentity: { findUnique: async ({ where }: Row) => { assert.deepEqual(plain(where), { id: tokenActor.identityId }); reads.identity++; return credential && { ...credential }; } },
    kvPolicy: { findMany: async (query: Row) => {
      if (typeof query.where.principal === "object") {
        assert.deepEqual(plain(query), { where: { principal: { in: ["user:" + actor.id, "identity:" + tokenActor.identityId] } }, take: 513 });
        reads.owner++; reads.token++;
        await hold("owner"); await hold("token");
        return [...ownerRules.map(rule => ({ ...rule, principal: "user:" + actor.id })), ...tokenRules.map(rule => ({ ...rule, principal: "identity:" + tokenActor.identityId }))].slice(0, 513);
      }
      const kind = query.where.principal === "user:" + actor.id ? "owner" : "token";
      assert.deepEqual(plain(query), { where: { principal: kind === "owner" ? "user:" + actor.id : "identity:" + tokenActor.identityId }, take: 257 });
      reads[kind]++; await hold(kind); return (kind === "owner" ? ownerRules : tokenRules).map(rule => ({ ...rule }));
    } },
    kvPath: { findUnique: async (query: Row) => { reads.path++; queries.push(plain(query)); const captured = metadata; await hold("path"); return captured; } },
    $transaction: forbidden,
  };
  const registry = new KvRegistry(db, ["public-namespace"], { historyNamespace: "public-history", retention: 20, maxRetention: 100, guardedAdoption: false });
  return { registry, who, reads, queries, pending, release, phase,
    fail: (at = phase) => failures.add(at), setUser: (v: Row | null) => { account = v; }, setIdentity: (v: Row | null) => { credential = v; },
    setRules: (principal: string, v: Row[]) => { if (principal === "token") tokenRules = v; else ownerRules = v; },
    setMetadata: (v: Row | null) => { metadata = v; }, run: () => route.GET(registry, who, {}, { id: "public-path" }) };
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
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "removed",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "readOnly",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "wrongMount",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "wrongPrefix",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "lookalike",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "globalDeny",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "scopedDeny",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "actions",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "effect",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "prefix",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "count",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": false,
    "phase": "token",
    "variant": "outage",
    "baselineFail": true
  },
  {
    "kind": "stable",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "ownerRestored",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "tokenRestored",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "accountMissing",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "accountSession",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "identityMissing",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "identityOwner",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "identitySession",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "identityRevoked",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "identityExpired",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "demoted",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "repromoted",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "capturedMetadata",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "tokenOutage",
    "automation": true,
    "admin": false,
    "phase": "token"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner",
    "variant": "removed"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner",
    "variant": "readOnly"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner",
    "variant": "wrongMount"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner",
    "variant": "wrongPrefix"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner",
    "variant": "lookalike"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner",
    "variant": "globalDeny"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner",
    "variant": "scopedDeny"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner",
    "variant": "actions"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner",
    "variant": "effect"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner",
    "variant": "prefix"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner",
    "variant": "count"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token",
    "variant": "removed"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token",
    "variant": "readOnly"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token",
    "variant": "wrongMount"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token",
    "variant": "wrongPrefix"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token",
    "variant": "lookalike"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token",
    "variant": "globalDeny"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token",
    "variant": "scopedDeny"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token",
    "variant": "actions"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token",
    "variant": "effect"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token",
    "variant": "prefix"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token",
    "variant": "count"
  },
  {
    "kind": "ownerPrefix",
    "automation": true,
    "admin": false,
    "phase": "token",
    "prefix": ""
  },
  {
    "kind": "ownerPrefix",
    "automation": true,
    "admin": false,
    "phase": "token",
    "prefix": "apps"
  },
  {
    "kind": "ownerPrefix",
    "automation": true,
    "admin": false,
    "phase": "token",
    "prefix": "apps/api"
  },
  {
    "kind": "unrelatedDeny",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "owner"
  },
  {
    "kind": "unrelatedDeny",
    "automation": true,
    "admin": false,
    "phase": "token",
    "principal": "token"
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "removed",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "readOnly",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "wrongMount",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "wrongPrefix",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "lookalike",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "globalDeny",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "scopedDeny",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "actions",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "effect",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "prefix",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "count",
    "baselineFail": true
  },
  {
    "kind": "ownerDuringToken",
    "automation": true,
    "admin": true,
    "phase": "token",
    "variant": "outage",
    "baselineFail": true
  },
  {
    "kind": "stable",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "ownerRestored",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "tokenRestored",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "accountMissing",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "accountSession",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "identityMissing",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "identityOwner",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "identitySession",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "identityRevoked",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "identityExpired",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "demoted",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "repromoted",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "capturedMetadata",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "tokenOutage",
    "automation": true,
    "admin": true,
    "phase": "token"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner",
    "variant": "removed"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner",
    "variant": "readOnly"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner",
    "variant": "wrongMount"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner",
    "variant": "wrongPrefix"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner",
    "variant": "lookalike"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner",
    "variant": "globalDeny"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner",
    "variant": "scopedDeny"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner",
    "variant": "actions"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner",
    "variant": "effect"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner",
    "variant": "prefix"
  },
  {
    "kind": "initialPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner",
    "variant": "count"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token",
    "variant": "removed"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token",
    "variant": "readOnly"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token",
    "variant": "wrongMount"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token",
    "variant": "wrongPrefix"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token",
    "variant": "lookalike"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token",
    "variant": "globalDeny"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token",
    "variant": "scopedDeny"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token",
    "variant": "actions"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token",
    "variant": "effect"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token",
    "variant": "prefix"
  },
  {
    "kind": "tokenPolicy",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token",
    "variant": "count"
  },
  {
    "kind": "ownerPrefix",
    "automation": true,
    "admin": true,
    "phase": "token",
    "prefix": ""
  },
  {
    "kind": "ownerPrefix",
    "automation": true,
    "admin": true,
    "phase": "token",
    "prefix": "apps"
  },
  {
    "kind": "ownerPrefix",
    "automation": true,
    "admin": true,
    "phase": "token",
    "prefix": "apps/api"
  },
  {
    "kind": "unrelatedDeny",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "owner"
  },
  {
    "kind": "unrelatedDeny",
    "automation": true,
    "admin": true,
    "phase": "token",
    "principal": "token"
  },
  {
    "kind": "stable",
    "role": "readonly",
    "admin": false,
    "phase": "owner"
  },
  {
    "kind": "humanDemotion",
    "role": "readonly",
    "admin": false,
    "phase": "owner"
  },
  {
    "kind": "humanPolicyDeny",
    "role": "readonly",
    "admin": false,
    "phase": "owner"
  },
  {
    "kind": "humanPolicyMalformed",
    "role": "readonly",
    "admin": false,
    "phase": "owner"
  },
  {
    "kind": "stable",
    "role": "readonly",
    "admin": true,
    "phase": "owner"
  },
  {
    "kind": "humanDemotion",
    "role": "readonly",
    "admin": true,
    "phase": "owner"
  },
  {
    "kind": "humanPolicyDeny",
    "role": "readonly",
    "admin": true,
    "phase": "owner"
  },
  {
    "kind": "humanPolicyMalformed",
    "role": "readonly",
    "admin": true,
    "phase": "owner"
  },
  {
    "kind": "stable",
    "role": "write",
    "admin": false,
    "phase": "owner"
  },
  {
    "kind": "humanDemotion",
    "role": "write",
    "admin": false,
    "phase": "owner"
  },
  {
    "kind": "humanPolicyDeny",
    "role": "write",
    "admin": false,
    "phase": "owner"
  },
  {
    "kind": "humanPolicyMalformed",
    "role": "write",
    "admin": false,
    "phase": "owner"
  },
  {
    "kind": "stable",
    "role": "write",
    "admin": true,
    "phase": "owner"
  },
  {
    "kind": "humanDemotion",
    "role": "write",
    "admin": true,
    "phase": "owner"
  },
  {
    "kind": "humanPolicyDeny",
    "role": "write",
    "admin": true,
    "phase": "owner"
  },
  {
    "kind": "humanPolicyMalformed",
    "role": "write",
    "admin": true,
    "phase": "owner"
  }
];

for (const [index, c] of cases.entries()) test("public selected-path owner policy " + index + " " + JSON.stringify(c), async () => {
  const f = fixture(c);
  if (c.kind === "initialPolicy") {
    f.setRules("owner", changedRules(c.variant)); f.release();
    await assert.rejects(f.run(), denied(["actions", "effect", "prefix", "count"].includes(c.variant) ? 503 : 403));
    assert.equal(f.reads.owner, 1); assert.equal(f.reads.token, 0); return;
  }
  const outcome: Promise<Row> = f.run().then((value: Row) => ({value, error:null}), (error: unknown) => ({value:null,error}));
  await f.pending;
  let status: number | undefined, outage = false;
  switch (c.kind) {
    case "ownerDuringToken":
      if (c.variant === "outage") { f.fail("owner"); outage = true; }
      else { f.setRules("owner", changedRules(c.variant)); status = ["actions", "effect", "prefix", "count"].includes(c.variant) ? 503 : 403; }
      break;
    case "tokenPolicy": f.setRules("token", changedRules(c.variant)); status = ["actions", "effect", "prefix", "count"].includes(c.variant) ? 503 : 403; break;
    case "humanPolicyDeny": f.setRules("owner", [grant(),grant(null,"apps","deny",["list"])]); status = 403; break;
    case "humanPolicyMalformed": f.setRules("owner", changedRules("actions")); status = 503; break;
    case "ownerRestored": f.setRules("owner", []); f.setRules("owner", [grant()]); break;
    case "tokenRestored": f.setRules("token", []); f.setRules("token", [grant()]); break;
    case "ownerPrefix": f.setRules("owner", [grant("public-mount", c.prefix)]); break;
    case "unrelatedDeny": f.setRules(c.principal, [grant(),grant("other-mount","apps","deny",["list"]),grant(null,"apps","deny",["read"])]); break;
    case "accountMissing": f.setUser(null); status = 401; break;
    case "accountSession": f.setUser({...user(),sessionVersion:8}); status = 401; break;
    case "identityMissing": f.setIdentity(null); status = 401; break;
    case "identityOwner": f.setIdentity({...identity(),ownerId:"other-owner"}); status = 401; break;
    case "identitySession": f.setIdentity({...identity(),ownerSessionVersion:8}); status = 401; break;
    case "identityRevoked": f.setIdentity({...identity(),revokedAt:new Date(0)}); status = 401; break;
    case "identityExpired": f.setIdentity({...identity(),expiresAt:new Date(0)}); status = 401; break;
    case "demoted": case "repromoted": f.setUser(user("readonly")); status = 401; break;
    case "humanDemotion": f.setUser(user("readonly",c.admin)); break;
    case "capturedMetadata": f.setMetadata({...path(),id:"changed-id",revision:18,fields:[]}); break;
    case "tokenOutage": f.fail("token"); outage = true; break;
  }
  f.release(); const result = await outcome;
  if (outage) { assert.equal(result.value,null); assert.match(result.error?.message || "", /PUBLIC .* UNAVAILABLE/); }
  else if (status) { assert.equal(result.value,null); assert(denied(status)(result.error)); }
  else { assert.equal(result.error,null); assert.deepEqual(plain(result.value),expected()); }
  assert.equal(f.reads.path,1); assert.equal(f.reads.token,c.automation ? c.kind === "tokenPolicy" || c.kind === "tokenOutage" ? 1 : 2 : 0);
  assert.deepEqual(f.queries,[{where:{id:"public-path"},include:{fields:true,mount:true}}]);
  if (c.kind === "repromoted") {
    f.setUser(user("write",c.admin)); assert.deepEqual(plain(await f.run()),expected());
    assert.equal(user().sessionVersion,7); assert.equal(identity().revokedAt,null);
  }
});
