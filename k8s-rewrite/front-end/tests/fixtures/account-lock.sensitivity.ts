import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { PrismaClient } from "@prisma/client";

type Outcome = { success: boolean; status: number | null; countCalls: number; reportedCount: number | null };
function participant(url: string, owned: Set<ChildProcess>) {
  const child = spawn(process.execPath, [path.resolve("tests/fixtures/account-lock-participant.cjs")], {
    cwd: process.cwd(), env: { ...process.env, BORTUS_PUBLIC_TEST_DB: url }, stdio: ["ignore", "pipe", "pipe", "ipc"],
  });
  owned.add(child);
  let ready!: () => void, notReady!: (error: Error) => void, counted!: (value: number) => void, noCount!: (error: Error) => void;
  let completed!: (value: Outcome) => void, noOutcome!: (error: Error) => void;
  const started = new Promise<void>((resolve, reject) => { ready = resolve; notReady = reject; });
  const count = new Promise<number>((resolve, reject) => { counted = resolve; noCount = reject; });
  const done = new Promise<Outcome>((resolve, reject) => { completed = resolve; noOutcome = reject; });
  for (const promise of [started, count, done]) void promise.catch(() => {});
  let readySeen = false, countSeen = false, doneSeen = false, stdoutBytes = 0, stderrBytes = 0;
  const refuse = () => { const error = Error("Owned participant protocol refused"); notReady(error); noCount(error); noOutcome(error); };
  child.stdout!.on("data", chunk => { stdoutBytes += chunk.length; refuse(); });
  child.stderr!.on("data", chunk => { stderrBytes += chunk.length; refuse(); });
  child.on("error", refuse);
  child.on("message", (message: { kind?: string } & Partial<Outcome> & { value?: number }) => {
    if (message?.kind === "ready" && !readySeen) { readySeen = true; ready(); }
    else if (message?.kind === "final-count" && readySeen && !countSeen && Number.isInteger(message.value)) { countSeen = true; counted(message.value!); }
    else if (message?.kind === "done" && readySeen && !doneSeen && typeof message.success === "boolean" &&
      (message.status === null || Number.isInteger(message.status)) && (message.countCalls === 0 || message.countCalls === 1) &&
      (message.reportedCount === null || Number.isInteger(message.reportedCount))) { doneSeen = true; completed(message as Outcome); }
    else refuse();
  });
  const closed = new Promise<{ code: number | null; signal: NodeJS.Signals | null }>(resolve => child.once("close", (code, signal) => {
    if (code !== 0 || signal !== null || !doneSeen || stdoutBytes || stderrBytes) refuse();
    resolve({ code, signal });
  }));
  const send = (value: object) => new Promise<void>((resolve, reject) => child.send(value, error => error ? reject(error) : resolve()));
  return { child, started, count, done, closed, send, bytes: () => [stdoutBytes, stderrBytes] };
}

test("separate processes require the SQL writer lock across the final real writer count and change", { timeout: 25000 }, async () => {
  const deadline = Date.now() + 23000;
  async function within<T>(promise: Promise<T>, limit: number): Promise<T> {
    const milliseconds = Math.min(limit, deadline - Date.now() - 2000);
    if (milliseconds <= 0) throw Error("Process sensitivity deadline exhausted");
    let timer: NodeJS.Timeout | undefined;
    try { return await Promise.race([promise, new Promise<never>((_, reject) => { timer = setTimeout(() => reject(Error("Process phase deadline")), milliseconds); })]); }
    finally { clearTimeout(timer); }
  }
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-lock-sensitivity-")), file = path.join(dir, "public.db");
  const url = "file:" + file.replaceAll("\\", "/"), owned = new Set<ChildProcess>();
  let db: PrismaClient | undefined, probe: DatabaseSync | undefined, held = false, primary: unknown;
  const cleanupFailures: number[] = [];
  try {
    execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], {
      env: { ...process.env, DATABASE_URL: url }, stdio: "pipe", timeout: 5000, killSignal: "SIGKILL", maxBuffer: 1048576,
    });
    db = new PrismaClient({ datasources: { db: { url } } });
    const users = await Promise.all(["first", "second"].map(name => db!.user.create({ data: { username: "public_lock_" + name, passwordHash: "unused-public-hash", role: "write", engineAdmin: true } })));
    const first = participant(url, owned), second = participant(url, owned);
    await within(Promise.all([first.started, second.started]), 5000);
    const start = (index: number) => ({ kind: "start", actor: { id: users[index].id, sessionVersion: users[index].sessionVersion }, target: users[1 - index].id });
    await first.send(start(0));
    const firstCount = await within(first.count, 2000); assert.equal(firstCount, 2);
    probe = new DatabaseSync(file, { timeout: 0 });
    let busyCode: number | null = null;
    try { probe.exec("BEGIN IMMEDIATE"); held = true; }
    catch (error) { if ((error as { errcode?: number }).errcode !== 5) throw error; busyCode = 5; }
    const acquired = held;
    let secondCount: number | null = null, outcomes: Outcome[];
    if (held) {
      // Reads proceed under the real reserved writer lock. Both observations must be actual2.
      await second.send(start(1)); secondCount = await within(second.count, 2000); assert.equal(secondCount, 2);
      probe.exec("ROLLBACK"); held = false;
      await first.send({ kind: "release" }); const firstOutcome = await within(first.done, 4000);
      // Complete the first real autocommit before releasing the second, avoiding write races.
      await second.send({ kind: "release" }); outcomes = [firstOutcome, await within(second.done, 4000)];
    } else {
      assert.equal(busyCode, 5);
      await first.send({ kind: "release" }); const firstOutcome = await within(first.done, 4000);
      await second.send(start(1)); outcomes = [firstOutcome, await within(second.done, 4000)];
    }
    const exits = await within(Promise.all([first.closed, second.closed]), 1000);
    assert.deepEqual(exits, [{ code: 0, signal: null }, { code: 0, signal: null }]);
    assert.deepEqual([first.bytes(), second.bytes()], [[0, 0], [0, 0]]);
    assert.deepEqual(outcomes.map(value => value.countCalls), acquired ? [1, 1] : [1, 0]);
    assert.deepEqual(outcomes.map(value => value.reportedCount), acquired ? [2, 2] : [2, null]);
    const writers = await db.user.count({ where: { role: "write" } }), administrators = await db.user.count({ where: { role: "write", engineAdmin: true } });
    console.log("A01_LOCK_PROOF " + JSON.stringify({ schema: 1, acquired, busyCode, firstCount, secondCount, countCalls: outcomes.map(value => value.countCalls),
      outcomes: outcomes.map(value => ({ success: value.success, status: value.status })), writers, administrators, distinctParticipantProcesses: first.child.pid !== second.child.pid, participantExits: exits.map(value => value.code) }));
    assert.equal(outcomes.filter(value => value.success).length, 1, "Separate-process changes must retain exactly one authorized success");
    assert.ok(outcomes.filter(value => !value.success).every(value => value.status === 401 || value.status === 403));
    assert.equal(writers, 1); assert.equal(administrators, 1);
  } catch (error) { primary = error; }
  finally {
    if (held) { try { probe!.exec("ROLLBACK"); } catch { cleanupFailures.push(1); } }
    try { probe?.close(); } catch { cleanupFailures.push(2); }
    const closureDeadline = Math.min(Date.now() + 2000, deadline);
    for (const child of owned) if (child.exitCode === null && child.signalCode === null) { try { child.kill("SIGTERM"); } catch { cleanupFailures.push(3); } }
    for (const child of owned) {
      if (child.exitCode !== null || child.signalCode !== null) continue;
      const remaining = Math.max(1, closureDeadline - Date.now());
      const closed = await Promise.race([new Promise<boolean>(resolve => child.once("close", () => resolve(true))), new Promise<boolean>(resolve => setTimeout(() => resolve(false), remaining))]);
      if (!closed) { cleanupFailures.push(4); try { child.kill("SIGKILL"); } catch { cleanupFailures.push(5); } }
    }
    try { await db?.$disconnect(); } catch { cleanupFailures.push(6); }
    try {
      if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-lock-sensitivity-")) throw Error("Owned cleanup scope");
      await rm(dir, { recursive: true, force: true });
    } catch { cleanupFailures.push(7); }
    console.log("A01_LOCK_CLEANUP " + JSON.stringify({ failures: cleanupFailures, twoParticipants: owned.size === 2,
      bothReportedExit: Array.from(owned).every(child => child.exitCode !== null || child.signalCode !== null) }));
  }
  if (primary) throw primary;
  assert.deepEqual(cleanupFailures, []);
});
