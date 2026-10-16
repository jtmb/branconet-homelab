import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { PrismaClient } from "@prisma/client";
import { SignJWT } from "jose";
import { AccountError, AccountStore } from "../src/lib/account-store";

test("SQLite account invariants and session revocation across independent clients", { timeout: 90000 }, async t => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-accounts-"));
  const url = `file:${path.join(dir, "accounts.db").replaceAll("\\", "/")}`;
  const env: NodeJS.ProcessEnv = { ...process.env, DATABASE_URL: url };
  delete env.RUST_LOG;
  execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe" });
  const clients = [0, 1].map(() => new PrismaClient({ datasources: { db: { url } } }));
  const stores = clients.map(db => new AccountStore(db));
  const db = clients[0];
  const previousRegistration = process.env.ALLOW_REGISTRATION;
  process.env.ALLOW_REGISTRATION = "false";
  try {
    await t.test("exactly one bootstrap claim when registration is closed", async () => {
      const results = await Promise.allSettled(Array.from({ length: 6 }, (_, i) => stores[i % 2].register({ username: `bootstrap${i}`, passwordHash: "unused-fixture-hash" })));
      assert.equal(results.filter(r => r.status === "fulfilled").length, 1);
      assert.equal(await db.user.count({ where: { role: "write" } }), 1);
      for (const result of results) if (result.status === "rejected") {
        assert.ok(result.reason instanceof AccountError);
        assert.equal(result.reason.status, 403);
      }
    });
    await t.test("open registration still has exactly one initial writer; uniqueness is 409", async () => {
      await db.user.deleteMany();
      process.env.ALLOW_REGISTRATION = "true";
      const users = await Promise.all(Array.from({ length: 6 }, (_, i) => stores[i % 2].register({ username: `open${i}`, passwordHash: "unused-fixture-hash" })));
      assert.equal(users.filter(u => u.role === "write").length, 1);
      await assert.rejects(stores[1].register({ username: "open0", passwordHash: "unused-fixture-hash" }), (e: unknown) => e instanceof AccountError && e.status === 409);
      process.env.ALLOW_REGISTRATION = "false";
    });
    await t.test("cross-demotion, cross-deletion and mixed changes preserve a writer", async () => {
      for (const mode of ["demote", "delete", "mixed"] as const) for (let round = 0; round < 4; round++) {
        await db.user.deleteMany();
        const a = await db.user.create({ data: { username: "actor_a", passwordHash: "unused-fixture-hash", role: "write", engineAdmin: true } });
        const b = await db.user.create({ data: { username: "actor_b", passwordHash: "unused-fixture-hash", role: "write", engineAdmin: true } });
        const actor = (u: typeof a) => ({ id: u.id, sessionVersion: u.sessionVersion });
        const results = await Promise.allSettled([
          mode === "delete" ? stores[0].delete(actor(a), b.id) : stores[0].update(actor(a), b.id, { role: "readonly", passwordHash: "unused-new-fixture-hash" }),
          mode === "demote" ? stores[1].update(actor(b), a.id, { role: "readonly", passwordHash: "unused-new-fixture-hash" }) : stores[1].delete(actor(b), a.id),
        ]);
        assert.equal(results.filter(r => r.status === "fulfilled").length, 1);
        assert.equal(await db.user.count({ where: { role: "write" } }), 1);
        assert.equal(await db.user.count({ where: { role: "write", engineAdmin: true } }), 1);
        for (const result of results) if (result.status === "rejected") assert.ok(result.reason instanceof AccountError && [401, 403].includes(result.reason.status));
      }
    });
    await t.test("session existence, reset revocation, role recheck and self protection", async () => {
      await db.user.deleteMany();
      const user = await db.user.create({ data: { username: "session_writer", passwordHash: "unused-fixture-hash", role: "write" } });
      process.env.DATABASE_URL = url;
      process.env.BOTRUS_JWT_SECRET = "fixture-signing-material-only";
      const auth = await import("../src/lib/auth");
      const { default: singleton } = await import("../src/lib/db");
      try {
        const token = await auth.signJWT({ sub: user.id, username: user.username });
        const cookie = `botrus_auth_token=${token}`;
        assert.equal((await auth.getSessionFromHeaders(cookie))?.id, user.id);
        const legacy = await new SignJWT({ sub: user.id, username: user.username })
          .setProtectedHeader({ alg: "HS256" }).setExpirationTime("1h")
          .sign(new TextEncoder().encode("fixture-signing-material-only"));
        assert.equal((await auth.getSessionFromHeaders(`botrus_auth_token=${legacy}`))?.id, user.id);
        const actor = { id: user.id, sessionVersion: 0 };
        await assert.rejects(stores[0].update(actor, user.id, { role: "readonly" }), (e: unknown) => e instanceof AccountError && e.status === 403);
        await assert.rejects(stores[0].delete(actor, user.id), (e: unknown) => e instanceof AccountError && e.status === 403);
        await stores[0].update(actor, user.id, { passwordHash: "unused-new-fixture-hash" });
        assert.equal(await auth.getSessionFromHeaders(cookie), null);
        assert.equal(await auth.getSessionFromHeaders(`botrus_auth_token=${legacy}`), null);
        await assert.rejects(stores[1].create(actor, { username: "revoked_create", passwordHash: "unused-fixture-hash", role: "write" }), (e: unknown) => e instanceof AccountError && e.status === 401);
        const freshCookie = `botrus_auth_token=${await auth.signJWT({ sub: user.id, username: user.username, sessionVersion: 1 })}`;
        assert.equal((await auth.getSessionFromHeaders(freshCookie))?.sessionVersion, 1);
        await db.user.update({ where: { id: user.id }, data: { role: "readonly" } });
        await assert.rejects(stores[0].create({ id: user.id, sessionVersion: 1 }, { username: "demoted_create", passwordHash: "unused-fixture-hash", role: "write" }), (e: unknown) => e instanceof AccountError && e.status === 403);
        await db.user.delete({ where: { id: user.id } });
        assert.equal(await auth.getSessionFromHeaders(freshCookie), null);
      } finally { await singleton.$disconnect(); }
    });
  } finally {
    if (previousRegistration === undefined) delete process.env.ALLOW_REGISTRATION; else process.env.ALLOW_REGISTRATION = previousRegistration;
    await Promise.all(clients.map(client => client.$disconnect()));
    await rm(dir, { recursive: true, force: true });
  }
});
