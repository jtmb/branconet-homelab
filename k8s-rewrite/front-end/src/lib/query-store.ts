export interface QuerySnapshot<T = unknown> {
  data?: T; error?: string; status?: number;
  loading: boolean; refreshing: boolean; updatedAt: number; stale?: boolean;
}
export const EMPTY_QUERY: QuerySnapshot = Object.freeze({ loading: true, refreshing: false, updatedAt: 0 });
export class QueryFailure extends Error {
  constructor(message: string, public status: number, public data?: unknown) { super(message); }
}
interface Entry {
  snapshot: QuerySnapshot; listeners: Set<() => void>; controller?: AbortController;
  generation: number; failures: number; interval: number; timer?: ReturnType<typeof setTimeout>; usedAt: number;
}
interface QueryRuntime {
  load: (url: string, signal: AbortSignal) => Promise<unknown>;
  now?: () => number; schedule?: typeof setTimeout; cancel?: typeof clearTimeout;
}
/** Metadata queries only. Never use for revealed values, credentials or exports. */
export class QueryStore {
  private entries = new Map<string, Entry>();
  private visible = true;
  private now: () => number;
  private schedule: typeof setTimeout;
  private cancel: typeof clearTimeout;
  constructor(private runtime: QueryRuntime) {
    this.now = runtime.now ?? Date.now;
    this.schedule = runtime.schedule ?? setTimeout.bind(globalThis);
    this.cancel = runtime.cancel ?? clearTimeout.bind(globalThis);
  }
  private entry(url: string): Entry {
    let entry = this.entries.get(url);
    if (!entry) {
      entry = { snapshot: EMPTY_QUERY, listeners: new Set(), generation: 0, failures: 0, interval: 10000, usedAt: this.now() };
      this.entries.set(url, entry);
    }
    return entry;
  }
  snapshot<T>(url: string): QuerySnapshot<T> { return this.entry(url).snapshot as QuerySnapshot<T>; }
  private publish(entry: Entry, patch: Partial<QuerySnapshot>) {
    entry.snapshot = { ...entry.snapshot, ...patch };
    entry.listeners.forEach(listener => listener());
  }
  subscribe(url: string, listener: () => void, interval = 10000) {
    const entry = this.entry(url);
    entry.listeners.add(listener);
    entry.interval = Math.max(1000, interval);
    entry.usedAt = this.now();
    if (entry.listeners.size === 1 && this.visible) void this.run(url, entry);
    return () => {
      entry.listeners.delete(listener);
      entry.usedAt = this.now();
      if (!entry.listeners.size) this.stop(entry);
      this.prune();
    };
  }
  private stop(entry: Entry) {
    if (entry.timer) this.cancel(entry.timer);
    entry.timer = undefined;
    entry.generation++;
    entry.controller?.abort();
    entry.controller = undefined;
    this.publish(entry, { loading: entry.snapshot.data === undefined, refreshing: false });
  }
  private prune() {
    const inactive = [...this.entries].filter(([, e]) => !e.listeners.size).sort((a, b) => a[1].usedAt - b[1].usedAt);
    inactive.forEach(([url, e], i) => {
      if (this.now() - e.usedAt > 300000 || i < inactive.length - 32) this.entries.delete(url);
    });
  }
  private expire(entry: Entry) {
    if (entry.snapshot.data !== undefined && !entry.snapshot.stale && this.now() - entry.snapshot.updatedAt >= 15000)
      this.publish(entry, { stale: true });
  }
  /** A single timer alternates freshness notification and polling, including slow in-flight loads. */
  private watchPendingFreshness(entry: Entry) {
    this.expire(entry);
    if (entry.snapshot.data === undefined || entry.snapshot.stale) return;
    entry.timer = this.schedule(() => { entry.timer = undefined; this.expire(entry); }, Math.max(1, entry.snapshot.updatedAt + 15000 - this.now()));
  }
  private scheduleNext(url: string, entry: Entry, refreshAt: number) {
    if (entry.timer) this.cancel(entry.timer);
    entry.timer = undefined;
    this.expire(entry);
    const untilRefresh = Math.max(1, refreshAt - this.now());
    const untilExpiry = entry.snapshot.data !== undefined && !entry.snapshot.stale
      ? Math.max(1, entry.snapshot.updatedAt + 15000 - this.now()) : Infinity;
    entry.timer = this.schedule(() => {
      entry.timer = undefined;
      if (this.now() >= refreshAt) void this.run(url, entry);
      else { this.expire(entry); this.scheduleNext(url, entry, refreshAt); }
    }, Math.min(untilRefresh, untilExpiry));
  }
  private async run(url: string, entry: Entry) {
    if (!this.visible || !entry.listeners.size || entry.controller) return;
    if (entry.timer) this.cancel(entry.timer);
    entry.timer = undefined;
    const controller = new AbortController();
    const generation = entry.generation;
    entry.controller = controller;
    this.watchPendingFreshness(entry);
    this.publish(entry, { loading: entry.snapshot.data === undefined, refreshing: true });
    try {
      const data = await this.runtime.load(url, controller.signal);
      if (generation !== entry.generation || controller.signal.aborted) return;
      entry.failures = 0;
      this.publish(entry, { data, error: undefined, status: 200, updatedAt: this.now(), loading: false, refreshing: false, stale: false });
    } catch (error) {
      if (generation !== entry.generation || controller.signal.aborted) return;
      entry.failures++;
      const failure = error instanceof QueryFailure ? error : undefined;
      this.publish(entry, {
        data: failure?.status === 401 ? undefined : entry.snapshot.data,
        error: failure?.message ?? "Request failed. Try again.", status: failure?.status, loading: false, refreshing: false,
      });
    } finally {
      if (generation === entry.generation) {
        entry.controller = undefined;
        if (this.visible && entry.listeners.size) {
          const delay = Math.min(60000, entry.interval * 2 ** Math.min(entry.failures, 3));
          this.scheduleNext(url, entry, this.now() + delay);
        }
      }
    }
  }
  setVisible(visible: boolean) {
    if (this.visible === visible) return;
    this.visible = visible;
    this.entries.forEach((entry, url) => {
      this.stop(entry);
      if (visible && entry.listeners.size) void this.run(url, entry);
    });
  }
  invalidate(match: (url: string) => boolean = () => true) {
    this.entries.forEach((entry, url) => {
      if (!match(url)) return;
      this.stop(entry); entry.failures = 0;
      if (entry.listeners.size && this.visible) void this.run(url, entry);
    });
  }
  /** Focus shares a current fresh read; explicit invalidation still replaces its generation. */
  refreshActive() {
    this.entries.forEach((entry, url) => {
      if (this.visible && entry.listeners.size) void this.run(url, entry);
    });
  }
  clear(match: (url: string) => boolean = () => true) {
    this.entries.forEach((entry, url) => {
      if (!match(url)) return;
      this.stop(entry); entry.snapshot = { ...EMPTY_QUERY, loading: false }; entry.failures = 0;
      entry.listeners.forEach(listener => listener());
      if (!entry.listeners.size) this.entries.delete(url);
    });
  }
}
