import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC caller-source controls. Credential parsing/hashing and all
// database/native dependencies are inert stubs; no actual credential is used.
type Row = Record<string, any>;
const now = 2_000_000_000_000;
class Clock extends Date { static now() { return now; } }
class SecretError extends Error { constructor(readonly status: number, message: string) { super(message); } }
const forbidden = () => { throw Error("Outside ordinary authentication caller-source scope"); };
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
const plain = (v: unknown) => JSON.parse(JSON.stringify(v));
const config = { historyNamespace: "public-history", retention: 20, maxRetention: 100, guardedAdoption: false };
const scope = { mountId: "public-mount", path: "apps/api" };
const denied = (status: number, message: string) => (error: unknown) =>
  error instanceof contract.KvError && (error as SecretError).status === status && (error as Error).message === message;
const credentialDenied = denied(401, "Invalid KV automation credential");
const accountDenied = denied(401, "Authentication required");
const identityDenied = denied(401, "KV identity revoked or expired");
const policyDenied = denied(403, "KV policy denies this action");
function fixture() {
  const actor = { id: "public-owner", sessionVersion: 7, identityId: "public-identity" };
  const user = { id: actor.id, sessionVersion: 7, role: "write", engineAdmin: false };
  const initial = { id: actor.identityId, ownerId: actor.id, ownerSessionVersion: 7,
    credentialHash: "PUBLIC-STORED-MODEL", revokedAt: null, expiresAt: new Date(now + 60_000) };
  const fresh = { ...initial };
  const allow = () => [{ mountId: scope.mountId, prefix: "apps", effect: "allow", actions: '["list","read"]' }];
  const state = { presented: { id: actor.identityId, hash: "PUBLIC-PRESENTED-MODEL" } as Row | null,
    hashAccepted: true, initial: initial as Row | null, fresh: fresh as Row | null,
    user: user as Row | null, ownerRules: allow(), identityRules: allow(), lookup: 0 };
  const calls: string[] = [];
  const { KvRegistry } = evaluate("src/lib/kv-registry.ts", {
    "./kv-contract": contract, "./cluster-secrets": cluster,
    "./kv-identity-revision": { identityRevision: forbidden, expectedIdentityRevision: forbidden },
    "./kv-credentials": { issueCredential: forbidden,
      presentedCredential: (header: string | null) => { assert([null, "PUBLIC-HEADER"].includes(header)); calls.push("present"); return state.presented; },
      hashMatches: (a: string, b: string) => { assert.equal(a, "PUBLIC-PRESENTED-MODEL"); assert.equal(b, "PUBLIC-STORED-MODEL"); calls.push("hash"); return state.hashAccepted; } },
    "./kv-legacy-access": Object.fromEntries(["acknowledgeLegacyImpact", "legacyImpact", "legacyImpactPage", "readLegacyAliases"].map(n => [n, forbidden])),
  });
  const db = {
    user: { findUnique: async (args: Row) => { assert.deepEqual(plain(args), { where: { id: actor.id } }); calls.push("user"); return state.user; } },
    kvIdentity: { findUnique: async (args: Row) => {
      assert.deepEqual(plain(args), { where: { id: actor.identityId } });
      const initialRead = state.lookup++ === 0; calls.push(initialRead ? "initial" : "fresh");
      return initialRead ? state.initial : state.fresh;
    } },
    kvPolicy: { findMany: async (args: Row) => {
      const principal = args.where.principal;
      assert([`user:${actor.id}`, `identity:${actor.identityId}`].includes(principal));
      assert.deepEqual(plain(args), { where: { principal }, take: 257 }); calls.push(principal);
      return principal === `user:${actor.id}` ? state.ownerRules : state.identityRules;
    } },
    $queryRaw: forbidden, $transaction: forbidden,
  };
  const registry = new KvRegistry(db, ["public-namespace"], config, forbidden);
  const authenticate = () => { state.lookup = 0; return registry.authenticateIdentity("PUBLIC-HEADER"); };
  return { actor, user, initial, fresh, state, calls, db, registry, authenticate };
}

test("ordinary authentication delegates to fresh current authority", async t => {
  for (const label of ["absent header", "presenter refusal"] as const) {
    await t.test(label, async () => {
      const f = fixture(); f.state.presented = null;
      await assert.rejects(f.registry.authenticateIdentity(label === "absent header" ? null : "PUBLIC-HEADER"), credentialDenied);
      assert.deepEqual(f.calls, ["present"]);
    });
  }
  await t.test("missing initial identity refuses before hash and owner", async () => {
    const f = fixture(); f.state.initial = null;
    await assert.rejects(f.authenticate(), credentialDenied); assert.deepEqual(f.calls, ["present", "initial"]);
  });
  await t.test("rejected hash refuses before owner lookup", async () => {
    const f = fixture(); f.state.hashAccepted = false;
    await assert.rejects(f.authenticate(), credentialDenied); assert.deepEqual(f.calls, ["present", "initial", "hash"]);
  });
  await t.test("valid caller returns only actor identifiers after fresh authority", async () => {
    const f = fixture(); assert.deepEqual(plain(await f.authenticate()), f.actor);
    assert.deepEqual(f.calls, ["present", "initial", "hash", "user", "fresh"]);
  });
  for (const [label, expiry] of [["one millisecond future", new Date(now + 1)],
    ["maximum finite Date", new Date(8_640_000_000_000_000)]] as const) {
    await t.test(label, async () => {
      const f = fixture(); f.fresh.expiresAt = expiry; assert.deepEqual(plain(await f.authenticate()), f.actor);
    });
  }
  for (const [label, expiry] of [["invalid Date", new Date(NaN)], ["positive Infinity", { getTime: () => Infinity }],
    ["negative Infinity", { getTime: () => -Infinity }], ["past", new Date(now - 1)], ["clock equality", new Date(now)]] as const) {
    await t.test(`fresh identity rejects ${label}`, async () => {
      const f = fixture(); f.state.fresh!.expiresAt = expiry;
      await assert.rejects(f.authenticate(), identityDenied);
      assert.deepEqual(f.calls, ["present", "initial", "hash", "user", "fresh"]);
    });
  }
  for (const [label, change, refusal, finalRead] of [
    ["deleted owner", (f: ReturnType<typeof fixture>) => { f.state.user = null; }, accountDenied, false],
    ["changed owner session", (f: ReturnType<typeof fixture>) => { f.user.sessionVersion++; }, accountDenied, false],
    ["missing fresh identity", (f: ReturnType<typeof fixture>) => { f.state.fresh = null; }, identityDenied, true],
    ["changed identity owner", (f: ReturnType<typeof fixture>) => { f.fresh.ownerId = "public-other"; }, identityDenied, true],
    ["changed identity session", (f: ReturnType<typeof fixture>) => { f.fresh.ownerSessionVersion++; }, identityDenied, true],
    ["fresh revocation", (f: ReturnType<typeof fixture>) => { f.state.fresh!.revokedAt = new Date(now); }, identityDenied, true],
    ["readonly owner", (f: ReturnType<typeof fixture>) => { f.user.role = "readonly"; }, identityDenied, true],
  ] as const) {
    await t.test(label, async () => {
      const f = fixture(); change(f); await assert.rejects(f.authenticate(), refusal);
      assert.deepEqual(f.calls, ["present", "initial", "hash", "user", ...(finalRead ? ["fresh"] : [])]);
    });
  }
  await t.test("role-only restoration changes no session or revocation metadata", async () => {
    const f = fixture(), before = plain({ user: f.user, identity: f.fresh });
    assert.deepEqual(plain(await f.authenticate()), f.actor);
    f.user.role = "readonly"; await assert.rejects(f.authenticate(), identityDenied);
    f.user.role = "write"; assert.deepEqual(plain(await f.authenticate()), f.actor);
    assert.deepEqual(plain({ user: f.user, identity: f.fresh }), before);
    assert.equal(f.calls.filter(c => c === "user").length, 3);
  });
  for (const [label, change, refusal] of [
    ["revocation", (f: ReturnType<typeof fixture>) => { f.state.fresh!.revokedAt = new Date(now); }, identityDenied],
    ["owner session withdrawal", (f: ReturnType<typeof fixture>) => { f.user.sessionVersion++; }, accountDenied],
    ["expiry withdrawal", (f: ReturnType<typeof fixture>) => { f.fresh.expiresAt = new Date(now); }, identityDenied],
    ["owner deletion", (f: ReturnType<typeof fixture>) => { f.state.user = null; }, accountDenied],
  ] as const) {
    await t.test(`later ${label} is not cached`, async () => {
      const f = fixture(); assert.deepEqual(plain(await f.authenticate()), f.actor);
      change(f); await assert.rejects(f.authenticate(), refusal);
      assert.equal(f.calls.filter(c => c === "hash").length, 2);
    });
    await t.test(`repromotion does not bypass ${label}`, async () => {
      const f = fixture(); f.user.role = "readonly"; await assert.rejects(f.authenticate(), identityDenied);
      change(f); f.user.role = "write"; await assert.rejects(f.authenticate(), refusal);
    });
  }
  await t.test("returned actor still requires fresh ordinary authorization", async () => {
    const f = fixture(), actor = await f.authenticate(); f.user.role = "readonly";
    await assert.rejects(f.registry.authorize(actor, scope, "read"), identityDenied);
    assert.equal(f.calls.some(c => c.startsWith("user:")), false);
  });
  await t.test("returned actor retains both policy grants", async () => {
    const f = fixture(), actor = await f.authenticate();
    assert.equal(await f.registry.authorize(actor, scope, "read"), f.user);
    assert.deepEqual(f.calls.slice(-4), ["user", "fresh", "user:public-owner", "identity:public-identity"]);
  });
  for (const principal of ["ownerRules", "identityRules"] as const) {
    for (const mode of ["missing allow", "explicit deny", "neighbor prefix"] as const) {
      await t.test(`${principal} ${mode} remains denied`, async () => {
        const f = fixture(), actor = await f.authenticate();
        if (mode === "missing allow") f.state[principal] = [];
        else if (mode === "explicit deny") f.state[principal].push({ mountId: scope.mountId, prefix: "apps/api", effect: "deny", actions: '["read"]' });
        else f.state[principal][0].prefix = "apps/api-neighbor";
        await assert.rejects(f.registry.authorize(actor, scope, "read"), policyDenied);
      });
    }
  }
});
