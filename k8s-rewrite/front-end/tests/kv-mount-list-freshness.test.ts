import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// PUBLIC synthetic source controls only: real registry/current/admin and parser,
// deferred metadata query, account doubles. No ORM/server/native/credential/
// recovery/transaction/network/subprocess execution.
type Row = Record<string, any>;
type User = { id: string; sessionVersion: number; role: string; engineAdmin: boolean };
const actor = { id: "public-admin", sessionVersion: 7 };
const user = (role = "write", engineAdmin = true): User => ({ ...actor, role, engineAdmin });
const plain = (value: unknown): any => JSON.parse(JSON.stringify(value));
const forbidden = () => { throw new Error("Outside public mount-list controls"); };
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
const cluster = { SecretError, validateTarget: forbidden };
const contract = evaluate("src/lib/kv-contract.ts", { "./cluster-secrets": cluster });
const revisions = evaluate("src/lib/kv-identity-revision.ts", { "node:crypto": { createHash }, "./kv-contract": contract });
const { KvRegistry } = evaluate("src/lib/kv-registry.ts", {
  "./kv-contract": contract, "./cluster-secrets": cluster, "./kv-identity-revision": revisions,
  "./kv-credentials": { issueCredential: forbidden, hashMatches: forbidden, presentedCredential: forbidden },
  "./kv-legacy-access": Object.fromEntries(["acknowledgeLegacyImpact", "legacyImpact", "legacyImpactPage", "readLegacyAliases"].map(name => [name, forbidden])),
});
const deny = (status: number) => (error: any) => error instanceof contract.KvError && error.status === status;
const row = (index: number): Row => ({ id: "public-" + String(index).padStart(3, "0"),
  name: "public-mount-" + index, namespaces: '["public-namespace"]', revision: 3 });
const grant = (mountId: string | null = null, prefix = "", effect = "allow", actions = '["list"]'): Row =>
  ({ principal: "user:" + actor.id, mountId, prefix, effect, actions });
function fixture(rows: Row[] = [row(1), row(2)], initial = user(), initialRules = [grant()]) {
  let current: User | null = initial, rules = initialRules, failedAccount = false, failedQuery = false, failedRules = false;
  let reads = 0, policyReads = 0, afterRules: (() => void) | null = null;
  let release!: () => void, entered!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const pending = new Promise<void>(resolve => { entered = resolve; });
  const calls: string[] = [], queries: Row[] = [];
  const db = {
    user: { findUnique: async ({ where }: Row) => {
      assert.deepEqual(plain(where), { id: actor.id }); reads++; calls.push("account");
      if (failedAccount) throw new Error("PUBLIC ACCOUNT UNAVAILABLE");
      return current && { ...current };
    } },
    kvIdentity: { findUnique: async () => ({ id: "public-identity", ownerId: actor.id,
      ownerSessionVersion: 7, revokedAt: null, expiresAt: new Date("2099-01-01T00:00:00.000Z") }) },
    kvPolicy: { findMany: async (query: Row) => {
      assert.deepEqual(plain(query), { where: { principal: "user:" + actor.id }, take: 257 });
      policyReads++; calls.push("rules"); if (failedRules) throw new Error("PUBLIC RULES UNAVAILABLE");
      const snapshot = rules.map(r => ({ ...r })); if (policyReads > 1) afterRules?.(); return snapshot;
    } },
    kvMount: { findMany: async (query: Row) => {
      queries.push(plain(query)); calls.push("list-start"); entered(); await held; calls.push("list-settled");
      if (failedQuery) throw new Error("PUBLIC LIST UNAVAILABLE");
      return rows.filter(item => (!query.where.id?.gt || item.id > query.where.id.gt) &&
        (!query.where.id?.in || query.where.id.in.includes(item.id))).slice(0, query.take);
    } },
  };
  const registry = new KvRegistry(db, ["public-namespace"], { historyNamespace: "public-history", guardedAdoption: false });
  return { registry, pending, release, calls, queries, get reads() { return reads; }, get policyReads() { return policyReads; },
    setUser: (next: User | null) => { current = next; }, setRules: (next: Row[]) => { rules = next; },
    failAccount: () => { failedAccount = true; }, failQuery: () => { failedQuery = true; },
    failRules: () => { failedRules = true; }, afterRules: (callback: () => void) => { afterRules = callback; } };
}
async function heldList(f: ReturnType<typeof fixture>, cursor?: string) {
  let settled = false;
  const result: Promise<Row> = f.registry.listMounts(actor, cursor).then((value: unknown) => { settled = true; return value as Row; });
  const outcome = result.then(value => ({ value, error: null }), error => ({ value: null, error }));
  await f.pending; assert.equal(settled, false); assert.equal(f.reads, 1);
  return { result, outcome };
}
for (const initial of [user(), user("write", false), user("readonly", false)])
  for (const count of [0, 2]) test("stable " + initial.role + "/" + initial.engineAdmin + " preserves " + count + " rows", async () => {
    const rows = Array.from({ length: count }, (_, i) => row(i + 1)), f = fixture(rows, initial), { result } = await heldList(f);
    f.release(); assert.deepEqual(plain(await result), { items: rows.map(r => ({ ...r, namespaces: ["public-namespace"] })), nextCursor: null });
  });
for (const initial of [user(), user("readonly", false)]) for (const count of [0, 2])
  for (const [label, next] of [["deleted", null], ["session", { ...user(), sessionVersion: 8 }]] as const)
    test("deferred " + initial.engineAdmin + "/" + count + " refuses " + label, async () => {
      const f = fixture(Array.from({ length: count }, (_, i) => row(i + 1)), initial), { outcome } = await heldList(f);
      f.setUser(next); f.release(); const settled = await outcome; assert.equal(settled.value, null); assert(deny(401)(settled.error));
    });
for (const next of [user("readonly"), user("write", false), user("readonly", false)]) for (const count of [0, 2])
  test("captured administration refuses " + next.role + "/" + next.engineAdmin + "/" + count, async () => {
    const f = fixture(Array.from({ length: count }, (_, i) => row(i + 1))), { outcome } = await heldList(f);
    f.setUser(next); f.release(); const settled = await outcome; assert.equal(settled.value, null); assert(deny(403)(settled.error));
  });
for (const [label, rules] of [["removed", []], ["read-only", [grant(null, "", "allow", '["read"]')]],
  ["other mount", [grant("public-999")]]] as const)
  test("withdrawn list grant " + label + " filters deferred rows", async () => {
    const f = fixture(undefined, user("write", false)), { result } = await heldList(f);
    f.setRules([...rules]); f.release(); assert.deepEqual(plain((await result).items), []); assert.equal(f.policyReads, 2);
  });
for (const mountId of [null, "public-001"]) test("fresh mount-wide deny " + mountId + " filters captured rows", async () => {
  const f = fixture(undefined, user("readonly", false)), { result } = await heldList(f);
  f.setRules([grant(), grant(mountId, "", "deny")]); f.release();
  assert.deepEqual(plain((await result).items.map((r: Row) => r.id)), mountId ? ["public-002"] : []);
});
test("nonempty-prefix denial retains mount metadata", async () => {
  const f = fixture(undefined, user("readonly", false), [grant(), grant(null, "public/path", "deny")]), { result } = await heldList(f);
  f.release(); assert.equal((await result).items.length, 2);
});
test("prefix list grant retains original mount enumeration semantics", async () => {
  const f = fixture(undefined, user("write", false), [grant("public-001", "public/path")]), { result } = await heldList(f);
  f.release(); assert.deepEqual(plain((await result).items.map((r: Row) => r.id)), ["public-001"]);
});
for (const initial of [user(), user("readonly", false)]) for (const count of [0, 99, 100, 101, 105])
  test("cursor " + initial.engineAdmin + "/" + count + " preserves original boundaries", async () => {
    const rows = Array.from({ length: count + 1 }, (_, i) => row(i)), f = fixture(rows, initial), { result } = await heldList(f, "public-000");
    f.release(); const page = await result;
    assert.equal(page.items.length, Math.min(count, 100)); assert.equal(page.nextCursor, count > 100 ? "public-100" : null);
    assert.deepEqual(f.queries, [{ where: { id: { gt: "public-000" } }, orderBy: { id: "asc" }, take: 101 }]);
  });
test("scoped promotion does not broaden captured query", async () => {
  const f = fixture(undefined, user("write", false), [grant("public-001")]), { result } = await heldList(f);
  f.setUser(user()); f.release(); assert.deepEqual(plain((await result).items.map((r: Row) => r.id)), ["public-001"]);
  assert.deepEqual(f.queries[0].where, { id: { in: ["public-001"] } });
});
test("fresh partial grant withdrawal keeps only still permitted mount", async () => {
  const f = fixture(undefined, user("write", false), [grant("public-001"), grant("public-002")]), { result } = await heldList(f);
  f.setRules([grant("public-002")]); f.release(); assert.deepEqual(plain((await result).items.map((r: Row) => r.id)), ["public-002"]);
});
test("wildcard narrowed to exact mount filters captured page", async () => {
  const f = fixture(undefined, user("write", false)), { result } = await heldList(f);
  f.setRules([grant("public-002")]); f.release(); assert.deepEqual(plain((await result).items.map((r: Row) => r.id)), ["public-002"]);
});
test("new wildcard cannot broaden exact captured query", async () => {
  const f = fixture(undefined, user("write", false), [grant("public-001")]), { result } = await heldList(f);
  f.setRules([grant()]); f.release(); assert.deepEqual(plain((await result).items.map((r: Row) => r.id)), ["public-001"]);
});
test("scoped role-only demotion retains permitted metadata", async () => {
  const f = fixture(undefined, user("write", false)), { result } = await heldList(f);
  f.setUser(user("readonly", false)); f.release(); assert.equal((await result).items.length, 2);
});
test("later request uses restored administration without stamped revocation", async () => {
  const f = fixture(), { outcome } = await heldList(f); f.setUser(user("readonly")); f.release();
  assert(deny(403)((await outcome).error)); f.setUser(user()); assert.equal((await f.registry.listMounts(actor)).items.length, 2);
});
for (const initial of [user(), user("readonly", false)]) test("account outage at release fails closed " + initial.engineAdmin, async () => {
  const f = fixture(undefined, initial), { outcome } = await heldList(f); f.failAccount(); f.release();
  const settled = await outcome; assert.equal(settled.value, null); assert.match(settled.error.message, /PUBLIC ACCOUNT UNAVAILABLE/); assert.equal(f.queries.length, 1);
});
test("policy outage at release fails closed without retry", async () => {
  const f = fixture(undefined, user("readonly", false)), { outcome } = await heldList(f); f.failRules(); f.release();
  const settled = await outcome; assert.equal(settled.value, null); assert.match(settled.error.message, /PUBLIC RULES UNAVAILABLE/); assert.equal(f.queries.length, 1);
});
test("malformed fresh policy fails closed", async () => {
  const f = fixture(undefined, user("readonly", false)), { outcome } = await heldList(f);
  f.setRules([grant(null, "", "allow", '["unknown"]')]); f.release(); const settled = await outcome;
  assert.equal(settled.value, null); assert(deny(503)(settled.error));
});
for (const next of [null, { ...user(), sessionVersion: 8 }]) test("invalid initial account refuses before query " + !!next, async () => {
  const f = fixture(); f.setUser(next); await assert.rejects(f.registry.listMounts(actor), deny(401)); assert.equal(f.queries.length, 0);
});
test("automation cannot enumerate mounts", async () => {
  const f = fixture(); await assert.rejects(f.registry.listMounts({ ...actor, identityId: "public-identity" }), deny(403)); assert.equal(f.queries.length, 0);
});
test("query failure does not retry or release metadata", async () => {
  const f = fixture(), { outcome } = await heldList(f); f.failQuery(); f.release(); const settled = await outcome;
  assert.equal(settled.value, null); assert.match(settled.error.message, /PUBLIC LIST UNAVAILABLE/); assert.equal(f.queries.length, 1);
});
test("malformed namespace JSON remains a refusal", async () => {
  const f = fixture([{ ...row(1), namespaces: "invalid-json" }]), { outcome } = await heldList(f); f.release(); assert.equal((await outcome).value, null);
});
test("stable administration retains its policy bypass", async () => {
  const f = fixture(), { result } = await heldList(f); f.setRules([grant(null, "", "deny")]); f.release(); assert.equal((await result).items.length, 2);
});
test("administration restored before release uses current authority", async () => {
  const f = fixture(), { result } = await heldList(f); f.setUser(user("readonly")); f.setUser(user()); f.release(); assert.equal((await result).items.length, 2);
});
for (const next of [null, { ...user(), sessionVersion: 8 }]) test("account changed during fresh policy read refuses " + !!next, async () => {
  const f = fixture(undefined, user("readonly", false)), { outcome } = await heldList(f);
  f.afterRules(() => f.setUser(next)); f.release(); const settled = await outcome;
  assert.equal(settled.value, null); assert(deny(401)(settled.error));
});
test("fresh policy count overflow still fails closed", async () => {
  const f = fixture(undefined, user("readonly", false)), { outcome } = await heldList(f);
  f.setRules(Array.from({ length: 257 }, () => grant())); f.release(); const settled = await outcome;
  assert.equal(settled.value, null); assert(deny(503)(settled.error));
});
