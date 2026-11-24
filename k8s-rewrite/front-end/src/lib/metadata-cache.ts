import { SecretError } from "./cluster-secrets";

// Use only for bounded, nonsecret metadata. A timed-out worker keeps its slot until it settles.
export class MetadataCache<T> {
  private key?: string;
  private generation = 0;
  private cached?: { value: T; expires: number };
  private failure?: { error: unknown; expires: number };
  private worker?: { result: Promise<T> };
  constructor(readonly load: (key: string, signal: AbortSignal) => Promise<T>, readonly ttl = 10000,
    readonly timeout = 5000, readonly now: () => number = Date.now) {}
  invalidate() { this.generation++; this.cached = undefined; this.failure = undefined; }
  get(key: string): Promise<T> {
    if (key !== this.key) { this.invalidate(); this.key = key; }
    if (this.cached && this.cached.expires > this.now()) return Promise.resolve(this.cached.value);
    if (this.failure && this.failure.expires > this.now()) return Promise.reject(this.failure.error);
    if (this.worker) return this.worker.result;
    const generation = this.generation, deadline = this.now() + this.timeout, controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const task = Promise.resolve().then(() => this.load(key, controller.signal)).then(value => {
      if (generation !== this.generation || key !== this.key || this.now() >= deadline)
        throw new SecretError(503, "Metadata refresh changed or exceeded its deadline");
      this.cached = { value, expires: this.now() + this.ttl }; return value;
    });
    const worker = { result: Promise.race([task, new Promise<never>((_, reject) => {
      timer = setTimeout(() => { controller.abort(); reject(new SecretError(503, "Metadata refresh timed out")); }, this.timeout);
    })]).catch(error => {
      if (generation === this.generation) this.failure = { error, expires: this.now() + 2000 };
      throw error;
    }).finally(() => clearTimeout(timer)) };
    this.worker = worker;
    void task.finally(() => { if (this.worker === worker) this.worker = undefined; }).catch(() => {});
    return worker.result;
  }
}
