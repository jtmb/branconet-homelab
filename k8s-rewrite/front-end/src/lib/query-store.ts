export interface QuerySnapshot<T = unknown> {
  data?: T; error?: string; status?: number;
  loading: boolean; refreshing: boolean; updatedAt: number;
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
  private async run(url: string, entry: Entry) {
    if (!this.visible || !entry.listeners.size || entry.controller) return;
    if (entry.timer) this.cancel(entry.timer);
    entry.timer = undefined;
    const controller = new AbortController();
    const generation = entry.generation;
    entry.controller = controller;
    this.publish(entry, { loading: entry.snapshot.data === undefined, refreshing: true });
    try {
      const data = await this.runtime.load(url, controller.signal);
      if (generation !== entry.generation || controller.signal.aborted) return;
      entry.failures = 0;
      this.publish(entry, { data, error: undefined, status: 200, updatedAt: this.now(), loading: false, refreshing: false });
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
          entry.timer = this.schedule(() => { entry.timer = undefined; void this.run(url, entry); }, delay);
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
  clear(match: (url: string) => boolean = () => true) {
    this.entries.forEach((entry, url) => {
      if (!match(url)) return;
      this.stop(entry); entry.snapshot = { ...EMPTY_QUERY, loading: false }; entry.failures = 0;
      entry.listeners.forEach(listener => listener());
      if (!entry.listeners.size) this.entries.delete(url);
    });
  }
}
