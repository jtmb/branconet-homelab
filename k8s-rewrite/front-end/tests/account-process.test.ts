import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { PrismaClient } from "@prisma/client";

type Outcome = { success: boolean; status: number | null };
function participant(url: string) {
  const child = spawn(process.execPath, [path.resolve("tests/fixtures/account-process.cjs")], {
    cwd: process.cwd(), env: { ...process.env, BORTUS_PUBLIC_TEST_DB: url }, stdio: ["ignore", "ignore", "ignore", "ipc"],
  });
  let ready!: () => void, notReady!: (error: Error) => void, complete!: (result: Outcome) => void, fail!: (error: Error) => void;
  const started = new Promise<void>((resolve, reject) => { ready = resolve; notReady = reject; });
  const result = new Promise<Outcome>((resolve, reject) => { complete = resolve; fail = reject; });
  // Observe early failures even while the caller is waiting for both participants' ready messages.
  void result.catch(() => {});
  const reject = () => { const error = new Error("Owned account participant failed"); notReady(error); fail(error); };
  const timer = setTimeout(() => { reject(); if (child.exitCode === null) child.kill(); }, 45000);
  child.on("message", (message: { kind: string; success: boolean; status: number | null }) => {
    if (message.kind === "ready") ready();
    if (message.kind === "done") complete({ success: message.success, status: message.status });
  });
  child.on("error", reject);
  const exited = new Promise<number | null>(resolve => child.once("exit", code => { clearTimeout(timer); resolve(code); if (code !== 0) reject(); }));
  return { child, started, result, exited };
}

test("independent processes retain SQL last-writer and effective-admin authority", { timeout: 90000 }, async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-account-process-"));
  const url = `file:${path.join(dir, "public.db").replaceAll("\\", "/")}`;
  execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env: { ...process.env, DATABASE_URL: url }, stdio: "pipe" });
  const db = new PrismaClient({ datasources: { db: { url } } });
  const owned = new Set<ChildProcess>();
  try {
    for (const mode of ["demote", "delete", "mixed"] as const) for (let round = 0; round < 2; round++) {
      await db.user.deleteMany();
      const users = await Promise.all(["a", "b"].map(name => db.user.create({ data: { username: `actor_${name}`, passwordHash: "unused-public-hash", role: "write", engineAdmin: true } })));
      const participants = [participant(url), participant(url)];
      for (const item of participants) owned.add(item.child);
      await Promise.all(participants.map(item => item.started));
      for (let i = 0; i < 2; i++) participants[i].child.send({ action: mode === "delete" || (mode === "mixed" && i === 0) ? "delete" : "demote", actor: { id: users[i].id, sessionVersion: users[i].sessionVersion }, target: users[1 - i].id });
      const outcomes = await Promise.all(participants.map(item => item.result));
      assert.equal(outcomes.filter(item => item.success).length, 1);
      assert.ok(outcomes.filter(item => !item.success).every(item => item.status === 401 || item.status === 403));
      assert.equal(await db.user.count({ where: { role: "write" } }), 1);
      assert.equal(await db.user.count({ where: { role: "write", engineAdmin: true } }), 1);
      assert.deepEqual(await Promise.all(participants.map(item => item.exited)), [0, 0]);
      for (const item of participants) owned.delete(item.child);
    }
  } finally {
    for (const child of owned) if (child.exitCode === null) child.kill();
    await Promise.all(Array.from(owned, child => new Promise<void>(resolve => { if (child.exitCode !== null) resolve(); else child.once("exit", () => resolve()); })));
    await db.$disconnect(); await rm(dir, { recursive: true, force: true });
  }
});
