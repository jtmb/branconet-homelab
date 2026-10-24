import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { runInNewContext } from "node:vm";
import { Prisma, PrismaClient } from "@prisma/client";
import ts from "typescript";

// Finite PUBLIC synthetic transport controls. Only a new owned temporary DB is
// opened. Native/HTTP/credentials/legacy dependencies remain inert refusals.
type Row = Record<string, any>;
const forbidden = () => { throw Error("Outside selected-path synthetic transport scope"); };
class SecretError extends Error { constructor(readonly status: number, message: string) { super(message); } }
function evaluate(file: string, dependencies: Row) {
  const m = { exports: {} as any };
  const output = ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  runInNewContext(output, { module: m, exports: m.exports, Buffer, Date, JSON,
    require: (name: string) => { assert(Object.hasOwn(dependencies, name), `Unselected dependency: ${name}`); return dependencies[name]; },
  }, { filename: file, timeout: 5000 });
  return m.exports;
}
const cluster = { SecretError, validateTarget: forbidden };
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
const plain = (value: unknown) => JSON.parse(JSON.stringify(value));
const denied = (error: unknown) => error instanceof contract.KvError && (error as SecretError).status === 401;
const sql = 'SELECT u."id", u."sessionVersion", u."role", i."id" AS "identityId", i."ownerId", i."ownerSessionVersion", i."revokedAt", i."expiresAt" FROM "users" AS u LEFT JOIN "kv_identities" AS i ON i."id" = ? WHERE u."id" = ? LIMIT 1';
const owner = "public-owner' OR 1=1 --", identityId = "public-identity'; DROP TABLE users; --";
const actor = { id: owner, sessionVersion: 7, identityId };
const config = { historyNamespace: "public-history", retention: 20, maxRetention: 100, guardedAdoption: false };
const metadata = { id: "public-path", mountId: "public-mount", path: "apps/api", namespace: "public-namespace",
  name: "public-secret", retention: 20, revision: 17, createdAt: "public-created-at",
  fields: [{ field: "public_field", key: "public_key" }, { field: "second_field", key: "second_key" }] };

test("finite selected-path Prisma/SQLite transport (two public synthetic tables only)", { timeout: 30000 }, async t => {
  for (const [name, table, fields] of [
    ["User", "users", ["id", "sessionVersion", "role"]],
    ["KvIdentity", "kv_identities", ["id", "ownerId", "ownerSessionVersion", "revokedAt", "expiresAt"]],
  ] as const) {
    const model = Prisma.dmmf.datamodel.models.find(m => m.name === name)!;
    assert.equal(model.dbName, table);
    for (const name of fields) { const field = model.fields.find(f => f.name === name)!; assert.equal(field.dbName ?? field.name, name); }
  }
  const directory = mkdtempSync(join(tmpdir(), "bortus-public-selected-path-sql-"));
  const db = new PrismaClient({ datasources: { db: { url: "file:" + join(directory, "public.db") } } });
  try {
    // Minimal final model shape, not migration execution or populated-schema proof.
    await db.$executeRaw`CREATE TABLE "users" ("id" TEXT PRIMARY KEY NOT NULL, "username" TEXT UNIQUE NOT NULL,
      "passwordHash" TEXT NOT NULL, "role" TEXT NOT NULL DEFAULT 'readonly', "sessionVersion" INTEGER NOT NULL DEFAULT 0,
      "engineAdmin" BOOLEAN NOT NULL DEFAULT false, "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)`;
    await db.$executeRaw`CREATE TABLE "kv_identities" ("id" TEXT PRIMARY KEY NOT NULL, "ownerId" TEXT NOT NULL,
      "ownerSessionVersion" INTEGER NOT NULL, "name" TEXT NOT NULL, "credentialHash" TEXT UNIQUE NOT NULL,
      "expiresAt" DATETIME NOT NULL, "revokedAt" DATETIME, "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)`;
    for (const engineAdmin of [false, true]) {
      const seed = async () => {
        await db.kvIdentity.deleteMany(); await db.user.deleteMany();
        await db.user.create({ data: { id: owner, username: "public-owner", passwordHash: "PUBLIC NONCREDENTIAL", role: "write", sessionVersion: 7, engineAdmin } });
        await db.kvIdentity.create({ data: { id: identityId, ownerId: owner, ownerSessionVersion: 7, name: "public-identity",
          credentialHash: "PUBLIC NONCREDENTIAL", expiresAt: new Date("2099-01-01T00:00:00Z") } });
      };
      let lastRows: Row[] = [], queries = 0, expectedBindings = [identityId, owner];
      const adapter = { user: db.user, $queryRaw: async (strings: TemplateStringsArray, ...values: unknown[]) => {
        queries++; assert.equal(strings.join("?").replace(/\s+/g, " ").trim(), sql);
        assert.deepEqual(values, expectedBindings);
        lastRows = await db.$queryRaw<Row[]>(strings, ...values); assert(lastRows.length <= 1); return lastRows;
      } };
      const registry = new KvRegistry(adapter, ["public-namespace"], config);
      await t.test(`mapped joined statement and DateTime/null decoding, admin=${engineAdmin}`, async () => {
        await seed(); queries = 0; await registry.currentSelectedPath(actor); assert.equal(queries, 1);
        assert.equal(lastRows[0].id, owner); assert.equal(lastRows[0].identityId, identityId);
        assert(lastRows[0].expiresAt instanceof Date); assert.equal(lastRows[0].expiresAt.toISOString(), "2099-01-01T00:00:00.000Z");
        assert.equal(lastRows[0].revokedAt, null);
        assert.deepEqual(Object.keys(lastRows[0]).sort(), ["id", "sessionVersion", "role", "identityId", "ownerId", "ownerSessionVersion", "revokedAt", "expiresAt"].sort());
        assert.equal(await db.user.count(), 1); assert.equal(await db.kvIdentity.count(), 1);
      });
      const changes: Record<string, () => Promise<unknown>> = {
        missingAccount: () => db.user.delete({ where: { id: owner } }),
        accountSession: () => db.user.update({ where: { id: owner }, data: { sessionVersion: 8 } }),
        readonlyOwner: () => db.user.update({ where: { id: owner }, data: { role: "readonly" } }),
        missingIdentity: () => db.kvIdentity.delete({ where: { id: identityId } }),
        mismatchedOwner: () => db.kvIdentity.update({ where: { id: identityId }, data: { ownerId: "other-public-owner" } }),
        identitySession: () => db.kvIdentity.update({ where: { id: identityId }, data: { ownerSessionVersion: 8 } }),
        revokedIdentity: () => db.kvIdentity.update({ where: { id: identityId }, data: { revokedAt: new Date("2020-01-01T00:00:00Z") } }),
        expiredIdentity: () => db.kvIdentity.update({ where: { id: identityId }, data: { expiresAt: new Date(0) } }),
      };
      for (const [name, change] of Object.entries(changes)) await t.test(`${name} refuses401, admin=${engineAdmin}`, async () => {
        await seed(); await change(); queries = 0; await assert.rejects(registry.currentSelectedPath(actor), denied); assert.equal(queries, 1);
        if (name === "missingIdentity") assert.equal(lastRows[0].expiresAt, null);
        if (name === "revokedIdentity") assert(lastRows[0].revokedAt instanceof Date);
      });
      await t.test(`role-only restoration keeps session and revocation, admin=${engineAdmin}`, async () => {
        await seed(); await db.user.update({ where: { id: owner }, data: { role: "readonly" } });
        await assert.rejects(registry.currentSelectedPath(actor), denied);
        await db.user.update({ where: { id: owner }, data: { role: "write" } }); await registry.currentSelectedPath(actor);
        const user = await db.user.findUniqueOrThrow({ where: { id: owner } }), identity = await db.kvIdentity.findUniqueOrThrow({ where: { id: identityId } });
        assert.equal(user.sessionVersion, 7); assert.equal(identity.ownerSessionVersion, 7); assert.equal(identity.revokedAt, null);
      });
      await t.test(`human readonly delegates ORM current without joined statement, admin=${engineAdmin}`, async () => {
        await seed(); await db.user.update({ where: { id: owner }, data: { role: "readonly" } }); queries = 0;
        await registry.currentSelectedPath({ id: owner, sessionVersion: 7 }); assert.equal(queries, 0);
        await db.user.delete({ where: { id: owner } }); await assert.rejects(registry.currentSelectedPath({ id: owner, sessionVersion: 7 }), denied);
      });
      await t.test(`quote-like identifiers remain bound values, admin=${engineAdmin}`, async () => {
        await seed(); await db.user.create({ data: { id: "decoy", username: "public-decoy", passwordHash: "PUBLIC NONCREDENTIAL", role: "write" } });
        await registry.currentSelectedPath(actor); assert.equal(lastRows.length, 1); assert.equal(lastRows[0].id, owner); assert.equal(await db.user.count(), 2);
        expectedBindings = [identityId, "' OR 1=1 --"];
        await assert.rejects(registry.currentSelectedPath({ ...actor, id: expectedBindings[1] }), denied);
        expectedBindings = [identityId, owner];
      });
      await t.test(`malformed SQL DateTime fails closed, admin=${engineAdmin}`, async () => {
        await seed(); await db.$executeRaw`UPDATE "kv_identities" SET "expiresAt" = ${"PUBLIC INVALID DATETIME"} WHERE "id" = ${identityId}`;
        await assert.rejects(registry.currentSelectedPath(actor));
      });
      await t.test(`selected callback keeps metadata and final gate order (other gates inert), admin=${engineAdmin}`, async () => {
        await seed(); const order: string[] = [];
        const callbackRegistry = { path: async () => { order.push("path"); return metadata; },
          authorize: async () => { order.push("authorize"); }, authorizePolicyIntersection: async () => { order.push("policies"); },
          currentSelectedPath: async (a: Row) => { order.push("authority"); await registry.currentSelectedPath(a); } };
        assert.deepEqual(plain(await route.GET(callbackRegistry, actor, {}, { id: metadata.id })), metadata);
        assert.deepEqual(order, ["path", "authorize", "policies", "authority"]);
      });
      // Separate source boundary controls: these are not SQL decoding evidence.
      for (const [name, expiresAt] of [["invalidDate", new Date(NaN)], ["positiveInfinity", { getTime: () => Infinity }]] as const)
        await t.test(`non-finite expiry source refusal ${name}, admin=${engineAdmin}`, async () => {
          const invalid = new KvRegistry({ $queryRaw: async () => [{ id: owner, sessionVersion: 7, role: "write", identityId,
            ownerId: owner, ownerSessionVersion: 7, revokedAt: null, expiresAt }] }, ["public-namespace"], config);
          await assert.rejects(invalid.currentSelectedPath(actor), denied);
        });
    }
  } finally { await db.$disconnect(); rmSync(directory, { recursive: true, force: true }); }
});
