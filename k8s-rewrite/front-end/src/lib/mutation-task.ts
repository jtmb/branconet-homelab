export interface MutationState { busy: boolean; error: string }
interface Options {
  request: <T>(url: string, init: RequestInit) => Promise<T>;
  changed: (state: MutationState) => void;
  setTimer?: typeof setTimeout; clearTimer?: typeof clearTimeout;
}
/** One explicit mutation at a time. No automatic retry after an ambiguous outcome. */
export class MutationTask {
  private active = true;
  private current?: { controller: AbortController; timer: ReturnType<typeof setTimeout> };
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;
  constructor(private readonly options: Options) {
    this.setTimer = options.setTimer ?? globalThis.setTimeout.bind(globalThis);
    this.clearTimer = options.clearTimer ?? globalThis.clearTimeout.bind(globalThis);
  }
  activate() { this.active = true; }
  clear() { if (this.active && !this.current) this.options.changed({ busy: false, error: "" }); }
  dispose() {
    this.active = false;
    const task = this.current;
    this.current = undefined;
    if (task) { this.clearTimer(task.timer); task.controller.abort(); }
  }
  async run<T>(url: string, init: RequestInit, success: (data: T) => void) {
    if (!this.active || this.current) return;
    const controller = new AbortController();
    const task = { controller, timer: this.setTimer(() => controller.abort(), 20000) };
    this.current = task;
    this.options.changed({ busy: true, error: "" });
    try {
      const data = await this.options.request<T>(url, { ...init, signal: controller.signal });
      if (!this.active || this.current !== task) return;
      if (controller.signal.aborted) throw new Error("Request timed out. Refresh to check the result before trying again.");
      success(data);
      this.options.changed({ busy: false, error: "" });
    } catch (failure) {
      if (this.active && this.current === task) this.options.changed({ busy: false, error: controller.signal.aborted
        ? "Request timed out. Refresh to check the result before trying again."
        : failure instanceof Error ? failure.message : "Request failed. Refresh to check the result." });
    } finally {
      this.clearTimer(task.timer);
      if (this.current === task) this.current = undefined;
    }
  }
}
