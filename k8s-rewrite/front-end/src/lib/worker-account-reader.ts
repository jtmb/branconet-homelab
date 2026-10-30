import path from "node:path";
import { constants, lstatSync, readFileSync } from "node:fs";
import { accessSync } from "node:fs";
import { createHash } from "node:crypto";
import { Worker, SHARE_ENV, MessageChannel, MessagePort, receiveMessageOnPort } from "node:worker_threads";
import { accountDatabaseLocation, type SessionRow, type AccountRow } from "./direct-account-core";

type Row = SessionRow | AccountRow | null;
type Projection = "session" | "account";
type Operation = { id: number; subject: string; projection: Projection; config: string; file: string;
  deadline: number; fence: Int32Array<SharedArrayBuffer>; settled: boolean; cancelled: boolean; refusing?: boolean;
  resolve: (row: Row) => void; reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>; signal?: AbortSignal; abort?: () => void };
const unavailable = () => new Error("Account authorization unavailable");
// Same process monotonic clock in parent and worker; no per-receive deadline reset.
const now = () => Number(process.hrtime.bigint()) / 1_000_000;

function identity(file: string) {
  let current = path.parse(file).root;
  const parts = [current];
  for (const component of file.slice(current.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, component); parts.push(current);
  }
  const checks = parts.map(part => { try { return lstatSync(part, { bigint: part === file }); } catch { return undefined; } });
  let readable = false; try { accessSync(file, constants.R_OK); readable = true; } catch { /* Fixed refusal below. */ }
  if (!readable || checks.some((stat, index) => !stat || stat.isSymbolicLink() ||
    (index === checks.length - 1 ? !stat.isFile() : !stat.isDirectory()))) throw unavailable();
  const leaf = checks[checks.length - 1]!;
  if (typeof leaf.dev !== "bigint" || typeof leaf.ino !== "bigint") throw unavailable();
  return { dev: leaf.dev, ino: leaf.ino };
}

/** Evaluation transport. No rows, sessions or authority are retained between calls. */
export class WorkerAccountReader {
  private worker?: Worker;
  private responsePort?: MessagePort;
  private transferredPort?: MessagePort;
  private active?: Operation;
  private queued: Operation[] = [];
  private nextId = 0;
  private closing = false;
  private closeFailed = false;
  private shutdownRequested = false;
  private validatedCloseAck = false;
  private expectedTermination = false;
  private closedWaiters: { resolve: () => void; reject: (error: Error) => void }[] = [];
  constructor(private readonly currentConfig = () => process.env.DATABASE_URL,
    private readonly schemaDirectory = path.join(process.cwd(), "prisma"),
    private readonly workerFile = path.join(process.cwd(), "runtime", "direct-account-reader-worker.cjs"),
    private readonly createWorker = (file: string, settlementPort?: MessagePort) => new Worker(file, { env: SHARE_ENV,
      ...(settlementPort ? { workerData: { settlementPort }, transferList: [settlementPort] } : {}) })) {}

  readSession(subject: string, signal?: AbortSignal): Promise<SessionRow | null> {
    return this.read(subject, "session", signal) as Promise<SessionRow | null>;
  }
  readAccount(subject: string, signal?: AbortSignal): Promise<AccountRow | null> {
    return this.read(subject, "account", signal) as Promise<AccountRow | null>;
  }
  activity() { return { active: this.active ? 1 : 0, queued: this.queued.length, closing: this.closing, closeFailed: this.closeFailed }; }
  private read(subject: string, projection: Projection, signal?: AbortSignal): Promise<Row> {
    this.drainPendingSettlement();
    let config: string, file: string;
    try {
      config = this.currentConfig()!; file = accountDatabaseLocation(config, this.schemaDirectory);
      if (typeof subject !== "string" || signal?.aborted || this.closing || this.closeFailed || this.queued.length >= 64) throw unavailable();
    } catch { return Promise.reject(unavailable()); }
    return new Promise((resolve, reject) => {
      const operation: Operation = { id: ++this.nextId, subject, projection, config, file,
        deadline: now() + 5000, fence: new Int32Array(new SharedArrayBuffer(4)), settled: false, cancelled: false,
        resolve, reject, timer: setTimeout(() => this.expire(operation), 5000), signal };
      operation.abort = () => this.expire(operation);
      signal?.addEventListener("abort", operation.abort, { once: true });
      this.queued.push(operation); this.pump();
    });
  }
  private finish(operation: Operation, row?: Row) {
    if (operation.settled) return;
    operation.settled = true; clearTimeout(operation.timer);
    if (operation.abort) operation.signal?.removeEventListener("abort", operation.abort);
    if (row === undefined) operation.reject(unavailable()); else operation.resolve(row);
  }
  private expire(operation: Operation) {
    operation.cancelled = true; Atomics.store(operation.fence, 0, 1); this.finish(operation);
    const index = this.queued.indexOf(operation); if (index >= 0) this.queued.splice(index, 1);
    // The admitted slot remains owned until the worker reports actual core settlement or exits.
  }
  private live(operation: Operation) {
    if (this.closing || this.closeFailed || operation.cancelled || now() >= operation.deadline ||
      operation.config !== this.currentConfig()) throw unavailable();
  }
  private drainPendingSettlement() {
    if (!this.responsePort || !this.worker || this.closing || this.closeFailed) return;
    const worker = this.worker;
    try {
      const pending = receiveMessageOnPort(this.responsePort);
      if (pending) this.receive(worker, pending.message);
    } catch { this.poison(worker); }
  }
  private attach(): Worker {
    if (this.worker) return this.worker;
    const root = path.dirname(this.workerFile), receiptFile = path.join(root, "direct-account-build.json"),
      coreFile = path.join(root, "direct-account-core.cjs");
    for (const file of [this.workerFile, receiptFile, coreFile]) {
      const stat = lstatSync(file); if (!stat.isFile() || stat.isSymbolicLink()) throw unavailable();
    }
    const receipt = JSON.parse(readFileSync(receiptFile, "utf8"));
    const hash = (file: string) => createHash("sha256").update(readFileSync(file)).digest("hex");
    if (receipt.workerSHA256 !== hash(this.workerFile) || receipt.coreSHA256 !== hash(coreFile)) throw unavailable();
    const { port1, port2 } = new MessageChannel();
    let worker: Worker;
    try { worker = this.createWorker(this.workerFile, port2); }
    catch (error) { port1.close(); port2.close(); throw error; }
    this.worker = worker; this.responsePort = port1; this.transferredPort = port2;
    port1.on("message", message => this.receive(worker, message));
    port1.on("messageerror", () => this.poison(worker));
    port1.unref();
    this.validatedCloseAck = false; this.expectedTermination = false;
    worker.on("message", message => this.receive(worker, message));
    worker.on("messageerror", () => this.poison(worker));
    worker.on("error", () => this.poison(worker));
    worker.on("exit", code => {
      if (worker !== this.worker) return;
      this.worker = undefined;
      this.responsePort?.close(); this.transferredPort?.close();
      this.responsePort = undefined; this.transferredPort = undefined;
      if (this.active) { this.finish(this.active); this.active = undefined; }
      for (const operation of this.queued.splice(0)) this.finish(operation);
      if (!this.shutdownRequested || !this.validatedCloseAck || !this.expectedTermination ||
        (code !== 0 && code !== 1)) this.closeFailed = true;
      this.shutdownRequested = false; this.closing = false;
      this.validatedCloseAck = false; this.expectedTermination = false;
      for (const waiter of this.closedWaiters.splice(0)) {
        if (this.closeFailed) waiter.reject(unavailable()); else waiter.resolve();
      }
    });
    return worker;
  }
  private pump() {
    if (this.active || this.closing || this.closeFailed) return;
    const operation = this.queued.shift(); if (!operation) return;
    this.active = operation;
    try { this.live(operation); }
    catch { this.refuse(operation); return; }
    try {
      this.attach().ref();
      this.worker!.postMessage({ kind: "read", id: operation.id, subject: operation.subject,
        projection: operation.projection, config: operation.config, file: operation.file,
        schemaDirectory: this.schemaDirectory, deadline: operation.deadline, fence: operation.fence.buffer });
    } catch {
      if (this.worker) this.poison(this.worker);
      else { this.active = undefined; this.finish(operation); this.pump(); }
    }
  }
  private refuse(operation: Operation) {
    this.finish(operation);
    if (!this.worker) { this.active = undefined; if (this.closing) this.shutdown(); else this.pump(); return; }
    operation.refusing = true;
    try { this.worker.ref(); this.worker.postMessage({ kind: "discard", id: operation.id }); }
    catch { this.poison(this.worker); }
  }
  private row(value: unknown, operation: Operation): Row {
    if (value === null) return null;
    if (!value || typeof value !== "object") throw unavailable();
    const row = value as AccountRow;
    const keys = operation.projection === "session" ? "id,sessionVersion,username" : "engineAdmin,id,role,sessionVersion,username";
    if (Object.keys(row).sort().join(",") !== keys || row.id !== operation.subject || typeof row.username !== "string" ||
      !Number.isInteger(row.sessionVersion) || row.sessionVersion < -2147483648 || row.sessionVersion > 2147483647 ||
      operation.projection === "account" && (typeof row.role !== "string" || typeof row.engineAdmin !== "boolean")) throw unavailable();
    return row;
  }
  private receive(worker: Worker, message: unknown) {
    if (worker !== this.worker) return;
    const value = message as { kind?: unknown; id?: unknown; refused?: unknown; row?: unknown;
      identity?: { dev?: unknown; ino?: unknown }; closeFailed?: unknown };
    if (value?.kind === "closed" && this.shutdownRequested && !this.active) {
      if (this.validatedCloseAck || value.closeFailed !== false || Object.keys(value).sort().join(",") !== "closeFailed,kind") {
        this.poison(worker); return;
      }
      this.validatedCloseAck = true; this.expectedTermination = true;
      void worker.terminate().catch(() => { this.closeFailed = true; }); return;
    }
    const operation = this.active;
    if (operation?.refusing && value?.kind === "discarded" && value.id === operation.id && typeof value.closeFailed === "boolean") {
      if (value.closeFailed) { this.poison(worker); return; }
      this.active = undefined;
      if (this.closing) this.shutdown(); else { this.pump(); if (!this.active) worker.unref(); }
      return;
    }
    if (!operation || value?.kind !== "settled" || value.id !== operation.id || typeof value.refused !== "boolean" ||
      typeof value.closeFailed !== "boolean") { this.poison(worker); return; }
    if (value.closeFailed) { this.poison(worker); return; }
    let row: Row | undefined;
    try {
      this.live(operation);
      if (value.refused) throw unavailable();
      row = this.row(value.row, operation);
      const current = identity(operation.file);
      if (value.identity?.dev !== current.dev || value.identity?.ino !== current.ino) throw unavailable();
      this.live(operation);
    } catch { this.refuse(operation); return; }
    this.active = undefined; this.finish(operation, row);
    if (this.closing) this.shutdown(); else { this.pump(); if (!this.active) worker.unref(); }
  }
  private poison(worker: Worker) {
    if (worker !== this.worker) return;
    this.closing = true; this.closeFailed = true;
    if (this.active) this.expire(this.active);
    for (const operation of this.queued.splice(0)) this.expire(operation);
    // No replacement is possible until actual exit; a failed termination retains ownership.
    worker.ref(); void worker.terminate().catch(() => { this.closeFailed = true; });
  }
  private shutdown() {
    if (this.active) return;
    if (!this.worker) {
      this.closing = false;
      for (const waiter of this.closedWaiters.splice(0)) {
        if (this.closeFailed) waiter.reject(unavailable()); else waiter.resolve();
      }
      return;
    }
    if (this.shutdownRequested) return;
    this.shutdownRequested = true;
    try { this.worker.ref(); this.worker.postMessage({ kind: "close" }); } catch { this.poison(this.worker); }
  }
  close(): Promise<void> {
    this.closing = true;
    if (this.active) this.expire(this.active);
    for (const operation of this.queued.splice(0)) this.expire(operation);
    return new Promise((resolve, reject) => { this.closedWaiters.push({ resolve, reject }); this.shutdown(); });
  }
}
