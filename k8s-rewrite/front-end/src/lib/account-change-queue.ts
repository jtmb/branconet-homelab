const busyBrand = Symbol.for("bortus.account-change.busy.v1");
const busyCode = "BORTUS_ACCOUNT_QUEUE_BUSY";
export class AccountQueueBusyError extends Error {
  readonly code = busyCode;
  constructor() {
    super("Account change is busy; retry shortly");
    Object.defineProperty(this, busyBrand, { value: true });
  }
}

export function isAccountQueueBusy(error: unknown): boolean {
  return typeof error === "object" && error !== null &&
    (error as Record<symbol, unknown>)[busyBrand] === true &&
    (error as { code?: unknown }).code === busyCode;
}

type Pending = { start: () => void; reject: () => void; expiresAt: number; timer: ReturnType<typeof setTimeout> };

/** Non-reentrant process admission only. The database lock remains authoritative. */
export class AccountChangeQueue {
  private active = false;
  private readonly pending: Pending[] = [];

  constructor(private readonly maxQueued = 64, private readonly queueWaitMs = 10000) {
    if (!Number.isSafeInteger(maxQueued) || maxQueued < 0 || !Number.isFinite(queueWaitMs) || queueWaitMs <= 0)
      throw new Error("Invalid account queue bounds");
  }

  run<T>(operation: () => Promise<T>): Promise<T> {
    if (this.active && this.pending.length >= this.maxQueued) return Promise.reject(new AccountQueueBusyError());
    return new Promise<T>((resolve, reject) => {
      const start = () => {
        this.active = true;
        // Ownership lasts until the actual callback settles, including database retries.
        void Promise.resolve().then(operation).then(resolve, reject).finally(() => this.advance());
      };
      if (!this.active) { start(); return; }
      const entry: Pending = {
        start, reject: () => reject(new AccountQueueBusyError()),
        expiresAt: performance.now() + this.queueWaitMs,
        timer: setTimeout(() => {
          const index = this.pending.indexOf(entry);
          if (index === -1) return;
          this.pending.splice(index, 1);
          entry.reject();
        }, this.queueWaitMs),
      };
      this.pending.push(entry);
    });
  }

  private advance() {
    this.active = false;
    while (this.pending.length) {
      const entry = this.pending.shift()!;
      clearTimeout(entry.timer);
      if (performance.now() >= entry.expiresAt) { entry.reject(); continue; }
      entry.start();
      break;
    }
  }

  diagnostics() { return { active: Number(this.active), queued: this.pending.length }; }
}

const globalQueue = globalThis as typeof globalThis & { __bortusAccountChangesV1?: AccountChangeQueue };
export function accountChangeQueue() {
  return globalQueue.__bortusAccountChangesV1 ??= new AccountChangeQueue();
}
