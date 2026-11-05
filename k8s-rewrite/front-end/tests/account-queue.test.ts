import { test } from "node:test";
import assert from "node:assert/strict";
import { AccountChangeQueue, AccountQueueBusyError, accountChangeQueue, isAccountQueueBusy } from "../src/lib/account-change-queue";
import { execFileSync } from "node:child_process";
import { mkdtemp, rm, readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import path from "node:path";
import { PrismaClient } from "@prisma/client";
import { AccountStore, AccountError } from "../src/lib/account-store";

function deferred() {
  let release!: () => void;
  const promise = new Promise<void>(resolve => { release = resolve; });
  return { promise, release };
}
const turn = () => new Promise<void>(resolve => setImmediate(resolve));

test("account FIFO bounds admission at one active and64 waiters without invoking rejected work", async () => {
  const queue = new AccountChangeQueue(), held = deferred();
  const order: number[] = [];
  const first = queue.run(async () => { order.push(-1); await held.promise; });
  const waiting = Array.from({ length: 64 }, (_, i) => queue.run(async () => { order.push(i); return i; }));
  await assert.rejects(queue.run(async () => { throw new Error("Must not execute overflow"); }), AccountQueueBusyError);
  assert.deepEqual(queue.diagnostics(), { active: 1, queued: 64 });
  held.release(); await first;
  assert.deepEqual(await Promise.all(waiting), Array.from({ length: 64 }, (_, i) => i));
  await turn(); assert.deepEqual(order, [-1, ...Array.from({ length: 64 }, (_, i) => i)]);
  assert.deepEqual(queue.diagnostics(), { active: 0, queued: 0 });
});

test("queued expiry removes only unstarted work and never releases a live active callback", async () => {
  const queue = new AccountChangeQueue(64, 30), held = deferred(); let expiredCalled = false;
  const active = queue.run(async () => { await held.promise; return "settled"; });
  await assert.rejects(queue.run(async () => { expiredCalled = true; }), AccountQueueBusyError);
  assert.equal(expiredCalled, false); assert.deepEqual(queue.diagnostics(), { active: 1, queued: 0 });
  const next = queue.run(async () => "next");
  assert.deepEqual(queue.diagnostics(), { active: 1, queued: 1 });
  held.release(); assert.equal(await active, "settled"); assert.equal(await next, "next");
  await turn(); assert.deepEqual(queue.diagnostics(), { active: 0, queued: 0 });
});

test("failed or synchronously throwing account callbacks settle ownership before the next FIFO admission", async () => {
  const queue = new AccountChangeQueue(), held = deferred(); const order: string[] = [];
  const failed = queue.run(async () => { order.push("started"); await held.promise; order.push("failed"); throw new Error("Public failure"); });
  const expected = assert.rejects(failed, /Public failure/);
  const next = queue.run(async () => { order.push("next"); });
  held.release(); await expected; await next; await turn();
  assert.deepEqual(order, ["started", "failed", "next"]);
  await assert.rejects(queue.run(() => { throw new Error("Public synchronous failure"); }), /Public synchronous failure/);
  assert.equal(await queue.run(async () => "recovered"), "recovered"); await turn();
  assert.deepEqual(queue.diagnostics(), { active: 0, queued: 0 });
});

test("all AccountStore instances in this process share the same admission owner", () => {
  assert.equal(accountChangeQueue(), accountChangeQueue());
});

test("a genuine second module copy shares queue ownership and fixed busy translation", async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-account-module-"));
  const globalState = globalThis as typeof globalThis & { __bortusAccountChangesV1?: AccountChangeQueue };
  const saved = accountChangeQueue(); assert.deepEqual(saved.diagnostics(), { active: 0, queued: 0 });
  const held = deferred(); let owner: Promise<void> | undefined; const waiting: Promise<void>[] = [];
  try {
    const modulePath = path.join(dir, "account-copy.ts");
    await writeFile(modulePath, await readFile(path.resolve("src/lib/account-change-queue.ts")));
    const copied = createRequire(path.resolve("package.json"))(modulePath) as typeof import("../src/lib/account-change-queue");
    assert.notEqual(copied.AccountQueueBusyError, AccountQueueBusyError);
    assert.equal(copied.accountChangeQueue(), saved);
    const foreign = new copied.AccountQueueBusyError(); foreign.message = "Untrusted dynamic message";
    assert.equal(foreign instanceof AccountQueueBusyError, false);
    assert.equal(isAccountQueueBusy(foreign), true);
    assert.equal(isAccountQueueBusy({ code: foreign.code }), false);
    globalState.__bortusAccountChangesV1 = new copied.AccountChangeQueue();
    const queue = accountChangeQueue(); owner = queue.run(async () => { await held.promise; });
    for (let i = 0; i < 64; i++) waiting.push(queue.run(async () => {}));
    let databaseCalled = false;
    const db = { $transaction: async () => { databaseCalled = true; throw new Error("Must not run database"); } } as unknown as PrismaClient;
    await assert.rejects(new AccountStore(db).create({ id: "public", sessionVersion: 0 }, { username: "public", passwordHash: "unused-public-hash", role: "readonly" }),
      (e: unknown) => e instanceof AccountError && e.status === 503 && e.message === "Account change is busy; retry shortly");
    assert.equal(databaseCalled, false);
  } finally {
    held.release(); if (owner) await owner; await Promise.all(waiting); await turn();
    globalState.__bortusAccountChangesV1 = saved;
    await rm(dir, { recursive: true, force: true });
  }
});

test("queued account mutations recheck demotion, reset and deletion after admission", { timeout: 30000 }, async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-queue-auth-"));
  const url = `file:${path.join(dir, "public.db").replaceAll("\\", "/")}`;
  execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env: { ...process.env, DATABASE_URL: url }, stdio: "pipe" });
  const db = new PrismaClient({ datasources: { db: { url } } }), store = new AccountStore(db);
  try {
    for (const withdrawal of ["demote", "reset", "delete"] as const) {
      const actor = await db.user.create({ data: { username: `actor_${withdrawal}`, passwordHash: "unused-public-hash", role: "write", engineAdmin: true } });
      const held = deferred(), owner = accountChangeQueue().run(async () => { await held.promise; });
      const change = store.create({ id: actor.id, sessionVersion: actor.sessionVersion }, { username: `refused_${withdrawal}`, passwordHash: "unused-public-hash", role: "readonly" });
      const refusal = assert.rejects(change, (e: unknown) => e instanceof AccountError && e.status === (withdrawal === "demote" ? 403 : 401));
      try {
        assert.equal(accountChangeQueue().diagnostics().queued, 1);
        if (withdrawal === "delete") await db.user.delete({ where: { id: actor.id } });
        else await db.user.update({ where: { id: actor.id }, data: withdrawal === "demote" ? { role: "readonly", engineAdmin: false } : { sessionVersion: { increment: 1 } } });
      } finally { held.release(); await owner; }
      await refusal;
      assert.equal(await db.user.count({ where: { username: `refused_${withdrawal}` } }), 0);
    }
  } finally { await db.$disconnect(); await rm(dir, { recursive: true, force: true }); }
});
