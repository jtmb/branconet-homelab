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
    $queryRaw: async (strings: TemplateStringsArray, ...values: unknown[]) => {
      assert.equal(strings.join("?").replace(/\s+/g, " ").trim(), "SELECT u.\"id\", u.\"sessionVersion\", u.\"role\", i.\"id\" AS \"identityId\", i.\"ownerId\", i.\"ownerSessionVersion\", i.\"revokedAt\", i.\"expiresAt\" FROM \"users\" AS u LEFT JOIN \"kv_identities\" AS i ON i.\"id\" = ? WHERE u.\"id\" = ? LIMIT 1");
      assert.deepEqual(plain(values), [tokenActor.identityId, actor.id]);
      reads.account++; reads.identity++;
      return account ? [{ id: account.id, sessionVersion: account.sessionVersion, role: account.role,
        identityId: credential?.id ?? null, ownerId: credential?.ownerId ?? null,
        ownerSessionVersion: credential?.ownerSessionVersion ?? null, revokedAt: credential?.revokedAt ?? null,
        expiresAt: credential?.expiresAt ?? null }] : [];
    },
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
    fail: () => failures.add(phase), setUser: (v: Row | null) => { account = v; }, setIdentity: (v: Row | null) => { credential = v; },
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
    "kind": "stable",
    "role": "write",
    "admin": false
  },
  {
    "kind": "stable",
    "role": "write",
    "admin": true
  },
  {
    "kind": "stable",
    "role": "readonly",
    "admin": false
  },
  {
    "kind": "stable",
    "role": "readonly",
    "admin": true
  },
  {
    "kind": "stable",
    "automation": true,
    "admin": false
  },
  {
    "kind": "stable",
    "automation": true,
    "admin": true
  },
  {
    "kind": "account",
    "automation": false,
    "phase": "path",
    "variant": "missing",
    "baselineFail": false
  },
  {
    "kind": "account",
    "automation": false,
    "phase": "path",
    "variant": "session",
    "baselineFail": false
  },
  {
    "kind": "account",
    "automation": false,
    "phase": "owner",
    "variant": "missing",
    "baselineFail": true
  },
  {
    "kind": "account",
    "automation": false,
    "phase": "owner",
    "variant": "session",
    "baselineFail": true
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "path",
    "variant": "missing",
    "baselineFail": false
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "path",
    "variant": "session",
    "baselineFail": false
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "owner",
    "variant": "missing",
    "baselineFail": true
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "owner",
    "variant": "session",
    "baselineFail": true
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "token",
    "variant": "missing",
    "baselineFail": true
  },
  {
    "kind": "account",
    "automation": true,
    "phase": "token",
    "variant": "session",
    "baselineFail": true
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "path",
    "variant": "missing",
    "baselineFail": false
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "path",
    "variant": "owner",
    "baselineFail": false
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "path",
    "variant": "session",
    "baselineFail": false
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "path",
    "variant": "revoked",
    "baselineFail": false
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "path",
    "variant": "expired",
    "baselineFail": false
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "owner",
    "variant": "missing",
    "baselineFail": true
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "owner",
    "variant": "owner",
    "baselineFail": true
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "owner",
    "variant": "session",
    "baselineFail": true
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "owner",
    "variant": "revoked",
    "baselineFail": true
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "owner",
    "variant": "expired",
    "baselineFail": true
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "token",
    "variant": "missing",
    "baselineFail": true
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "token",
    "variant": "owner",
    "baselineFail": true
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "token",
    "variant": "session",
    "baselineFail": true
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "token",
    "variant": "revoked",
    "baselineFail": true
  },
  {
    "kind": "identity",
    "automation": true,
    "phase": "token",
    "variant": "expired",
    "baselineFail": true
  },
  {
    "kind": "automationDemotion",
    "automation": true,
    "phase": "path",
    "baselineFail": false
  },
  {
    "kind": "automationDemotion",
    "automation": true,
    "phase": "owner",
    "baselineFail": true
  },
  {
    "kind": "automationDemotion",
    "automation": true,
    "phase": "token",
    "baselineFail": true
  },
  {
    "kind": "humanDemotion",
    "phase": "path",
    "admin": false
  },
  {
    "kind": "humanDemotion",
    "phase": "path",
    "admin": true
  },
  {
    "kind": "humanDemotion",
    "phase": "owner",
    "admin": false
  },
  {
    "kind": "humanDemotion",
    "phase": "owner",
    "admin": true
  },
  {
    "kind": "repromotion",
    "automation": true,
    "phase": "owner",
    "baselineFail": true
  },
  {
    "kind": "humanRepromotion",
    "role": "readonly"
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "removed"
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "readOnly"
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "wrongMount"
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "wrongPrefix"
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "lookalike"
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "globalDeny"
  },
  {
    "kind": "policy",
    "automation": false,
    "principal": "owner",
    "variant": "scopedDeny"
  },
  {
    "kind": "malformed",
    "automation": false,
    "principal": "owner",
    "variant": "actions"
  },
  {
    "kind": "malformed",
    "automation": false,
    "principal": "owner",
    "variant": "effect"
  },
  {
    "kind": "malformed",
    "automation": false,
    "principal": "owner",
    "variant": "prefix"
  },
  {
    "kind": "malformed",
    "automation": false,
    "principal": "owner",
    "variant": "count"
  },
  {
    "kind": "prefix",
    "automation": false,
    "principal": "owner",
    "prefix": ""
  },
  {
    "kind": "prefix",
    "automation": false,
    "principal": "owner",
    "prefix": "apps"
  },
  {
    "kind": "prefix",
    "automation": false,
    "principal": "owner",
    "prefix": "apps/api"
  },
  {
    "kind": "partial",
    "automation": false,
    "principal": "owner"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "removed"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "readOnly"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "wrongMount"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "wrongPrefix"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "lookalike"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "globalDeny"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "owner",
    "variant": "scopedDeny"
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
    "kind": "prefix",
    "automation": true,
    "principal": "owner",
    "prefix": ""
  },
  {
    "kind": "prefix",
    "automation": true,
    "principal": "owner",
    "prefix": "apps"
  },
  {
    "kind": "prefix",
    "automation": true,
    "principal": "owner",
    "prefix": "apps/api"
  },
  {
    "kind": "partial",
    "automation": true,
    "principal": "owner"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "removed"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "readOnly"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "wrongMount"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "wrongPrefix"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "lookalike"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "globalDeny"
  },
  {
    "kind": "policy",
    "automation": true,
    "principal": "token",
    "variant": "scopedDeny"
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
    "kind": "prefix",
    "automation": true,
    "principal": "token",
    "prefix": ""
  },
  {
    "kind": "prefix",
    "automation": true,
    "principal": "token",
    "prefix": "apps"
  },
  {
    "kind": "prefix",
    "automation": true,
    "principal": "token",
    "prefix": "apps/api"
  },
  {
    "kind": "partial",
    "automation": true,
    "principal": "token"
  },
  {
    "kind": "outage",
    "automation": false,
    "phase": "owner"
  },
  {
    "kind": "outage",
    "automation": true,
    "phase": "owner"
  },
  {
    "kind": "outage",
    "automation": true,
    "phase": "token"
  },
  {
    "kind": "capturedMetadata",
    "automation": false,
    "phase": "path"
  },
  {
    "kind": "capturedMetadata",
    "automation": true,
    "phase": "path"
  },
  {
    "kind": "invalidNamespace"
  },
  {
    "kind": "historyNamespace"
  },
  {
    "kind": "invalidMount"
  },
  {
    "kind": "invalidMapping"
  },
  {
    "kind": "missingPath"
  },
  {
    "kind": "noAdminBypass"
  }
];
for (const [index, c] of cases.entries()) test("public selected path " + index + " " + JSON.stringify(c), async () => {
  const f = fixture(c);
  if (["invalidNamespace", "historyNamespace", "invalidMount", "invalidMapping", "missingPath", "noAdminBypass"].includes(c.kind)) {
    const p = path(); let status = 403;
    if (c.kind === "invalidNamespace") p.namespace = "other-namespace";
    if (c.kind === "historyNamespace") p.namespace = "public-history";
    if (c.kind === "invalidMount") p.mount.namespaces = '["other-namespace"]';
    if (c.kind === "invalidMapping") { p.fields[0].namespace = "other-namespace"; status = 503; }
    if (c.kind === "missingPath") status = 404;
    f.setMetadata(c.kind === "missingPath" ? null : p);
    if (c.kind === "noAdminBypass") { f.setUser(user("write", true)); f.setRules("owner", []); }
    f.release(); await assert.rejects(f.run(), denied(status)); return;
  }
  const outcome: Promise<Row> = f.run().then((value: Row) => ({ value, error: null }), (error: unknown) => ({ value: null, error }));
  await f.pending;
  assert.equal(f.reads.path, 1);
  let status: number | undefined;
  switch (c.kind) {
    case "account": f.setUser(c.variant === "missing" ? null : { ...user(), sessionVersion: 8 }); status = 401; break;
    case "identity": {
      const next = identity();
      if (c.variant === "owner") next.ownerId = "other-owner";
      if (c.variant === "session") next.ownerSessionVersion = 8;
      if (c.variant === "revoked") next.revokedAt = new Date();
      if (c.variant === "expired") next.expiresAt = new Date(0);
      f.setIdentity(c.variant === "missing" ? null : next); status = 401; break;
    }
    case "automationDemotion": case "repromotion": f.setUser(user("readonly")); status = 401; break;
    case "humanDemotion": f.setUser(user("readonly", c.admin)); break;
    case "humanRepromotion": f.setUser(user()); break;
    case "policy": f.setRules(c.principal, changedRules(c.variant)); status = 403; break;
    case "malformed": f.setRules(c.principal, changedRules(c.variant)); status = 503; break;
    case "outage": f.fail(); break;
    case "prefix": f.setRules(c.principal, [grant("public-mount", c.prefix)]); break;
    case "partial": f.setRules(c.principal, [grant(null, "", "allow", ["list", "read"]), grant(null, "apps", "deny", ["read"])]); break;
    case "capturedMetadata": f.setMetadata({ ...path(), id: "other-path", revision: 18, fields: [] }); break;
  }
  f.release(); const result = await outcome;
  if (c.kind === "outage") { assert.equal(result.value, null); assert.match(result.error.message, /PUBLIC .* UNAVAILABLE/); }
  else if (status) { assert.equal(result.value, null); assert(denied(status)(result.error)); }
  else { assert.equal(result.error, null); assert.deepEqual(plain(result.value), expected()); }
  assert.deepEqual(f.queries, [{ where: { id: "public-path" }, include: { fields: true, mount: true } }]);
  const earlyAccountRefusal = f.phase === "path" && ["account", "identity", "automationDemotion"].includes(c.kind);
  const policyRefusal = ["policy", "malformed", "outage"].includes(c.kind);
  assert.equal(f.reads.owner, earlyAccountRefusal ? 0 : c.automation && !policyRefusal ? 2 : 1);
  assert.equal(f.reads.token, !c.automation || earlyAccountRefusal || (f.phase === "owner" && policyRefusal) ? 0 : policyRefusal ? 1 : 2);
  if (c.kind === "repromotion") {
    f.setUser(user()); assert.deepEqual(plain(await f.run()), expected());
    assert.equal(identity().revokedAt, null); assert.equal(user().sessionVersion, 7);
  }
});
