import { randomUUID } from "node:crypto";
import type { Scanner } from "./system-report-scanner";
import { resultStale, type Inventory, type ScanResult, type SystemReport } from "./system-report-types";

export const REPORT_LIMITS = { images: 256, deadlineMs: 10 * 60000, cacheBytes: 32 * 1024 * 1024, resultBytes: 16 * 1024 * 1024, cacheMs: 6 * 3600000 };
export class ReportRequestError extends Error { constructor(public status: number, message: string) { super(message); } }
interface CacheEntry { result: ScanResult; expires: number; bytes: number }

/** In-process job, using BORTUS's existing cancellation registry. No database/inventory persistence. */
export class SystemReportJobs {
  private job: SystemReport["job"] = null;
  private results = new Map<string, ScanResult>();
  private cache = new Map<string, CacheEntry>();
  private cacheBytes = 0;
  private starting?: Promise<SystemReport["job"]>;
  private drain?: Promise<void>;
  constructor(private inventory: () => Promise<Inventory>, private scanner: Scanner,
    private controllers: Map<string, AbortController>, private now = Date.now,
    private limits = REPORT_LIMITS) {}

  async report(): Promise<SystemReport> {
    const [inventory, scanner] = await Promise.all([this.inventory(), this.scanner.status()]);
    const { configured, message } = scanner;
    return { ...inventory, scanner: { configured, message }, job: this.job ? { ...this.job } : null,
      images: inventory.images.map(image => ({ ...image, ...(this.results.get(image.key) ?? {}) })) };
  }

  start(): Promise<SystemReport["job"]> {
    if (this.starting) return this.starting;
    if (this.job?.state === "running") return Promise.resolve({ ...this.job });
    const flight = this.prepare();
    this.starting = flight;
    void flight.finally(() => { if (this.starting === flight) this.starting = undefined; }).catch(() => {});
    return flight;
  }

  private async prepare() {
    const [inventory, scanner] = await Promise.all([this.inventory(), this.scanner.status()]);
    if (!inventory.available || inventory.stale) throw new ReportRequestError(503, "A current Pod inventory is required before scanning.");
    if (!scanner.configured) throw new ReportRequestError(501, scanner.message);
    if (inventory.images.length > this.limits.images) throw new ReportRequestError(422, `Inventory exceeds the ${this.limits.images}-image job limit; coverage remains incomplete.`);
    const controller = new AbortController(), id = `system-report:${randomUUID()}`;
    const job = { id, state: "running" as const, startedAt: new Date(this.now()).toISOString() };
    this.job = job;
    this.results = new Map(inventory.images.map(image => [image.key, { state: image.reference ? "queued" : "unsupported", findings: [], message: image.message } as ScanResult]));
    this.controllers.set(id, controller);
    this.drain = this.run(inventory, scanner.cacheKey, controller, id);
    return { ...job };
  }

  cancel(id: string): void {
    if (this.job?.id !== id || this.job.state !== "running") throw new ReportRequestError(409, "That scan is no longer running. Refresh the report.");
    this.controllers.get(id)?.abort();
  }
  async settled() { await this.drain; }

  private async run(inventory: Inventory, databaseKey: string, controller: AbortController, id: string) {
    let deadline = false, bytes = 0;
    const timer = setTimeout(() => { deadline = true; controller.abort(); }, this.limits.deadlineMs);
    try {
      for (const image of inventory.images) {
        if (!image.reference) continue;
        if (controller.signal.aborted) {
          this.results.set(image.key, { state: "cancelled", findings: [], message: deadline ? "Job deadline reached; image unscanned." : "Scan cancelled; image unscanned." });
          continue;
        }
        const cacheKey = `${databaseKey}:${image.digest}`;
        const cached = this.cache.get(cacheKey);
        this.results.set(image.key, { state: "scanning", findings: [] });
        let result = cached && cached.expires > this.now() && !resultStale(cached.result, this.now()) ? cached.result : await this.scanner.scan(image.reference, controller.signal);
        if (controller.signal.aborted) result = { state: "cancelled", findings: [], message: deadline ? "Job deadline reached; coverage incomplete." : "Scan cancelled; coverage incomplete." };
        const size = Buffer.byteLength(JSON.stringify(result));
        if (bytes + size > this.limits.resultBytes) {
          result = { state: "error", findings: [], message: "Report size limit reached. Coverage is incomplete." };
          controller.abort();
        } else bytes += size;
        this.results.set(image.key, result);
        if (result.state === "complete" && result !== cached?.result) this.put(cacheKey, result, size);
      }
      if (this.job?.id === id) this.job.state = controller.signal.aborted ? (deadline ? "error" : "cancelled") : "complete";
    } catch {
      for (const [key, value] of this.results) if (["scanning", "queued"].includes(value.state))
        this.results.set(key, { state: "error", findings: [], message: "Scan job failed; coverage incomplete." });
      if (this.job?.id === id) this.job.state = "error";
    } finally {
      clearTimeout(timer); this.controllers.delete(id);
      if (this.job?.id === id) this.job.finishedAt = new Date(this.now()).toISOString();
    }
  }

  private put(key: string, result: ScanResult, bytes: number) {
    if (bytes > this.limits.cacheBytes) return;
    const replaced = this.cache.get(key);
    if (replaced) { this.cache.delete(key); this.cacheBytes -= replaced.bytes; }
    for (const [oldKey, entry] of this.cache) {
      if (entry.expires <= this.now() || this.cacheBytes + bytes > this.limits.cacheBytes || this.cache.size >= 512) {
        this.cache.delete(oldKey); this.cacheBytes -= entry.bytes;
      }
    }
    this.cache.set(key, { result, bytes, expires: this.now() + this.limits.cacheMs }); this.cacheBytes += bytes;
  }
}
