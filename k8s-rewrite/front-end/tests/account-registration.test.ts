import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { PrismaClient } from "@prisma/client";
import { AccountStore, AccountError } from "../src/lib/account-store";

test("concurrent distinct and duplicate bootstrap honors all environment/AppSetting permutations", { timeout: 30000 }, async t => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-registration-matrix-"));
  const url = `file:${path.join(dir, "public.db").replaceAll("\\", "/")}`;
  execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env: { ...process.env, DATABASE_URL: url }, stdio: "pipe" });
  const clients = [0, 1].map(() => new PrismaClient({ datasources: { db: { url } } })), stores = clients.map(db => new AccountStore(db));
  const previous = process.env.ALLOW_REGISTRATION;
  try {
    for (const [allowed, setting] of [["false", null], ["false", "false"], ["false", "true"], ["true", null], ["true", "false"]] as const) for (const duplicate of [false, true]) {
      await t.test(`environment ${allowed}; setting ${setting}; ${duplicate ? "duplicate" : "distinct"}`, async () => {
        await clients[0].kvPolicy.deleteMany(); await clients[0].user.deleteMany(); await clients[0].appSetting.deleteMany();
        process.env.ALLOW_REGISTRATION = allowed;
        if (setting !== null) await clients[0].appSetting.create({ data: { key: "allow_registration", value: setting } });
        const open = allowed === "true" || setting === "true";
        const results = await Promise.allSettled(Array.from({ length: 6 }, (_, i) => stores[i % 2].register({ username: duplicate ? "duplicate-public" : "distinct-public-" + i, passwordHash: "unused-public-hash" })));
        const fulfilled = results.filter(r => r.status === "fulfilled"), denied = results.filter(r => r.status === "rejected");
        const users = await clients[0].user.findMany(), policies = await clients[0].kvPolicy.findMany();
        assert.equal(fulfilled.length, duplicate || !open ? 1 : 6); assert.equal(users.length, fulfilled.length);
        assert.equal(users.filter(u => u.role === "write").length, 1);
        assert.equal(users.filter(u => u.role === "write" && u.engineAdmin).length, 1);
        assert.equal(users.filter(u => u.role === "readonly" && u.engineAdmin).length, 0);
        assert.equal(policies.length, users.length); assert.equal(new Set(policies.map(p => p.principal)).size, users.length);
        for (const user of users) assert.ok(policies.some(p => p.principal === "user:" + user.id));
        for (const rejected of denied) {
          assert.ok(rejected.reason instanceof AccountError); assert.equal(rejected.reason.status, open ? 409 : 403);
          assert.ok(["Username already taken", "Registration is locked"].includes(rejected.reason.message));
        }
        if (open) {
          const next = await stores[1].register({ username: "post-bootstrap-public", passwordHash: "unused-public-hash" });
          assert.equal(next.role, "readonly"); assert.equal(next.engineAdmin, false);
        } else await assert.rejects(stores[1].register({ username: "post-bootstrap-public", passwordHash: "unused-public-hash" }), e => e instanceof AccountError && e.status === 403);
      });
    }
  } finally {
    if (previous === undefined) delete process.env.ALLOW_REGISTRATION; else process.env.ALLOW_REGISTRATION = previous;
    await Promise.all(clients.map(db => db.$disconnect())); await rm(dir, { recursive: true, force: true });
  }
});
