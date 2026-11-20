import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// PUBLIC synthetic source controls only: real registry/current and policy parser,
// deferred metadata and account/identity doubles. No ORM/server/native/credential/
// recovery/transaction/network/subprocess execution.
type Row = Record<string, any>;
const actor = { id: "public-owner", sessionVersion: 7 };
const automation = { ...actor, identityId: "public-identity" };
const user = (role = "write", engineAdmin = false): Row => ({ ...actor, role, engineAdmin });
const identity = (): Row => ({ id: automation.identityId, ownerId: actor.id, ownerSessionVersion: 7,
  revokedAt: null, expiresAt: new Date("2099-01-01T00:00:00Z") });
const plain = (v: unknown): any => JSON.parse(JSON.stringify(v));
const forbidden = () => { throw new Error("Outside public path-list controls"); };
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
  "./kv-legacy-access": Object.fromEntries(["acknowledgeLegacyImpact", "legacyImpact", "legacyImpactPage", "readLegacyAliases"].map(n => [n, forbidden])),
});
const denied = (status: number) => (e: any) => e instanceof contract.KvError && e.status === status;
const grant = (mountId: string | null = null, prefix = "", effect = "allow", actions = '["list"]'): Row => ({ mountId, prefix, effect, actions });
const row = (i: number, path = "apps/api/" + i, mountId = "public-mount"): Row => ({
  id: "public-" + String(i).padStart(3, "0"), mountId, path, namespace: "public-namespace", name: "public-secret-" + i,
  revision: 3, retention: 20, fields: [{ id: "public-field-" + i, field: "username", key: "user_name" }],
});
function fixture(rows: Row[] = [row(1), row(2)], who: typeof actor | typeof automation = actor, initial = user(), owner = [grant()], token = [grant()]) {
  let account: Row | null = initial, credential: Row | null = identity(), ownerRules = owner, tokenRules = token;
  const reads = { account: 0, identity: 0, owner: 0, token: 0 };
  const failures = new Set<string>(), callbacks = new Map<string, () => void>(), queries: Row[] = [];
  let release!: () => void, entered!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const pending = new Promise<void>(resolve => { entered = resolve; });
  const db = {
    user: { findUnique: async ({ where }: Row) => {
      assert.deepEqual(plain(where), { id: actor.id }); reads.account++;
      if (failures.has("account")) throw new Error("PUBLIC ACCOUNT UNAVAILABLE"); return account && { ...account };
    } },
    kvIdentity: { findUnique: async ({ where }: Row) => {
      assert.deepEqual(plain(where), { id: automation.identityId }); reads.identity++;
      if (failures.has("identity")) throw new Error("PUBLIC IDENTITY UNAVAILABLE"); return credential && { ...credential };
    } },
    kvPolicy: { findMany: async (query: Row) => {
      const kind = query.where.principal === "user:" + actor.id ? "owner" : "token";
      assert.deepEqual(plain(query), { where: { principal: kind === "owner" ? "user:" + actor.id : "identity:" + automation.identityId }, take: 257 });
      reads[kind]++; if (failures.has(kind)) throw new Error("PUBLIC " + kind.toUpperCase() + " RULES UNAVAILABLE");
      const snapshot = (kind === "owner" ? ownerRules : tokenRules).map(r => ({ ...r }));
      callbacks.get(kind + (reads[kind] > 1 ? "Fresh" : "Initial"))?.(); return snapshot;
    } },
    kvPath: { findMany: async (query: Row) => {
      queries.push(plain(query)); entered(); await held;
      if (failures.has("query")) throw new Error("PUBLIC QUERY UNAVAILABLE");
      const matches = (item: Row, where: Row): boolean => (!where.id?.gt || item.id > where.id.gt) &&
        (!where.mountId || item.mountId === where.mountId) && (!where.path || (typeof where.path === "string" ? item.path === where.path : item.path.startsWith(where.path.startsWith))) &&
        (!where.OR || where.OR.some((part: Row) => matches(item, part)));
      return rows.filter(item => matches(item, query.where)).slice(0, query.take);
    } },
  };
  const registry = new KvRegistry(db, ["public-namespace"], { historyNamespace: "public-history", guardedAdoption: false });
  return { registry, who, pending, release, queries, reads, fail: (kind: string) => failures.add(kind),
    setUser: (next: Row | null) => { account = next; }, setIdentity: (next: Row | null) => { credential = next; },
    setOwner: (next: Row[]) => { ownerRules = next; }, setToken: (next: Row[]) => { tokenRules = next; },
    after: (kind: string, cb: () => void) => callbacks.set(kind, cb) };
}
async function heldList(f: ReturnType<typeof fixture>, mount?: string, cursor?: string) {
  let settled = false;
  const result: Promise<Row> = f.registry.listPaths(f.who, mount, cursor).then((value: Row) => { settled = true; return value; });
  const outcome = result.then(value => ({ value, error: null }), error => ({ value: null, error }));
  await f.pending; assert.equal(settled, false); assert.equal(f.reads.account, 1);
  return { result, outcome };
}
for (const initial of [user(), user("readonly"), user("write", true)]) for (const count of [0, 2])
  test("stable human " + initial.role + "/" + initial.engineAdmin + "/" + count, async () => {
    const rows = Array.from({ length: count }, (_, i) => row(i)), f = fixture(rows, actor, initial), { result } = await heldList(f);
    f.release(); assert.deepEqual(plain(await result), { items: rows, nextCursor: null });
  });
for (const count of [0, 2]) test("stable automation " + count, async () => {
  const rows = Array.from({ length: count }, (_, i) => row(i)), f = fixture(rows, automation), { result } = await heldList(f);
  f.release(); assert.deepEqual(plain(await result), { items: rows, nextCursor: null });
});
for (const who of [actor, automation]) for (const count of [0, 2]) for (const next of [null, { ...user(), sessionVersion: 8 }])
  test("deferred account withdrawal " + ("identityId" in who) + "/" + count + "/" + !!next, async () => {
    const f = fixture(Array.from({ length: count }, (_, i) => row(i)), who), { outcome } = await heldList(f);
    f.setUser(next); f.release(); const o = await outcome; assert.equal(o.value, null); assert(denied(401)(o.error));
  });
const invalidIdentities = [null, { ...identity(), ownerId: "other" }, { ...identity(), ownerSessionVersion: 8 },
  { ...identity(), revokedAt: new Date() }, { ...identity(), expiresAt: new Date(0) }];
for (const [index, next] of invalidIdentities.entries()) for (const count of [0, 2])
  test("deferred identity withdrawal " + index + "/" + count, async () => {
    const f = fixture(Array.from({ length: count }, (_, i) => row(i)), automation), { outcome } = await heldList(f);
    f.setIdentity(next); f.release(); const o = await outcome; assert.equal(o.value, null); assert(denied(401)(o.error));
  });
for (const who of [actor, automation]) for (const [label, rules] of [["removed", []], ["read", [grant(null, "", "allow", '["read"]')]],
  ["mount", [grant("other")]], ["prefix", [grant(null, "other")]]] as const)
  test("fresh owner grant " + ("identityId" in who) + "/" + label, async () => {
    const f = fixture(undefined, who), { result } = await heldList(f); f.setOwner([...rules]); f.release(); assert.deepEqual(plain((await result).items), []);
  });
for (const who of [actor, automation]) for (const mount of [null, "public-mount"]) test("fresh owner deny " + ("identityId" in who) + "/" + mount, async () => {
  const f = fixture(undefined, who), { result } = await heldList(f); f.setOwner([grant(), grant(mount, "apps/api", "deny")]); f.release(); assert.deepEqual(plain((await result).items), []);
});
for (const [label, rules] of [["removed", []], ["read", [grant(null, "", "allow", '["read"]')]],
  ["mount", [grant("other")]], ["prefix", [grant(null, "other")]], ["deny", [grant(), grant(null, "apps/api", "deny")]]] as const)
  test("fresh token policy " + label, async () => {
    const f = fixture(undefined, automation), { result } = await heldList(f); f.setToken([...rules]); f.release(); assert.deepEqual(plain((await result).items), []);
  });
for (const admin of [false, true]) test("human role-only demotion retains permitted metadata " + admin, async () => {
  const f = fixture(undefined, actor, user("write", admin)), { result } = await heldList(f);
  f.setUser(user("readonly", admin)); f.release(); assert.equal((await result).items.length, 2);
});
for (const count of [0, 2]) test("automation owner demotion refuses " + count, async () => {
  const f = fixture(Array.from({ length: count }, (_, i) => row(i)), automation), { outcome } = await heldList(f);
  f.setUser(user("readonly")); f.release(); const o = await outcome; assert.equal(o.value, null); assert(denied(401)(o.error));
});
for (const who of [actor, automation]) for (const count of [0, 99, 100, 101, 105]) test("cursor " + ("identityId" in who) + "/" + count, async () => {
  const rows = Array.from({ length: count + 1 }, (_, i) => row(i)), f = fixture(rows, who), { result } = await heldList(f, "public-mount", "public-000");
  f.release(); const page = await result;
  assert.equal(page.items.length, Math.min(count, 100)); assert.equal(page.nextCursor, count > 100 ? "public-100" : null);
  assert.deepEqual(f.queries, [{ where: { mountId: "public-mount", id: { gt: "public-000" } }, include: { fields: true }, orderBy: { id: "asc" }, take: 101 }]);
});
for (const who of [actor, automation]) test("prefix boundary and field metadata " + ("identityId" in who), async () => {
  const rows = [row(1, "apps/api"), row(2, "apps/api/child"), row(3, "apps/apiculture"), row(4, "apps/api-other")];
  const f = fixture(rows, who, user(), [grant("public-mount", "apps/api")]), { result } = await heldList(f);
  f.release(); assert.deepEqual(plain((await result).items), rows.slice(0, 2));
  assert.deepEqual(f.queries[0].where, { OR: [{ mountId: "public-mount", OR: [{ path: "apps/api" }, { path: { startsWith: "apps/api/" } }] }] });
});
for (const who of [actor, automation]) test("new wildcard does not broaden captured SQL " + ("identityId" in who), async () => {
  const rows = [row(1, "apps/api"), row(2, "other")], f = fixture(rows, who, user(), [grant(null, "apps/api")]), { result } = await heldList(f);
  f.setOwner([grant()]); f.setUser(user("write", true)); f.release(); assert.deepEqual(plain((await result).items), [rows[0]]);
});
for (const who of [actor, automation]) test("fresh partial owner grant " + ("identityId" in who), async () => {
  const rows = [row(1, "apps/api"), row(2, "other")], f = fixture(rows, who), { result } = await heldList(f);
  f.setOwner([grant(null, "other")]); f.release(); assert.deepEqual(plain((await result).items), [rows[1]]);
});
test("fresh identity remains intersection with owner", async () => {
  const rows = [row(1, "apps/api"), row(2, "other")], f = fixture(rows, automation), { result } = await heldList(f);
  f.setOwner([grant(), grant(null, "other", "deny")]); f.setToken([grant(null, "other")]); f.release(); assert.deepEqual(plain((await result).items), []);
});
for (const who of [actor, automation]) for (const next of [null, { ...user(), sessionVersion: 8 }]) test("invalid initial account " + ("identityId" in who) + "/" + !!next, async () => {
  const f = fixture(undefined, who); f.setUser(next); await assert.rejects(f.registry.listPaths(who), denied(401)); assert.equal(f.queries.length, 0);
});
for (const [index, next] of invalidIdentities.entries()) test("invalid initial identity " + index, async () => {
  const f = fixture(undefined, automation); f.setIdentity(next); await assert.rejects(f.registry.listPaths(automation), denied(401)); assert.equal(f.queries.length, 0);
});
for (const kind of ["account", "identity", "owner", "token", "query"]) test("release outage " + kind, async () => {
  const f = fixture(undefined, automation), { outcome } = await heldList(f); f.fail(kind); f.release(); const o = await outcome;
  assert.equal(o.value, null); assert.match(o.error.message, /PUBLIC .* UNAVAILABLE/); assert.equal(f.queries.length, 1);
});
for (const kind of ["owner", "token"]) for (const [label, rules] of [["actions", [grant(null, "", "allow", '["unknown"]')]],
  ["effect", [grant(null, "", "broken")]], ["prefix", [grant(null, "a//b")]], ["count", Array.from({ length: 257 }, () => grant())]] as const)
  test("fresh malformed " + kind + "/" + label, async () => {
    const f = fixture(undefined, automation), { outcome } = await heldList(f);
    if (kind === "owner") f.setOwner([...rules]); else f.setToken([...rules]); f.release(); const o = await outcome;
    assert.equal(o.value, null); assert(denied(503)(o.error));
  });
for (const who of [actor, automation]) for (const next of [null, { ...user(), sessionVersion: 8 }]) test("no grants still checks final account " + ("identityId" in who) + "/" + !!next, async () => {
  const f = fixture(undefined, who, user(), []); f.after("ownerInitial", () => f.setUser(next));
  await assert.rejects(f.registry.listPaths(who), denied(401)); assert.equal(f.queries.length, 0);
});
for (const kind of ["ownerFresh", "tokenFresh"]) for (const next of [null, { ...user(), sessionVersion: 8 }])
  test("account withdrawal during fresh policy " + kind + "/" + !!next, async () => {
    const f = fixture(undefined, automation), { outcome } = await heldList(f); f.after(kind, () => f.setUser(next)); f.release(); const o = await outcome;
    assert.equal(o.value, null); assert(denied(401)(o.error));
  });
for (const [index, next] of invalidIdentities.entries()) test("identity withdrawal during fresh policy " + index, async () => {
  const f = fixture(undefined, automation), { outcome } = await heldList(f); f.after("tokenFresh", () => f.setIdentity(next)); f.release(); const o = await outcome;
  assert.equal(o.value, null); assert(denied(401)(o.error));
});
test("later repromotion uses current identity without stamped revocation", async () => {
  const f = fixture(undefined, automation), { outcome } = await heldList(f); f.setUser(user("readonly")); f.release(); assert(denied(401)((await outcome).error));
  f.setUser(user()); assert.equal((await f.registry.listPaths(automation)).items.length, 2);
});
test("engine administration does not bypass path policies", async () => {
  const f = fixture(undefined, actor, user("write", true), []); assert.deepEqual(plain(await f.registry.listPaths(actor)), { items: [], nextCursor: null }); assert.equal(f.queries.length, 0);
});
test("cursor follows captured unfiltered page after fresh denial", async () => {
  const f = fixture(Array.from({ length: 101 }, (_, i) => row(i))), { result } = await heldList(f);
  f.setOwner([]); f.release(); assert.deepEqual(plain(await result), { items: [], nextCursor: "public-099" });
});
