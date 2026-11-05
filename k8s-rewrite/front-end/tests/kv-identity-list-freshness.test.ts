import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// PUBLIC synthetic source controls: actual registry/current/revision code,
// deferred metadata reads and fresh public account doubles. No ORM, server,
// native/credential/recovery module, transaction, network or subprocess runs.
type Row = Record<string, any>;
type User = { id: string; sessionVersion: number; role: string; engineAdmin: boolean };
const actor = { id: "public-owner", sessionVersion: 7 };
const originalUser = (role = "write", engineAdmin = false): User => ({ ...actor, role, engineAdmin });
const plain = (value: unknown): any => JSON.parse(JSON.stringify(value));
const forbidden = () => { throw new Error("Outside public identity-list controls"); };
class SecretError extends Error {
  constructor(readonly status: number, message: string) { super(message); }
}
function evaluate(file: string, dependencies: Row, source = readFileSync(file, "utf8")) {
  const compiledModule = { exports: {} as any };
  const output = ts.transpileModule(source, { fileName: file, compilerOptions: {
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
const dependencies = {
  "./kv-contract": contract, "./cluster-secrets": cluster, "./kv-identity-revision": revisions,
  "./kv-credentials": { issueCredential: forbidden, hashMatches: forbidden, presentedCredential: forbidden },
  "./kv-legacy-access": Object.fromEntries(["acknowledgeLegacyImpact", "legacyImpact", "legacyImpactPage", "readLegacyAliases"].map(name => [name, forbidden])),
};
const { KvRegistry } = evaluate("src/lib/kv-registry.ts", dependencies);
const deny = (status: number) => (error: any) => error instanceof contract.KvError && error.status === status;
const metadataKeys = ["id", "ownerId", "name", "expiresAt", "revokedAt", "createdAt"];
const row = (index: number, ownerId = actor.id): Row => ({
  id: `public-${String(index).padStart(3, "0")}`, ownerId, name: `public-name-${index}`,
  expiresAt: new Date("2099-01-01T00:00:00.000Z"), revokedAt: null,
  createdAt: new Date("2026-01-01T00:00:00.000Z"),
  credentialHash: "PUBLIC-HASH-SENTINEL", ownerSessionVersion: 7,
});
function fixture(initial = originalUser(), rows: Row[] = [row(1), row(2, "public-peer")], Registry = KvRegistry) {
  let user: User | null = { ...initial }, failRead = false, reads = 0;
  let release!: () => void, entered!: () => void, rejectQuery = false;
  const held = new Promise<void>(resolve => { release = resolve; });
  const pending = new Promise<void>(resolve => { entered = resolve; });
  const calls: string[] = [], queries: Row[] = [];
  const db = {
    user: { findUnique: async ({ where }: Row) => {
      assert.deepEqual(plain(where), { id: actor.id }); calls.push("current-account"); reads++;
      if (failRead) throw new Error("PUBLIC ACCOUNT UNAVAILABLE");
      return user && { ...user };
    } },
    kvIdentity: {
      findUnique: async () => ({ ...row(3), ownerSessionVersion: actor.sessionVersion }),
      findMany: async (query: Row) => {
        calls.push("list-start"); queries.push(plain(query)); entered(); await held;
        calls.push("list-settled"); if (rejectQuery) throw new Error("PUBLIC LIST UNAVAILABLE");
        assert.deepEqual(Object.keys(query.select).sort(), [...metadataKeys].sort());
        assert(Object.values(query.select).every(value => value === true));
        return rows.filter(item => (!query.where.ownerId || item.ownerId === query.where.ownerId) &&
          (!query.where.id || item.id > query.where.id.gt)).slice(0, query.take)
          .map(item => Object.fromEntries(metadataKeys.map(key => [key, item[key]])));
      },
    },
  };
  const registry = new Registry(db, ["public-namespace"], { historyNamespace: "public-history", guardedAdoption: false });
  return { registry, calls, queries, pending, release, get reads() { return reads; },
    setUser: (next: User | null) => { user = next; }, failAccount: () => { failRead = true; },
    failQuery: () => { rejectQuery = true; } };
}
async function heldList(f: ReturnType<typeof fixture>, cursor?: string) {
  let settled = false;
  const result: Promise<Row> = f.registry.listIdentities(actor, cursor).then((value: unknown) => { settled = true; return value as Row; });
  // Attach rejection handling before allowing the deferred read to settle.
  const outcome = result.then(value => ({ value, error: null }), error => ({ value: null, error }));
  await f.pending; assert.equal(settled, false); assert.equal(f.reads, 1);
  return { result, outcome };
}
for (const [label, role, admin, all] of [
  ["writer owner", "write", false, false], ["readonly owner", "readonly", false, false],
  ["readonly with admin flag", "readonly", true, false], ["effective administrator", "write", true, true],
] as const) test(`stable ${label} retains exact scope and metadata`, async () => {
  const f = fixture(originalUser(role, admin)), { result } = await heldList(f); f.release();
  const page = await result;
  assert.deepEqual(plain(f.queries), [{ where: all ? {} : { ownerId: actor.id },
    select: Object.fromEntries(metadataKeys.map(key => [key, true])), orderBy: { id: "asc" }, take: 101 }]);
  assert.equal(page.items.length, all ? 2 : 1); assert.equal(page.nextCursor, null);
  for (const item of page.items) {
    assert.deepEqual(Object.keys(item).sort(), [...metadataKeys, "revision"].sort());
    assert.equal(item.revision, revisions.identityRevision(item)); assert.match(item.revision, /^[0-9a-f]{64}$/);
  }
  assert.deepEqual(f.calls, ["current-account", "list-start", "list-settled", "current-account"]);
  assert(!JSON.stringify(page).includes("PUBLIC-HASH-SENTINEL")); assert(!JSON.stringify(page).includes("ownerSessionVersion"));
});
for (const admin of [false, true]) for (const [label, next] of [
  ["deleted account", null], ["changed session", { ...originalUser("write", admin), sessionVersion: 8 }],
] as const) test(`${admin ? "admin" : "owner"} deferred list refuses ${label} at release`, async () => {
  const f = fixture(originalUser("write", admin)), { outcome } = await heldList(f);
  f.setUser(next); f.release(); const settled = await outcome;
  assert.equal(settled.value, null); assert(deny(401)(settled.error));
  assert.equal(f.queries.length, 1); assert.equal(f.reads, 2);
});
for (const [label, next] of [
  ["role withdrawn", originalUser("readonly", true)], ["admin flag withdrawn", originalUser("write", false)],
  ["both withdrawn", originalUser("readonly", false)],
] as const) test(`deferred administrative list refuses ${label}, including an empty page`, async () => {
  for (const rows of [[row(1), row(2, "public-peer")], []]) {
    const f = fixture(originalUser("write", true), rows), { outcome } = await heldList(f);
    f.setUser(next); f.release(); const settled = await outcome;
    assert.equal(settled.value, null); assert(deny(403)(settled.error)); assert.equal(f.queries.length, 1);
  }
});
for (const [label, before, after] of [
  ["owner demotion", originalUser(), originalUser("readonly")],
  ["owner repromotion", originalUser("readonly"), originalUser()],
  ["owner acquires administration", originalUser(), originalUser("write", true)],
  ["readonly flag-holder promoted", originalUser("readonly", true), originalUser("write", true)],
  ["readonly admin flag removed", originalUser("readonly", true), originalUser("readonly")],
] as const) test(`${label} retains the originally captured owner-only query`, async () => {
  const f = fixture(before), { result } = await heldList(f); f.setUser(after); f.release();
  const page = await result; assert.deepEqual(plain(page.items.map((item: Row) => item.ownerId)), [actor.id]);
  assert.equal(f.queries[0].where.ownerId, actor.id); assert.equal(f.queries.length, 1); assert.equal(f.reads, 2);
});
for (const count of [0, 99, 100, 101, 105]) for (const admin of [false, true])
  test(`${admin ? "admin" : "owner"} cursor page preserves ${count} available-row boundary`, async () => {
    const rows = Array.from({ length: count }, (_, i) => row(i + 1));
    rows.unshift(row(0), row(0, "public-peer"));
    const f = fixture(originalUser("write", admin), rows), { result } = await heldList(f, "public-000"); f.release();
    const page = await result;
    assert.equal(page.items.length, Math.min(count, 100));
    assert.equal(page.nextCursor, count > 100 ? "public-100" : null);
    assert.deepEqual(plain(f.queries[0].where.id), { gt: "public-000" });
    assert.equal(f.queries[0].take, 101); assert.equal(f.queries.length, 1); assert.equal(f.reads, 2);
  });
test("unchanged session cannot rescue an absent account before the query", async () => {
  const f = fixture(); f.setUser(null); await assert.rejects(f.registry.listIdentities(actor), deny(401));
  assert.equal(f.queries.length, 0);
});
test("automation cannot list identities even when its owner is an administrator", async () => {
  const f = fixture(originalUser("write", true));
  await assert.rejects(f.registry.listIdentities({ ...actor, identityId: "public-003" }), deny(403));
  assert.equal(f.queries.length, 0);
});
test("account read failure after the list never releases a page or retries", async () => {
  const f = fixture(), { outcome } = await heldList(f); f.failAccount(); f.release();
  const settled = await outcome; assert.equal(settled.value, null); assert.match(settled.error.message, /PUBLIC ACCOUNT UNAVAILABLE/);
  assert.equal(f.queries.length, 1); assert.equal(f.reads, 2);
});
test("list failure never releases metadata or retries", async () => {
  const f = fixture(), { outcome } = await heldList(f); f.failQuery(); f.release();
  const settled = await outcome; assert.equal(settled.value, null); assert.match(settled.error.message, /PUBLIC LIST UNAVAILABLE/);
  assert.equal(f.queries.length, 1); assert.equal(f.reads, 1);
});
test("a later request can use restored administration without persisting revocation", async () => {
  const f = fixture(originalUser("write", true)), { outcome } = await heldList(f);
  f.setUser(originalUser("readonly", true)); f.release(); assert(deny(403)((await outcome).error));
  f.setUser(originalUser("write", true)); const page = await f.registry.listIdentities(actor);
  assert.equal(page.items.length, 2); assert.equal(f.queries.length, 2); assert.equal(f.reads, 4);
});
