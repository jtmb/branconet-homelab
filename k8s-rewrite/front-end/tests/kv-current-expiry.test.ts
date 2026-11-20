import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC source-row controls. No ORM, SQL, native client or HTTP is
// loaded. Invalid Date/Infinity are source models, not database decoding claims.
type Row = Record<string, any>;
const now = 2_000_000_000_000;
class Clock extends Date { static now() { return now; } }
class SecretError extends Error { constructor(readonly status: number, message: string) { super(message); } }
const forbidden = () => { throw Error("Outside ordinary-current public source scope"); };
function evaluate(file: string, dependencies: Row) {
  const m = { exports: {} as any };
  const output = ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  runInNewContext(output, { module: m, exports: m.exports, Buffer, Date: Clock, JSON,
    require: (name: string) => { assert(Object.hasOwn(dependencies, name), `Unselected dependency: ${name}`); return dependencies[name]; },
  }, { filename: file, timeout: 5000 });
  return m.exports;
}
const cluster = { SecretError, validateTarget: forbidden };
const contract = evaluate("src/lib/kv-contract.ts", { "./cluster-secrets": cluster });
const { KvRegistry } = evaluate("src/lib/kv-registry.ts", {
  "./kv-contract": contract, "./cluster-secrets": cluster,
  "./kv-identity-revision": { identityRevision: forbidden, expectedIdentityRevision: forbidden },
  "./kv-credentials": { issueCredential: forbidden, hashMatches: forbidden, presentedCredential: forbidden },
  "./kv-legacy-access": Object.fromEntries(["acknowledgeLegacyImpact", "legacyImpact", "legacyImpactPage", "readLegacyAliases"].map(n => [n, forbidden])),
});
const plain = (value: unknown) => JSON.parse(JSON.stringify(value));
const scope = { mountId: "public-mount", path: "apps/api" };
const config = { historyNamespace: "public-history", retention: 20, maxRetention: 100, guardedAdoption: false };
const failure = (status: number, message: string) => (error: unknown) =>
  error instanceof contract.KvError && (error as SecretError).status === status && (error as Error).message === message;
const identityDenied = failure(401, "KV identity revoked or expired");
const accountDenied = failure(401, "Authentication required");
const policyDenied = failure(403, "KV policy denies this action");
function fixture() {
  const actor = { id: "public-owner", sessionVersion: 7, identityId: "public-identity" };
  const user = { id: actor.id, sessionVersion: 7, role: "write", engineAdmin: false };
  const identity = { id: actor.identityId, ownerId: actor.id, ownerSessionVersion: 7,
    revokedAt: null as Date | null, expiresAt: new Date(now + 60_000) as any };
  const allow = () => [{ mountId: scope.mountId, prefix: "apps", effect: "allow", actions: '["list","read"]' }];
  const state = { user: user as typeof user | null, identity: identity as typeof identity | null,
    ownerRules: allow(), identityRules: allow() };
  const calls: string[] = [];
  const db = {
    user: { findUnique: async (args: Row) => { assert.deepEqual(plain(args), { where: { id: actor.id } }); calls.push("user"); return state.user; } },
    kvIdentity: { findUnique: async (args: Row) => { assert.deepEqual(plain(args), { where: { id: actor.identityId } }); calls.push("identity"); return state.identity; } },
    kvPolicy: { findMany: async (args: Row) => {
      const principal = args.where.principal;
      assert([`user:${actor.id}`, `identity:${actor.identityId}`].includes(principal));
      assert.deepEqual(plain(args), { where: { principal }, take: 257 }); calls.push(principal);
      return principal === `user:${actor.id}` ? state.ownerRules : state.identityRules;
    } },
    $queryRaw: forbidden, $transaction: forbidden,
  };
  const registry = new KvRegistry(db, ["public-namespace"], config, forbidden);
  return { actor, user, identity, state, calls, db, registry };
}

test("ordinary current finite-expiry source controls", async t => {
  await t.test("future identity returns the fresh owner", async () => {
    const f = fixture(); assert.equal(await f.registry.current(f.actor), f.user);
    assert.deepEqual(f.calls, ["user", "identity"]);
  });
  await t.test("one millisecond future identity remains valid", async () => {
    const f = fixture(); f.identity.expiresAt = new Date(now + 1);
    assert.equal(await f.registry.current(f.actor), f.user);
  });
  await t.test("maximum finite Date remains valid", async () => {
    const f = fixture(); f.identity.expiresAt = new Date(8_640_000_000_000_000);
    assert.equal(await f.registry.current(f.actor), f.user);
  });
  for (const [label, expiresAt] of [["invalid Date", new Date(NaN)], ["positive Infinity", { getTime: () => Infinity }]] as const) {
    await t.test(`current rejects ${label}`, async () => {
      const f = fixture(); f.identity.expiresAt = expiresAt;
      await assert.rejects(f.registry.current(f.actor), identityDenied);
      assert.deepEqual(f.calls, ["user", "identity"]);
    });
    await t.test(`authorize rejects ${label} before policy reads`, async () => {
      const f = fixture(); f.identity.expiresAt = expiresAt;
      await assert.rejects(f.registry.authorize(f.actor, scope, "read"), identityDenied);
      assert.deepEqual(f.calls, ["user", "identity"]);
    });
  }
  for (const [label, expiresAt] of [["negative Infinity", { getTime: () => -Infinity }],
    ["past", new Date(now - 1)], ["clock equality", new Date(now)]] as const) {
    await t.test(`current rejects ${label}`, async () => {
      const f = fixture(); f.identity.expiresAt = expiresAt;
      await assert.rejects(f.registry.current(f.actor), identityDenied);
    });
  }
  await t.test("deleted owner refuses before identity read", async () => {
    const f = fixture(); f.state.user = null;
    await assert.rejects(f.registry.current(f.actor), accountDenied); assert.deepEqual(f.calls, ["user"]);
  });
  await t.test("stale owner session refuses before identity read", async () => {
    const f = fixture(); f.user.sessionVersion++;
    await assert.rejects(f.registry.current(f.actor), accountDenied); assert.deepEqual(f.calls, ["user"]);
  });
  for (const [label, change] of [
    ["missing identity", (f: ReturnType<typeof fixture>) => { f.state.identity = null; }],
    ["wrong owner", (f: ReturnType<typeof fixture>) => { f.identity.ownerId = "public-other-owner"; }],
    ["stale identity owner session", (f: ReturnType<typeof fixture>) => { f.identity.ownerSessionVersion--; }],
    ["revoked identity", (f: ReturnType<typeof fixture>) => { f.identity.revokedAt = new Date(now - 1); }],
    ["readonly owner", (f: ReturnType<typeof fixture>) => { f.user.role = "readonly"; }],
  ] as const) {
    await t.test(`current rejects ${label}`, async () => {
      const f = fixture(); change(f); await assert.rejects(f.registry.current(f.actor), identityDenied);
    });
  }
  await t.test("explicit client remains selected", async () => {
    const f = fixture(), registry = new KvRegistry({ user: { findUnique: forbidden } }, [], config, forbidden);
    assert.equal(await registry.current(f.actor, f.db), f.user);
    assert.deepEqual(f.calls, ["user", "identity"]);
  });
  await t.test("human readonly current performs no identity read", async () => {
    const f = fixture(); f.user.role = "readonly";
    assert.equal(await f.registry.current({ id: f.actor.id, sessionVersion: 7 }), f.user);
    assert.deepEqual(f.calls, ["user"]);
  });
  await t.test("human readonly list retains policy access", async () => {
    const f = fixture(); f.user.role = "readonly";
    assert.equal(await f.registry.authorize({ id: f.actor.id, sessionVersion: 7 }, scope, "list"), f.user);
    assert.deepEqual(f.calls, ["user", "user:public-owner"]);
  });
  await t.test("human readonly read still refuses before policy", async () => {
    const f = fixture(); f.user.role = "readonly";
    await assert.rejects(f.registry.authorize({ id: f.actor.id, sessionVersion: 7 }, scope, "read"),
      failure(403, "KV values and changes require write access"));
    assert.deepEqual(f.calls, ["user"]);
  });
  await t.test("role-only demotion and restoration preserve session and revocation", async () => {
    const f = fixture(), before = plain({ session: f.user.sessionVersion, ownerSession: f.identity.ownerSessionVersion, revoked: f.identity.revokedAt });
    assert.equal(await f.registry.current(f.actor), f.user);
    f.user.role = "readonly"; await assert.rejects(f.registry.current(f.actor), identityDenied);
    f.user.role = "write"; assert.equal(await f.registry.current(f.actor), f.user);
    assert.deepEqual(plain({ session: f.user.sessionVersion, ownerSession: f.identity.ownerSessionVersion, revoked: f.identity.revokedAt }), before);
    assert.deepEqual(f.calls, ["user", "identity", "user", "identity", "user", "identity"]);
  });
  await t.test("repromotion does not restore revoked identity", async () => {
    const f = fixture(); f.user.role = "readonly"; f.identity.revokedAt = new Date(now);
    await assert.rejects(f.registry.current(f.actor), identityDenied); f.user.role = "write";
    await assert.rejects(f.registry.current(f.actor), identityDenied);
  });
  await t.test("repromotion does not restore changed session", async () => {
    const f = fixture(); f.user.role = "readonly"; f.user.sessionVersion++;
    await assert.rejects(f.registry.current(f.actor), accountDenied); f.user.role = "write";
    await assert.rejects(f.registry.current(f.actor), accountDenied);
  });
  await t.test("subsequent owner deletion remains fresh", async () => {
    const f = fixture(); assert.equal(await f.registry.current(f.actor), f.user); f.state.user = null;
    await assert.rejects(f.registry.current(f.actor), accountDenied);
  });
  await t.test("subsequent identity revocation remains fresh", async () => {
    const f = fixture(); assert.equal(await f.registry.current(f.actor), f.user); f.identity.revokedAt = new Date(now);
    await assert.rejects(f.registry.current(f.actor), identityDenied);
  });
  await t.test("ordinary authorization requires both matching policy sets", async () => {
    const f = fixture(); assert.equal(await f.registry.authorize(f.actor, scope, "read"), f.user);
    assert.deepEqual(f.calls, ["user", "identity", "user:public-owner", "identity:public-identity"]);
  });
  for (const lane of ["ownerRules", "identityRules"] as const) {
    for (const condition of ["missing", "deny", "wrong mount", "prefix boundary", "wrong action"] as const) {
      await t.test(`ordinary authorization refuses ${lane} ${condition}`, async () => {
        const f = fixture(), rules = f.state[lane];
        if (condition === "missing") f.state[lane] = [];
        if (condition === "deny") rules.push({ mountId: scope.mountId, prefix: "apps", effect: "deny", actions: '["read"]' });
        if (condition === "wrong mount") rules[0].mountId = "public-other-mount";
        if (condition === "prefix boundary") rules[0].prefix = "app";
        if (condition === "wrong action") rules[0].actions = '["list"]';
        await assert.rejects(f.registry.authorize(f.actor, scope, "read"), policyDenied);
      });
    }
  }
  await t.test("malformed policy remains a metadata refusal", async () => {
    const f = fixture(); f.state.identityRules[0].actions = "invalid-public-json";
    await assert.rejects(f.registry.authorize(f.actor, scope, "read"), failure(503, "KV policy metadata unavailable"));
  });
  await t.test("policy withdrawal between calls is not cached", async () => {
    const f = fixture(); assert.equal(await f.registry.authorize(f.actor, scope, "read"), f.user);
    f.state.ownerRules = []; await assert.rejects(f.registry.authorize(f.actor, scope, "read"), policyDenied);
  });
});
