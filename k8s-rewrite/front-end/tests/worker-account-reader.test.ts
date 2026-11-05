import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { EventEmitter } from "node:events";
import { Worker, SHARE_ENV } from "node:worker_threads";
import { DatabaseSync } from "node:sqlite";
import { PrismaClient } from "@prisma/client";
import { WorkerAccountReader } from "../src/lib/worker-account-reader";

test("worker reader preserves real fresh SQL and transport ownership", async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "bortus-worker-public-"));
  const file = path.join(root, "public.db"), config = `file:${file}`, original = process.env.DATABASE_URL;
  const writer = new DatabaseSync(file);
  writer.exec("CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT,sessionVersion INTEGER,role TEXT,engineAdmin BOOLEAN); INSERT INTO users VALUES('public','public',0,'write',1)");
  const readers: WorkerAccountReader[] = [];
  const publicCounts = new SharedArrayBuffer(96), counts = new Int32Array(publicCounts);
  const clocks = new BigInt64Array(publicCounts, 64, 2);
  const workerFile = path.join(process.cwd(), "runtime/direct-account-reader-worker.cjs");
  function reader(schema = root) {
    const r = new WorkerAccountReader(undefined, schema, workerFile, file => new Worker(file, {
      env: SHARE_ENV, workerData: { publicCounts }, execArgv: ["--require", path.join(process.cwd(), "tests/worker-account-probe.cjs")]
    })); readers.push(r); return r;
  }
  async function waiting(index: number, value: number) {
    const deadline = performance.now() + 2000;
    while (Atomics.load(counts, index) !== value) {
      assert.ok(performance.now() < deadline, "Public worker coordination deadline");
      await new Promise(resolve => setTimeout(resolve, 1));
    }
  }
  try {
    process.env.DATABASE_URL = config;
    await t.test("01 real three/five projections observe writer revocation and deletion without row cache", async () => {
      const r = reader();
      assert.deepEqual(await r.readSession("public"), { id: "public", username: "public", sessionVersion: 0 });
      const before = Atomics.load(counts, 0);
      writer.exec("UPDATE users SET sessionVersion=1,role='readonly',engineAdmin=0");
      assert.deepEqual(await r.readAccount("public"), { id: "public", username: "public", sessionVersion: 1, role: "readonly", engineAdmin: false });
      assert.equal(Atomics.load(counts, 0) - before, 3);
      writer.exec("DELETE FROM users"); assert.equal(await r.readSession("public"), null);
      writer.exec("INSERT INTO users VALUES('public','public',0,'write',1)"); await r.close();
      assert.equal(r.activity().active, 0);
    });
    await t.test("02 startup cancellation is atomically visible before any worker SQL and drains before close", async () => {
      const r = reader(), abort = new AbortController(), before = Atomics.load(counts, 0);
      const result = r.readSession("public", abort.signal); abort.abort();
      await assert.rejects(result, /^Error: Account authorization unavailable$/);
      assert.equal(r.activity().active, 1); await r.close();
      assert.equal(Atomics.load(counts, 0), before); assert.equal(r.activity().active, 0);
    });
    await t.test("03 current shared configuration rotation refuses an already admitted startup operation", async () => {
      const r = reader(), before = Atomics.load(counts, 0);
      const result = r.readSession("public"); process.env.DATABASE_URL = `file:${path.join(root, "missing.db")}`;
      await assert.rejects(result, /^Error: Account authorization unavailable$/); await r.close();
      assert.equal(Atomics.load(counts, 0), before); process.env.DATABASE_URL = config;
    });
    await t.test("04 real schema outage refuses, closes the connection and does not return an old row", async () => {
      const r = reader(); await r.readSession("public"); writer.exec("ALTER TABLE users RENAME TO unavailable_users");
      await assert.rejects(r.readSession("public"), /^Error: Account authorization unavailable$/);
      writer.exec("ALTER TABLE unavailable_users RENAME TO users");
      assert.equal((await r.readSession("public"))?.username, "public"); await r.close();
    });
    await t.test("05 real replaced database refuses old snapshot then opens fresh on the subsequent read", async () => {
      const r = reader(); await r.readSession("public");
      const replacement = path.join(root, "replacement.db"), db = new DatabaseSync(replacement);
      db.exec("CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT,sessionVersion INTEGER,role TEXT,engineAdmin BOOLEAN); INSERT INTO users VALUES('public','replacement',2,'readonly',0)"); db.close();
      fs.renameSync(file, file + ".old"); fs.renameSync(replacement, file);
      await assert.rejects(r.readSession("public"), /^Error: Account authorization unavailable$/);
      assert.equal((await r.readSession("public"))?.username, "replacement"); await r.close();
      fs.renameSync(file, file + ".new"); fs.renameSync(file + ".old", file);
    });
    await t.test("06 real timeout-zero exclusive lock expires without authority and releases only after settlement", async () => {
      const r = reader(); await r.readSession("public"); writer.exec("BEGIN EXCLUSIVE");
      const read = r.readAccount("public"); await assert.rejects(read, /^Error: Account authorization unavailable$/);
      const drain = r.close(); writer.exec("ROLLBACK"); await drain;
      assert.deepEqual(r.activity(), { active: 0, queued: 0, closing: false, closeFailed: false });
    });
    await t.test("15 actual shared process clock and two scheduled identity callbacks are observed and forwarded once", async () => {
      Atomics.store(counts, 8, 0); const beforeClock = process.hrtime.bigint(), r = reader();
      const beforeIdentities = Atomics.load(counts, 2), beforeCallbacks = Atomics.load(counts, 3), beforeForwards = Atomics.load(counts, 7);
      const result = r.readSession("public"); await waiting(8, 1);
      const workerClock = Atomics.load(clocks, 0), afterClock = process.hrtime.bigint();
      assert.ok(workerClock >= beforeClock && workerClock <= afterClock);
      await result;
      assert.equal(Atomics.load(counts, 2) - beforeIdentities, 2);
      assert.equal(Atomics.load(counts, 3) - beforeCallbacks, 2);
      assert.equal(Atomics.load(counts, 7) - beforeForwards, 2); await r.close();
    });
    const yieldCases = [
      { name: "16 actual pre-SQL yield cancellation retains ownership and executes no SQL", yield: 1, change: "abort" },
      { name: "17 actual post-SQL yield cancellation refuses its row and retains ownership", yield: 2, change: "abort" },
      { name: "18 actual pre-SQL yield close retains ownership and executes no SQL", yield: 1, change: "close" },
      { name: "19 actual post-SQL yield close refuses its row and retains ownership", yield: 2, change: "close" },
      { name: "20 actual pre-SQL shared ENV rotation refuses before SQL", yield: 1, change: "env" },
      { name: "21 actual post-SQL shared ENV rotation refuses its selected row", yield: 2, change: "env" }
    ] as const;
    for (const item of yieldCases) await t.test(item.name, async () => {
      const r = reader(); await r.readSession("public");
      const before = Atomics.load(counts, 0), target = Atomics.load(counts, 2) + item.yield, abort = new AbortController();
      Atomics.store(counts, 4, target); Atomics.store(counts, 5, 0); Atomics.store(counts, 6, 0);
      const result = r.readSession("public", abort.signal);
      const outcome = assert.rejects(result, /^Error: Account authorization unavailable$/);
      let closing: Promise<void> | undefined;
      try {
        await waiting(6, target);
        assert.equal(Atomics.load(counts, 0) - before, item.yield === 1 ? 0 : 3);
        if (item.change === "abort") abort.abort();
        else if (item.change === "close") closing = r.close();
        else process.env.DATABASE_URL = `file:${path.join(root, "missing-yield.db")}`;
        if (item.change !== "env") await outcome;
        assert.equal(r.activity().active, 1);
      } finally {
        Atomics.store(counts, 5, 1);
        await outcome; await (closing ?? r.close()); process.env.DATABASE_URL = config;
        Atomics.store(counts, 4, 0);
      }
      assert.equal(Atomics.load(counts, 0) - before, item.yield === 1 ? 0 : 3);
      assert.equal(r.activity().active, 0); assert.equal(r.activity().queued, 0);
    });
    await t.test("22 actual worker ancestor leaf R_OK symlink and missing file fences refuse before SQL", async () => {
      const directory = path.join(root, "denied"), target = path.join(directory, "public.db"); fs.mkdirSync(directory);
      fs.copyFileSync(file, target);
      try {
        for (const kind of ["ancestor", "leaf", "symlink", "missing"] as const) {
          process.env.DATABASE_URL = `file:${target}`;
          if (kind === "ancestor") fs.chmodSync(directory, 0);
          if (kind === "leaf") fs.chmodSync(target, 0);
          if (kind === "symlink") { fs.renameSync(target, target + ".saved"); fs.symlinkSync(target + ".saved", target); }
          if (kind === "missing") process.env.DATABASE_URL = `file:${path.join(directory, "absent.db")}`;
          const before = Atomics.load(counts, 0), r = reader();
          await assert.rejects(r.readSession("public"), /^Error: Account authorization unavailable$/); await r.close();
          assert.equal(Atomics.load(counts, 0), before);
          if (kind === "ancestor") fs.chmodSync(directory, 0o700);
          if (kind === "leaf") fs.chmodSync(target, 0o600);
          if (kind === "symlink") { fs.unlinkSync(target); fs.renameSync(target + ".saved", target); }
        }
      } finally { fs.chmodSync(directory, 0o700); process.env.DATABASE_URL = config; }
    });
    await t.test("23 actual worker absolute literal-percent query and relative URLs select the same Prisma file", async () => {
      for (const name of ["worker%20literal.db", "worker-relative.db"]) {
        const target = path.join(root, name); fs.copyFileSync(file, target);
        const relative = path.relative(path.resolve("prisma"), target).replaceAll("\\", "/");
        const configs = [`file:${target}?connection_limit=1`, `file:${relative}?connection_limit=1`];
        for (const url of configs) {
          process.env.DATABASE_URL = url;
          const prisma = new PrismaClient({ datasources: { db: { url } } }), r = reader(path.resolve("prisma"));
          try {
            assert.deepEqual(await r.readSession("public"), await prisma.user.findUnique({ where: { id: "public" }, select: { id: true, username: true, sessionVersion: true } }));
            assert.deepEqual(await r.readAccount("public"), await prisma.user.findUnique({ where: { id: "public" }, select: { id: true, username: true, sessionVersion: true, role: true, engineAdmin: true } }));
          } finally { await r.close(); await prisma.$disconnect(); }
        }
      }
      process.env.DATABASE_URL = config;
    });
    await t.test("24 real BUSY release observes the completed write without renewing the original envelope", async () => {
      const r = reader(); await r.readSession("public"); writer.exec("BEGIN EXCLUSIVE");
      const pending = r.readAccount("public");
      let released = false;
      const release = setTimeout(() => { writer.exec("UPDATE users SET sessionVersion=3; COMMIT"); released = true; }, 50);
      try { assert.equal((await pending)?.sessionVersion, 3); }
      finally { clearTimeout(release); if (!released) writer.exec("ROLLBACK"); await r.close(); writer.exec("UPDATE users SET sessionVersion=0"); }
    });
    await t.test("25 real held-yield deadline refuses queued work without SQL and retains actual active ownership", async () => {
      const r = reader(); await r.readSession("public");
      const before = Atomics.load(counts, 0), target = Atomics.load(counts, 2) + 1;
      const idle = Atomics.load(counts, 9), activeIdle = Atomics.load(counts, 10), settled = Atomics.load(counts, 11),
        closed = Atomics.load(counts, 12), identities = Atomics.load(counts, 13);
      Atomics.store(counts, 4, target); Atomics.store(counts, 5, 0); Atomics.store(counts, 6, 0);
      const first = r.readSession("public"), next = r.readSession("public");
      const outcomes = Promise.all([assert.rejects(first, /^Error: Account authorization unavailable$/), assert.rejects(next, /^Error: Account authorization unavailable$/)]);
      let closing: Promise<void> | undefined;
      try {
        await waiting(6, target); await outcomes;
        await waiting(9, idle + 1);
        assert.equal(r.activity().active, 1); assert.equal(r.activity().queued, 0);
        assert.equal(Atomics.load(counts, 10), activeIdle + 1);
        closing = r.close();
        assert.equal(Atomics.load(counts, 11), settled);
        assert.equal(Atomics.load(counts, 12), closed);
        assert.equal(Atomics.load(counts, 13), identities);
        assert.equal(Atomics.load(counts, 0), before);
      } finally { Atomics.store(counts, 5, 1); await (closing ?? r.close()); Atomics.store(counts, 4, 0); }
      assert.equal(Atomics.load(counts, 0), before);
      assert.equal(Atomics.load(counts, 11), settled + 1);
      assert.equal(Atomics.load(counts, 12), closed + 2);
      assert.equal(Atomics.load(counts, 13), identities + 1);
      assert.equal(Atomics.load(counts, 15), 0);
    });
    await t.test("26 real successful row and null settle after both yields without entering the refusal drain", async () => {
      const r = reader(), idle = Atomics.load(counts, 9), identities = Atomics.load(counts, 13),
        settled = Atomics.load(counts, 11), callbacks = Atomics.load(counts, 3), forwards = Atomics.load(counts, 7);
      assert.deepEqual(await r.readSession("public"), { id: "public", username: "public", sessionVersion: 0 });
      assert.equal(await r.readAccount("absent"), null);
      assert.equal(Atomics.load(counts, 9), idle);
      assert.equal(Atomics.load(counts, 13), identities + 2);
      assert.equal(Atomics.load(counts, 11), settled + 2);
      assert.equal(Atomics.load(counts, 3), callbacks + 4);
      assert.equal(Atomics.load(counts, 7), forwards + 4);
      assert.equal(Atomics.load(counts, 15), 0);
      assert.equal(r.activity().active, 0); await r.close();
    });
  } finally {
    writer.close(); for (const r of readers) await r.close();
    if (original === undefined) delete process.env.DATABASE_URL; else process.env.DATABASE_URL = original;
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("worker reader fault model retains exact admitted ownership", async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "bortus-worker-model-")), file = path.join(root, "public.db");
  fs.writeFileSync(file, "public"); const original = process.env.DATABASE_URL; process.env.DATABASE_URL = `file:${file}`;
  class PublicWorker extends EventEmitter {
    messages: Array<Record<string, unknown>> = []; terminationRequested = 0;
    postMessage(message: Record<string, unknown>) { this.messages.push(message); }
    ref() { return this; } unref() { return this; }
    terminate(): Promise<number> { this.terminationRequested++; return new Promise(resolve => this.once("exit", resolve)); }
  }
  const workers: PublicWorker[] = [], readers: WorkerAccountReader[] = [];
  const create = () => { const worker = new PublicWorker(); workers.push(worker); return worker as unknown as Worker; };
  function reader() { const r = new WorkerAccountReader(undefined, root,
    path.join(process.cwd(), "runtime/direct-account-reader-worker.cjs"), create); readers.push(r); return r; }
  function reply(worker: PublicWorker, message: Record<string, unknown>, rowId = "public") {
    const stat = fs.lstatSync(file, { bigint: true });
    worker.emit("message", { kind: "settled", id: message.id, refused: false, closeFailed: false,
      row: { id: rowId, username: "public", sessionVersion: 0 }, identity: { dev: stat.dev, ino: stat.ino } });
  }
  function end(worker: PublicWorker) { worker.emit("message", { kind: "closed", closeFailed: false }); worker.emit("exit", 0); }
  try {
    await t.test("07 one admitted and 64 FIFO queued; overflow refuses without another worker or dispatch", async () => {
      const r = reader(); const results = Array.from({ length: 65 }, () => r.readSession("public"));
      const worker = workers.at(-1)!; assert.equal(worker.messages.length, 1);
      assert.deepEqual(r.activity(), { active: 1, queued: 64, closing: false, closeFailed: false });
      await assert.rejects(r.readSession("public"));
      for (let i = 0; i < 65; i++) { assert.equal(worker.messages[i].kind, "read"); reply(worker, worker.messages[i]); }
      assert.equal((await Promise.all(results)).length, 65); const closed = r.close(); end(worker); await closed;
    });
    await t.test("08 rejected caller retains active through refusal-close acknowledgement; queued SQL stays undispatched", async () => {
      const r = reader(), abort = new AbortController(); const first = r.readSession("public", abort.signal), second = r.readSession("public");
      const worker = workers.at(-1)!, message = worker.messages[0]; abort.abort(); await assert.rejects(first);
      assert.equal(Atomics.load(new Int32Array(message.fence as SharedArrayBuffer), 0), 1);
      assert.equal(r.activity().active, 1); assert.equal(worker.messages.length, 1);
      reply(worker, message); assert.equal(worker.messages[1].kind, "discard"); assert.equal(r.activity().active, 1);
      worker.emit("message", { kind: "discarded", id: message.id, closeFailed: false });
      assert.equal(worker.messages[2].kind, "read"); reply(worker, worker.messages[2]); await second;
      const closed = r.close(); end(worker); await closed;
    });
    await t.test("09 close retains owner until actual exit, forbids replacement and fences late replies", async () => {
      const r = reader(), pending = r.readSession("public"), worker = workers.at(-1)!;
      const closing = r.close(); await assert.rejects(pending); await assert.rejects(r.readSession("public"));
      reply(worker, worker.messages[0]); worker.emit("message", { kind: "discarded", id: worker.messages[0].id, closeFailed: false });
      worker.emit("message", { kind: "closed", closeFailed: false }); assert.equal(r.activity().closing, true);
      assert.equal(worker.terminationRequested, 1); worker.emit("exit", 0); await closing;
      reply(worker, worker.messages[0]); assert.equal(r.activity().active, 0);
    });
    await t.test("10 malformed subject cannot pass using a real matching file identity", async () => {
      const r = reader(), result = r.readSession("public"), worker = workers.at(-1)!;
      reply(worker, worker.messages[0], "other"); await assert.rejects(result);
      assert.equal(r.activity().active, 1); assert.equal(worker.messages[1].kind, "discard");
      worker.emit("message", { kind: "discarded", id: worker.messages[0].id, closeFailed: false });
      const closed = r.close(); end(worker); await closed;
    });
    await t.test("11 failed worker termination cannot clear active or create an accumulating replacement", async () => {
      const r = reader(), result = r.readSession("public"), worker = workers.at(-1)!;
      worker.emit("error", new Error("public fault")); await assert.rejects(result);
      assert.equal(r.activity().active, 1); const before = workers.length; await assert.rejects(r.readSession("public"));
      assert.equal(workers.length, before); const closing = r.close(); worker.emit("exit", 1); await assert.rejects(closing);
    });
    await t.test("12 original-call deadline reaches transport unchanged and is not reset by settlement", async () => {
      const r = reader(), start = Number(process.hrtime.bigint()) / 1_000_000, result = r.readSession("public");
      const dispatched = Number(process.hrtime.bigint()) / 1_000_000;
      const worker = workers.at(-1)!, message = worker.messages[0];
      assert.ok(Number(message.deadline) >= start + 5000); assert.ok(Number(message.deadline) <= dispatched + 5000);
      const saved = message.deadline; reply(worker, message); await result; assert.equal(message.deadline, saved);
      const closed = r.close(); end(worker); await closed;
    });
    await t.test("13 exit after close request but before validated acknowledgement rejects close permanently", async () => {
      const r = reader(), result = r.readSession("public"), worker = workers.at(-1)!;
      reply(worker, worker.messages[0]); await result;
      const closing = r.close(); assert.equal(worker.messages.at(-1)?.kind, "close");
      worker.emit("exit", 0); await assert.rejects(closing, /^Error: Account authorization unavailable$/);
      assert.equal(r.activity().closeFailed, true); await assert.rejects(r.readSession("public"));
    });
    await t.test("14 malformed close acknowledgement cannot turn a requested crash into successful close", async () => {
      const r = reader(), result = r.readSession("public"), worker = workers.at(-1)!;
      reply(worker, worker.messages[0]); await result;
      const closing = r.close(); worker.emit("message", { kind: "closed", closeFailed: false, unexpected: true });
      worker.emit("exit", 1); await assert.rejects(closing, /^Error: Account authorization unavailable$/);
      assert.equal(r.activity().closeFailed, true);
    });
  } finally {
    for (let i = 0; i < readers.length; i++) { const closed = readers[i].close().catch(() => {}); end(workers[i]); await closed; }
    if (original === undefined) delete process.env.DATABASE_URL; else process.env.DATABASE_URL = original;
    fs.rmSync(root, { recursive: true, force: true });
  }
});
