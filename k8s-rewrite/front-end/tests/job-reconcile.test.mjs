import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { ORPHAN_MARKER, claimProvisioningJob, reconcileProvisioningJobs } from "../src/lib/job-reconcile.ts";
import { acquireProvisioningLock } from "../src/lib/provisioning-lock.ts";
import { createJobStream } from "../src/lib/job-stream.ts";

const directory = fileURLToPath(new URL(".", import.meta.url));
const lockModule = new URL("../src/lib/provisioning-lock.ts", import.meta.url).href;

test("runner retains the admission lock after dashboard death; recovery preserves its log", {
  skip: process.platform !== "linux", timeout: 15_000,
}, async t => {
  const db = new DatabaseSync(":memory:");
  t.after(() => db.close());
  db.exec('CREATE TABLE jobs (id TEXT PRIMARY KEY, playbook TEXT, status TEXT, output TEXT, startedAt INTEGER, finishedAt INTEGER)');
  const client = {
    job: { findMany: async ({ where }) => where.id
      ? db.prepare("SELECT id FROM jobs WHERE status = ? AND id = ?").all(where.status, where.id)
      : db.prepare("SELECT id FROM jobs WHERE status = ?").all(where.status) },
    $executeRaw: async (query, ...args) => db.prepare(query.join("?")).run(...args).changes,
  };
  const dashboard = spawn(process.execPath, ["--input-type=module", "-e", `
    import { spawn } from "node:child_process";
    import { acquireProvisioningLock } from ${JSON.stringify(lockModule)};
    const lock = await acquireProvisioningLock(${JSON.stringify(directory)});
    if (lock.state !== "held") process.exit(1);
    const runner = spawn(process.execPath, ["-e",
      'process.on("SIGTERM", () => process.exit(0)); console.log(process.pid); setInterval(() => {}, 1000)'],
      { stdio: ["ignore", "pipe", "ignore", lock.lease.fd] });
    runner.stdout.once("data", line =>
      console.log(JSON.stringify({ pid: Number(line), id: lock.lease.newJobId() })));
  `], { stdio: ["ignore", "pipe", "inherit"] });
  const closed = once(dashboard, "exit");
  t.after(() => { dashboard.kill("SIGKILL"); });
  const [line] = await once(dashboard.stdout, "data");
  const { id, pid } = JSON.parse(line);
  assert.ok(Number.isSafeInteger(pid) && pid > 1);
  let stopped = false;
  t.after(() => { if (!stopped) try { process.kill(pid, "SIGTERM"); } catch {} });
  db.prepare("INSERT INTO jobs (id, status, output) VALUES (?, 'running', ?)").run(id, "partial log");
  db.prepare("INSERT INTO jobs (id, status, output) VALUES ('legacy', 'running', 'unverified log')").run();

  dashboard.kill("SIGKILL");
  await closed;
  assert.equal((await acquireProvisioningLock(directory)).state, "busy");
  assert.equal((await acquireProvisioningLock(directory + "/absent")).state, "unknown");
  assert.equal(db.prepare("SELECT status FROM jobs WHERE id=?").get(id).status, "running");

  process.kill(pid, "SIGTERM");
  let lock = await acquireProvisioningLock(directory);
  for (let attempt = 0; lock.state === "busy" && attempt < 50; attempt++) {
    await delay(20);
    lock = await acquireProvisioningLock(directory);
  }
  assert.equal(lock.state, "held");
  stopped = true;
  try {
    assert.deepEqual(await reconcileProvisioningJobs(client, lock.lease), { interrupted: 1, unknown: true });
    assert.deepEqual(await reconcileProvisioningJobs(client, lock.lease), { interrupted: 0, unknown: true });
    const row = db.prepare("SELECT status, output, finishedAt FROM jobs WHERE id=?").get(id);
    assert.equal(row.status, "interrupted");
    assert.equal(row.output, "partial log" + ORPHAN_MARKER);
    assert.ok(row.finishedAt > 0);
    assert.equal(db.prepare("SELECT status FROM jobs WHERE id='legacy'").get().status, "running");
    assert.equal(await claimProvisioningJob(client, lock.lease, "site.yml"), null);
    db.prepare("UPDATE jobs SET status='failed' WHERE id='legacy'").run();
    assert.deepEqual(await reconcileProvisioningJobs(client, lock.lease), { interrupted: 0, unknown: false });
    const nextId = await claimProvisioningJob(client, lock.lease, "site.yml");
    assert.ok(lock.lease.ownsJobId(nextId));
    assert.equal(await claimProvisioningJob(client, lock.lease, "site.yml"), null);
  } finally { await lock.lease.release(); }
});

test("interrupted output arrives in a terminal stream frame", async () => {
  const stream = createJobStream({
    signal: new AbortController().signal, cursor: 0, authorize: async () => true,
    load: async () => ({ output: "kept", nextOffset: 4, total: 4, status: "interrupted" }),
  });
  const frames = [];
  for await (const frame of stream) frames.push(new TextDecoder().decode(frame));
  const data = JSON.parse(frames.join("").split("\n").find(line => line.startsWith("data: ")).slice(6));
  assert.deepEqual(data, { done: true, status: "interrupted", output: "kept", cursor: 4, total: 4 });
});
