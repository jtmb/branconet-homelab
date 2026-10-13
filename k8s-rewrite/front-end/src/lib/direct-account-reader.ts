import path from "node:path";
import { constants } from "node:fs";
import { access, lstat } from "node:fs/promises";
import type { DatabaseSync, StatementSync } from "node:sqlite";

export type SessionRow = { id: string; username: string; sessionVersion: number };
export type AccountRow = SessionRow & { role: string; engineAdmin: boolean };
type Projection = "session" | "account";
type Row = SessionRow | AccountRow | null;
type Identity = { dev: bigint; ino: bigint };
type Operation = { subject: string; projection: Projection; config: string; file: string; deadline: number;
  resolve: (row: Row) => void; reject: (error: Error) => void; settled: boolean; cancelled: boolean;
  timer: ReturnType<typeof setTimeout>; signal?: AbortSignal; abort?: () => void };
type Connection = { db: DatabaseSync; config: string; file: string; identity: Identity;
  version?: StatementSync; schemaVersion?: bigint; session?: StatementSync; account?: StatementSync };
const unavailable = () => new Error("Account authorization unavailable");
const same = (a: Identity, b: Identity) => a.dev === b.dev && a.ino === b.ino;

/** Prisma6 file datasources preserve literal percent bytes and use the schema directory. */
export function accountDatabaseLocation(config: string | undefined, schemaDirectory = path.join(process.cwd(), "prisma")): string {
  if (!config?.startsWith("file:") || config.includes("\0")) throw unavailable();
  const value = config.slice(5).split("?")[0];
  if (!value || value.startsWith("//")) throw unavailable();
  const file = process.platform === "win32" && /^\/[A-Za-z]:\//.test(value) ? value.slice(1) : value;
  return path.resolve(schemaDirectory, file);
}

/** No row/authority cache. SQLite calls are synchronous, with no deliberate lock wait. */
export class DirectAccountReader {
  private connection?: Connection;
  private active?: Operation;
  private queued: Operation[] = [];
  private closing = false;
  private closeFailed = false;
  private closedWaiters: { resolve: () => void; reject: (error: Error) => void }[] = [];
  constructor(private readonly currentConfig = () => process.env.DATABASE_URL,
    private readonly schemaDirectory = path.join(process.cwd(), "prisma")) {}

  readSession(subject: string, signal?: AbortSignal): Promise<SessionRow | null> {
    return this.read(subject, "session", signal) as Promise<SessionRow | null>;
  }
  readAccount(subject: string, signal?: AbortSignal): Promise<AccountRow | null> {
    return this.read(subject, "account", signal) as Promise<AccountRow | null>;
  }
  activity() { return { active: this.active ? 1 : 0, queued: this.queued.length, closing: this.closing, closeFailed: this.closeFailed }; }

  private read(subject: string, projection: Projection, signal?: AbortSignal): Promise<Row> {
    let config: string, file: string;
    try {
      config = this.currentConfig()!; file = accountDatabaseLocation(config, this.schemaDirectory);
      if (typeof subject !== "string" || signal?.aborted || this.closing || this.closeFailed || this.queued.length >= 64) throw unavailable();
    } catch { return Promise.reject(unavailable()); }
    return new Promise((resolve, reject) => {
      const operation: Operation = { subject, projection, config, file, deadline: performance.now() + 5000,
        resolve, reject, settled: false, cancelled: false, timer: setTimeout(() => this.expire(operation), 5000), signal };
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
    operation.cancelled = true; this.finish(operation);
    // An active read still owns its connection until actual asynchronous checks settle.
    const index = this.queued.indexOf(operation);
    if (index >= 0) this.queued.splice(index, 1);
  }
  private live(operation: Operation) {
    if (this.closing || this.closeFailed || operation.cancelled || operation.deadline <= performance.now() ||
      operation.config !== this.currentConfig()) throw unavailable();
  }
  private pump() {
    if (this.active || this.closing || this.closeFailed) return;
    const operation = this.queued.shift(); if (!operation) return;
    this.active = operation;
    void (async () => {
      let row: Row | undefined;
      try { row = await this.execute(operation); this.live(operation); }
      catch { row = undefined; try { this.discard(); } catch { /* A failed close keeps this owner unavailable. */ } }
      this.active = undefined; this.finish(operation, row);
      if (this.closing) this.finishClose(); else this.pump();
    })();
  }
  private async identity(file: string): Promise<Identity> {
    let current = path.parse(file).root;
    const parts = [current];
    for (const component of file.slice(current.length).split(path.sep).filter(Boolean)) {
      current = path.join(current, component); parts.push(current);
    }
    // Retain the active owner until every initiated check settles, including faults.
    const checks = await Promise.allSettled([...parts.map(part => Promise.resolve().then(() => lstat(part, { bigint: true }))),
      Promise.resolve().then(() => access(file, constants.R_OK))]);
    if (checks.some(check => check.status === "rejected")) throw unavailable();
    const stats = checks.slice(0, -1).map(check => {
      if (check.status !== "fulfilled" || !check.value) throw unavailable();
      return check.value;
    });
    if (stats.some((stat, index) => stat.isSymbolicLink() || (index === stats.length - 1 ? !stat.isFile() : !stat.isDirectory()))) throw unavailable();
    const leaf = stats[stats.length - 1]; return { dev: leaf.dev, ino: leaf.ino };
  }
  private discard() {
    const connection = this.connection;
    if (!connection) return;
    try { connection.db.close(); this.connection = undefined; }
    catch { this.closeFailed = true; throw unavailable(); }
  }
  private schema(connection: Connection): bigint {
    connection.version ??= connection.db.prepare("PRAGMA schema_version");
    const version = connection.version.get()?.schema_version;
    if (typeof version !== "bigint" || version < 0n || version > 2147483647n) throw unavailable();
    if (version !== connection.schemaVersion) {
      const table = connection.db.prepare("SELECT type FROM sqlite_master WHERE name='users'").get();
      const columns = connection.db.prepare("PRAGMA table_info(users)").all();
      const required = { id: "TEXT", username: "TEXT", sessionVersion: "INTEGER", role: "TEXT", engineAdmin: "BOOLEAN" };
      if (table?.type !== "table" || Object.entries(required).some(([name, type]) => !columns.some(column => column.name === name &&
        typeof column.type === "string" && column.type.toUpperCase() === type)) ||
        columns.filter(column => column.pk !== 0n).length !== 1 || !columns.some(column => column.name === "id" && column.pk === 1n)) throw unavailable();
      connection.session = connection.db.prepare("SELECT id,username,sessionVersion FROM users WHERE id=?");
      connection.account = connection.db.prepare("SELECT id,username,sessionVersion,role,engineAdmin FROM users WHERE id=?");
      connection.schemaVersion = version;
    }
    return version;
  }
  private async execute(operation: Operation): Promise<Row> {
    try {
      for (;;) {
        this.live(operation);
        const identity = await this.identity(operation.file); this.live(operation);
        if (this.connection && (this.connection.config !== operation.config || this.connection.file !== operation.file ||
          !same(this.connection.identity, identity))) throw unavailable();
        try {
          if (!this.connection) {
            const { DatabaseSync } = await import("node:sqlite"); this.live(operation);
            const db = new DatabaseSync(operation.file, { readOnly: true, allowExtension: false, timeout: 0, readBigInts: true });
            // Retain the owner even if preparation/schema validation subsequently fails.
            this.connection = { db, config: operation.config, file: operation.file, identity };
          }
          const connection = this.connection;
          const version = this.schema(connection);
          const row = (operation.projection === "session" ? connection.session! : connection.account!).get(operation.subject);
          if (connection.version!.get()?.schema_version !== version) throw unavailable();
          const result = this.project(row, operation);
          const after = await this.identity(operation.file); this.live(operation);
          if (!same(after, connection.identity)) throw unavailable();
          return result;
        } catch (error) {
          // Numeric SQLite BUSY only; no dynamic error text or mutation retry.
          const busy = error as { code?: string; errcode?: number };
          if (busy?.code !== "ERR_SQLITE_ERROR" || !Number.isInteger(busy.errcode) || (busy.errcode! & 255) !== 5) throw error;
          this.live(operation);
          await new Promise<void>(resolve => setTimeout(resolve, Math.min(25, Math.max(0, operation.deadline - performance.now()))));
        }
      }
    } catch {
      this.discard(); throw unavailable();
    }
  }
  private project(row: ReturnType<StatementSync["get"]>, operation: Operation): Row {
    if (!row) return null;
    if (row.id !== operation.subject || typeof row.username !== "string" || typeof row.sessionVersion !== "bigint" ||
      row.sessionVersion < -2147483648n || row.sessionVersion > 2147483647n) throw unavailable();
    const result: SessionRow = { id: operation.subject, username: row.username, sessionVersion: Number(row.sessionVersion) };
    if (operation.projection === "session") return result;
    if (typeof row.role !== "string" || typeof row.engineAdmin !== "bigint") throw unavailable();
    return { ...result, role: row.role, engineAdmin: row.engineAdmin !== 0n };
  }
  private finishClose() {
    if (this.active) return;
    try {
      this.discard(); this.closing = false;
      for (const waiter of this.closedWaiters.splice(0)) waiter.resolve();
    } catch { for (const waiter of this.closedWaiters.splice(0)) waiter.reject(unavailable()); }
  }
  close(): Promise<void> {
    this.closing = true;
    if (this.active) this.expire(this.active);
    for (const operation of this.queued.splice(0)) this.expire(operation);
    return new Promise<void>((resolve, reject) => { this.closedWaiters.push({ resolve, reject }); this.finishClose(); });
  }
}

const scope = globalThis as typeof globalThis & { __bortusDirectAccountReader?: DirectAccountReader };
export const directAccountReader = scope.__bortusDirectAccountReader ??= new DirectAccountReader();
