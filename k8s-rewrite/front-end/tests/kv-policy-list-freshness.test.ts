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
const forbidden = () => { throw new Error("Outside public policy-list controls"); };
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
const row = (index: number): Row => ({ id: `public-${String(index).padStart(3, "0")}`,
  principal: "user:public-writer", mountId: "public-mount", prefix: "public/path", effect: "allow",
  actions: '["list","read"]', revision: 3, createdAt: new Date("2026-01-01T00:00:00.000Z") });
function fixture(rows: Row[] = [row(1), row(2)]) {
  let current: User | null = user(), failedAccount = false, failedQuery = false, reads = 0;
  let release!: () => void, entered!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const pending = new Promise<void>(resolve => { entered = resolve; });
  const calls: string[] = [], queries: Row[] = [];
  const db = {
    user: { findUnique: async ({ where }: Row) => {
      assert.deepEqual(plain(where), { id: actor.id }); reads++; calls.push("current-account");
      if (failedAccount) throw new Error("PUBLIC ACCOUNT UNAVAILABLE");
      return current && { ...current };
    } },
    kvIdentity: { findUnique: async () => ({ id: "public-identity", ownerId: actor.id,
      ownerSessionVersion: 7, revokedAt: null, expiresAt: new Date("2099-01-01T00:00:00.000Z") }) },
    kvPolicy: { findMany: async (query: Row) => {
      queries.push(plain(query)); calls.push("list-start"); entered(); await held; calls.push("list-settled");
      if (failedQuery) throw new Error("PUBLIC LIST UNAVAILABLE");
      return rows.filter(item => !query.where.id || item.id > query.where.id.gt).slice(0, query.take);
    } },
  };
  const registry = new KvRegistry(db, ["public-namespace"], { historyNamespace: "public-history", guardedAdoption: false });
  return { registry, pending, release, calls, queries, get reads() { return reads; },
    setUser: (next: User | null) => { current = next; }, failAccount: () => { failedAccount = true; },
    failQuery: () => { failedQuery = true; } };
}
async function heldList(f: ReturnType<typeof fixture>, cursor?: string) {
  let settled = false;
  const result: Promise<Row> = f.registry.listPolicies(actor, cursor).then((value: unknown) => { settled = true; return value as Row; });
  const outcome = result.then(value => ({ value, error: null }), error => ({ value: null, error }));
  await f.pending; assert.equal(settled, false); assert.equal(f.reads, 1);
  return { result, outcome };
}
for (const count of [0, 2]) test(`stable administration preserves ${count}-row policy metadata and parsed actions`, async () => {
  const rows = Array.from({ length: count }, (_, i) => row(i + 1));
  const f = fixture(rows), { result } = await heldList(f); f.release(); const page = await result;
  assert.deepEqual(plain(page), { items: rows.map(p => ({ ...plain(p), actions: ["list", "read"] })), nextCursor: null });
  assert.deepEqual(f.queries, [{ where: {}, orderBy: { id: "asc" }, take: 101 }]);
});
for (const [label, next, status] of [
  ["deleted account", null, 401], ["changed session", { ...user(), sessionVersion: 8 }, 401],
  ["role withdrawn", user("readonly"), 403], ["admin flag withdrawn", user("write", false), 403],
  ["both withdrawn", user("readonly", false), 403],
] as const) for (const count of [0, 2]) test(`deferred ${count}-row policy list refuses ${label}`, async () => {
  const f = fixture(Array.from({ length: count }, (_, i) => row(i + 1))), { outcome } = await heldList(f);
  f.setUser(next); f.release(); const settled = await outcome;
  assert.equal(settled.value, null); assert(deny(status)(settled.error));
  assert.equal(f.queries.length, 1); assert.equal(f.reads, 2);
});
for (const count of [0, 99, 100, 101, 105]) test(`cursor preserves ${count} available-row boundary`, async () => {
  const rows = Array.from({ length: count + 1 }, (_, i) => row(i));
  const f = fixture(rows), { result } = await heldList(f, "public-000"); f.release(); const page = await result;
  assert.equal(page.items.length, Math.min(count, 100)); assert.equal(page.nextCursor, count > 100 ? "public-100" : null);
  assert.deepEqual(f.queries, [{ where: { id: { gt: "public-000" } }, orderBy: { id: "asc" }, take: 101 }]);
  assert.deepEqual(plain(page.items.map((p: Row) => p.id)), rows.slice(1, 101).map(p => p.id));
});
for (const [label, next, status] of [
  ["absent account", null, 401], ["changed session", { ...user(), sessionVersion: 8 }, 401],
  ["readonly flag-holder", user("readonly"), 403], ["scoped writer", user("write", false), 403],
] as const) test(`initial ${label} is refused before the policy query`, async () => {
  const f = fixture(); f.setUser(next); await assert.rejects(f.registry.listPolicies(actor), deny(status)); assert.equal(f.queries.length, 0);
});
test("automation cannot list policies even with an administrator owner", async () => {
  const f = fixture(); await assert.rejects(f.registry.listPolicies({ ...actor, identityId: "public-identity" }), deny(403));
  assert.equal(f.queries.length, 0);
});
test("account read failure after query refuses the page without retry", async () => {
  const f = fixture(), { outcome } = await heldList(f); f.failAccount(); f.release(); const settled = await outcome;
  assert.equal(settled.value, null); assert.match(settled.error.message, /PUBLIC ACCOUNT UNAVAILABLE/);
  assert.equal(f.queries.length, 1); assert.equal(f.reads, 2);
});
test("query failure refuses the page without retry", async () => {
  const f = fixture(), { outcome } = await heldList(f); f.failQuery(); f.release(); const settled = await outcome;
  assert.equal(settled.value, null); assert.match(settled.error.message, /PUBLIC LIST UNAVAILABLE/); assert.equal(f.queries.length, 1);
});
test("a later request can use restored administration without persisted revocation", async () => {
  const f = fixture(), { outcome } = await heldList(f); f.setUser(user("readonly")); f.release();
  assert(deny(403)((await outcome).error)); f.setUser(user()); const page = await f.registry.listPolicies(actor);
  assert.equal(page.items.length, 2); assert.equal(f.queries.length, 2); assert.equal(f.reads, 4);
});
test("administration restored before release is judged by current authority", async () => {
  const f = fixture(), { result } = await heldList(f); f.setUser(user("readonly")); f.setUser(user()); f.release();
  assert.equal((await result).items.length, 2); assert.equal(f.queries.length, 1);
});
test("malformed policy actions still fail closed", async () => {
  const f = fixture([{ ...row(1), actions: '["unknown-action"]' }]), { outcome } = await heldList(f); f.release();
  assert.equal((await outcome).value, null); assert((await outcome).error instanceof contract.KvError);
});
