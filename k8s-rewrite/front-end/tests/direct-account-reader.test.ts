import { test } from "node:test";
import assert from "node:assert/strict";
import { isDeepStrictEqual } from "node:util";
import { execFileSync, fork, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, rm, rename, chmod, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { DatabaseSync, StatementSync } from "node:sqlite";
import { PrismaClient } from "@prisma/client";
import { DirectAccountReader, accountDatabaseLocation } from "../src/lib/direct-account-reader";

const fixedRefusal = (error: unknown) => error instanceof Error && error.message === "Account authorization unavailable";
const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));
const equalRows = (a: unknown, b: unknown) => assert.ok(isDeepStrictEqual(a, b), "Exact typed projection parity");

test("direct fresh authority uses real independent SQL, bounds and file/schema fences", { timeout: 90000 }, async t => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-direct-account-"));
  const file = path.join(dir, "public.db"), url = `file:${file.replaceAll("\\", "/")}`;
  const env = { ...process.env, DATABASE_URL: url }; delete env.RUST_LOG;
  const readers: DirectAccountReader[] = [], clients: PrismaClient[] = [];
  let child: ChildProcess | undefined;
  const inbox: string[] = [];
  const waiters = new Map<string, { resolve: () => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> }>();
  const receive = (event: string) => {
    const waiter = waiters.get(event);
    if (waiter) { clearTimeout(waiter.timer); waiters.delete(event); waiter.resolve(); }
    else inbox.push(event);
  };
  const event = (name: string) => {
    const index = inbox.indexOf(name); if (index >= 0) { inbox.splice(index, 1); return Promise.resolve(); }
    return new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => { waiters.delete(name); reject(Error("PUBLIC_WRITER_EVENT_REFUSED")); }, 5000);
      waiters.set(name, { resolve, reject, timer });
    });
  };
  const reader = (current = () => url, schema = path.resolve("prisma")) => {
    const value = new DirectAccountReader(current, schema); readers.push(value); return value;
  };
  const client = (config: string) => { const value = new PrismaClient({ datasources: { db: { url: config } } }); clients.push(value); return value; };
  try {
    execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe" });
    const writer = client(url);
    const user = await writer.user.create({ data: { username: "public-reader", passwordHash: "unused-public-fixture", role: "write", engineAdmin: true } });
    child = fork(path.resolve("tests/fixtures/direct-account-writer.cjs"), [file], { execArgv: [], stdio: ["ignore", "ignore", "inherit", "ipc"] });
    child.on("message", message => {
      const value = message as { event?: string };
      if (value.event === "refused") receive("refused"); else if (typeof value.event === "string") receive(value.event);
    });
    await event("ready");
    const active = reader();
    await t.test("Prisma projections match, missing identity is null, completed writes revoke between reads", async () => {
      equalRows(await active.readSession(user.id), await writer.user.findUnique({ where: { id: user.id }, select: { id: true, username: true, sessionVersion: true } }));
      equalRows(await active.readAccount(user.id), await writer.user.findUnique({ where: { id: user.id }, select: { id: true, username: true, sessionVersion: true, role: true, engineAdmin: true } }));
      assert.equal(await active.readSession("absent-public-subject"), null);
      const before = (await active.readSession(user.id))!.sessionVersion;
      child!.send({ operation: "reset", subject: user.id }); await event("reset");
      assert.equal((await active.readAccount(user.id))!.sessionVersion, before + 1);
      await writer.user.update({ where: { id: user.id }, data: { role: "readonly", engineAdmin: false } });
      assert.equal((await active.readAccount(user.id))!.role, "readonly");
      assert.equal((await active.readAccount(user.id))!.engineAdmin, false);
    });
    await t.test("actual Prisma literal-percent/query and schema-relative paths select the same file", async () => {
      for (const name of ["literal%20.db", "relative.db"]) {
        const target = path.join(dir, name), db = new DatabaseSync(target);
        db.exec('CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT NOT NULL,sessionVersion INTEGER NOT NULL,role TEXT NOT NULL,engineAdmin BOOLEAN NOT NULL)');
        db.prepare('INSERT INTO users VALUES(?,?,?,?,?)').run("public-path", "public", 7, "readonly", 0); db.close();
        const config = `file:${name}?connection_limit=1`, prisma = client(`file:${target.replaceAll("\\", "/")}?connection_limit=1`);
        const selected = reader(() => config, dir);
        assert.equal(accountDatabaseLocation(config, dir), target);
        equalRows(await selected.readSession("public-path"), await prisma.user.findUnique({ where: { id: "public-path" }, select: { id: true, username: true, sessionVersion: true } }));
      }
      for (const config of [undefined, "postgresql:public", "file:", "file://remote/path", "file:bad\0path"]) {
        await assert.rejects(reader(() => config).readSession(user.id), fixedRefusal);
      }
    });
    await t.test("noncanonical SQLite boolean integers preserve actual Prisma BOOLEAN interpretation", async () => {
      const db = new DatabaseSync(file);
      try {
        for (const value of [2n, -1n, 9223372036854775807n]) {
          db.prepare('UPDATE users SET engineAdmin=? WHERE id=?').run(value, user.id);
          equalRows(await active.readAccount(user.id), await writer.user.findUnique({ where: { id: user.id }, select: { id: true, username: true, sessionVersion: true, role: true, engineAdmin: true } }));
        }
      } finally { db.prepare('UPDATE users SET engineAdmin=0 WHERE id=?').run(user.id); db.close(); }
    });
    await t.test("real BUSY retries yield to event loop and release observes fresh state", async () => {
      child!.send({ operation: "lock" }); await event("locked");
      let ticks = 0; const timer = setInterval(() => ticks++, 5);
      const pending = active.readSession(user.id);
      try {
        await sleep(100); assert.equal(active.activity().active, 1); assert.ok(ticks >= 5, "Event loop advances while lock is held");
        child!.send({ operation: "release" }); await event("released");
        assert.ok(await pending); assert.equal(active.activity().active, 0);
      } finally { clearInterval(timer); }
    });
    await t.test("one active plus64 queued, 65th queue refusal, cancellation and actual close/drain", async () => {
      child!.send({ operation: "lock" }); await event("locked");
      const bounded = reader(), signals = Array.from({ length: 65 }, () => new AbortController());
      const pending = signals.map(signal => bounded.readSession(user.id, signal.signal));
      const outcomes = Promise.allSettled(pending);
      assert.deepEqual(bounded.activity(), { active: 1, queued: 64, closing: false, closeFailed: false });
      await assert.rejects(bounded.readSession(user.id), fixedRefusal);
      signals[30].abort(); assert.equal(bounded.activity().queued, 63);
      const closed = bounded.close(); assert.equal(bounded.activity().closing, true);
      assert.ok((await outcomes).every(result => result.status === "rejected" && fixedRefusal(result.reason)));
      await closed; assert.equal(bounded.activity().active, 0); assert.equal(bounded.activity().queued, 0);
      child!.send({ operation: "release" }); await event("released");
      assert.ok(await bounded.readSession(user.id), "Close completes before a later fresh reopen");
    });
    await t.test("original5000ms envelope expires queued work without executing its subject SQL", async () => {
      child!.send({ operation: "lock" }); await event("locked");
      const bounded = reader(); let expiredSubjectCalls = 0;
      const get = StatementSync.prototype.get;
      StatementSync.prototype.get = function (this: StatementSync, ...args: unknown[]) {
        if (args[0] === "must-expire-without-read") expiredSubjectCalls++;
        return Reflect.apply(get, this, args);
      } as typeof get;
      const began = performance.now();
      try {
        const outcomes = await Promise.allSettled([bounded.readSession(user.id), bounded.readSession("must-expire-without-read")]);
        assert.ok(outcomes.every(result => result.status === "rejected" && fixedRefusal(result.reason)));
        assert.ok(performance.now() - began >= 4900, "No shortened busy/admission envelope");
        assert.equal(expiredSubjectCalls, 0); await bounded.close(); assert.equal(bounded.activity().active, 0);
      } finally { StatementSync.prototype.get = get; child!.send({ operation: "release" }); await event("released"); }
    });
    await t.test("identity replacement refuses old handle before later validated reopen", async () => {
      const old = path.join(dir, "old-public.db");
      const replacement = reader(); assert.ok(await replacement.readSession(user.id));
      await rename(file, old);
      const db = new DatabaseSync(file);
      db.exec('CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT NOT NULL,sessionVersion INTEGER NOT NULL,role TEXT NOT NULL,engineAdmin BOOLEAN NOT NULL)'); db.close();
      await assert.rejects(replacement.readSession(user.id), fixedRefusal);
      assert.equal(await replacement.readSession(user.id), null); await replacement.close();
      await rm(file); await rename(old, file);
    });
    await t.test("configuration replacement refuses that operation and never reuses old rows", async () => {
      let config = url; const selected = reader(() => config); assert.ok(await selected.readSession(user.id));
      config = `file:${path.join(dir, "literal%20.db")}`;
      await assert.rejects(selected.readSession(user.id), fixedRefusal);
      assert.equal(await selected.readSession(user.id), null); assert.ok(await selected.readSession("public-path"));
    });
    await t.test("nonroot permissions, symlink and missing-column schema refuse with fixed errors", async () => {
      assert.notEqual(process.getuid?.(), 0, "EACCES controls require actual nonroot runtime");
      const permission = reader(); assert.ok(await permission.readSession(user.id));
      await chmod(file, 0);
      try { await assert.rejects(permission.readSession(user.id), fixedRefusal); } finally { await chmod(file, 0o600); }
      const link = path.join(dir, "public-link.db"); await symlink(file, link);
      await assert.rejects(reader(() => `file:${link}`).readSession(user.id), fixedRefusal);
      const bad = path.join(dir, "bad-schema.db"), db = new DatabaseSync(bad);
      db.exec('CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT,sessionVersion INTEGER,role TEXT)'); db.close();
      await assert.rejects(reader(() => `file:${bad}`).readSession(user.id), fixedRefusal);
    });
    await t.test("schema changes and malformed selected fields are detected without authority fallback", async () => {
      const db = new DatabaseSync(file);
      try {
        db.exec('ALTER TABLE users ADD COLUMN publicExtra TEXT'); assert.ok(await active.readSession(user.id));
        db.prepare('UPDATE users SET sessionVersion=? WHERE id=?').run(2147483648n, user.id);
        await assert.rejects(active.readSession(user.id), fixedRefusal);
        db.prepare('UPDATE users SET sessionVersion=? WHERE id=?').run(1n, user.id);
        assert.ok(await active.readSession(user.id));
      } finally { db.close(); }
    });
    await t.test("deletion after a successful read cannot reuse prior authority", async () => {
      assert.ok(await active.readAccount(user.id)); await writer.user.delete({ where: { id: user.id } });
      assert.equal(await active.readSession(user.id), null); assert.equal(await active.readAccount(user.id), null);
    });
  } finally {
    for (const waiter of waiters.values()) { clearTimeout(waiter.timer); waiter.reject(Error("PUBLIC_FIXTURE_CLOSED")); }
    await Promise.all(readers.map(value => value.close()));
    if (child && child.exitCode === null && child.signalCode === null) {
      const exit = once(child, "exit"); if (child.connected) child.send({ operation: "close" }); else child.kill("SIGTERM");
      const force = setTimeout(() => child!.kill("SIGKILL"), 1000);
      try { await exit; } finally { clearTimeout(force); }
    }
    await Promise.all(clients.map(value => value.$disconnect()));
    if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-direct-account-")) throw Error("Unsafe public fixture cleanup");
    await rm(dir, { recursive: true, force: true });
  }
});
