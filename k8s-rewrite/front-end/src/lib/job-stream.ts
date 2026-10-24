export interface JobSlice { output: string; nextOffset: number; total: number; status: string }
export const JOB_CHUNK_CHARS = 4096;
export interface JobStreamOptions {
  signal: AbortSignal; cursor: number;
  load: (cursor: number) => Promise<JobSlice | null>;
  authorize: () => Promise<boolean>;
  schedule?: typeof setTimeout; cancel?: typeof clearTimeout;
}

/** One database read at a time, only while a consumer requests the next frame. */
export function createJobStream(options: JobStreamOptions) {
  const schedule = options.schedule ?? setTimeout.bind(globalThis);
  const cancel = options.cancel ?? clearTimeout.bind(globalThis);
  const encoder = new TextEncoder();
  let cursor = options.cursor, closed = false;
  let controller: ReadableStreamDefaultController<Uint8Array>;
  let pollTimer: ReturnType<typeof setTimeout> | undefined;
  let deadline: ReturnType<typeof setTimeout> | undefined;
  let releaseWait: (() => void) | undefined;
  const finish = (close = true) => {
    if (closed) return;
    closed = true;
    if (pollTimer) cancel(pollTimer);
    if (deadline) cancel(deadline);
    pollTimer = deadline = undefined;
    releaseWait?.(); releaseWait = undefined;
    options.signal.removeEventListener("abort", abort);
    if (close) { try { controller.close(); } catch { /* cancelled by consumer */ } }
  };
  const abort = () => finish();
  const send = (body: Record<string, unknown>) => {
    if (closed) return;
    const frame = encoder.encode(`id: ${cursor}\ndata: ${JSON.stringify(body)}\n\n`);
    if (frame.byteLength > 32768) throw new Error("Job frame exceeds bound");
    controller.enqueue(frame);
  };
  return new ReadableStream<Uint8Array>({
    start(value) {
      controller = value;
      if (options.signal.aborted) { finish(); return; }
      options.signal.addEventListener("abort", abort, { once: true });
      controller.enqueue(encoder.encode(": connected\n\n"));
      deadline = schedule(() => { send({ error: "Stream time limit reached; reconnect with the last cursor", cursor, done: true }); finish(); }, 1800000);
    },
    async pull() {
      try {
        while (!closed) {
          const authorized = await options.authorize();
          if (closed) return;
          if (!authorized) { send({ error: "Session ended", cursor, done: true }); finish(); return; }
          const slice = await options.load(cursor);
          if (closed) return;
          if (!slice) { send({ error: "Job no longer exists", cursor, done: true }); finish(); return; }
          if (cursor > slice.total) {
            cursor = 0; send({ reset: true, cursor, status: slice.status }); return;
          }
          const count = Array.from(slice.output).length;
          if (count > JOB_CHUNK_CHARS || slice.nextOffset !== cursor + count || slice.nextOffset > slice.total)
            throw new Error("Invalid job slice");
          const done = slice.status === "success" || slice.status === "failed";
          if (slice.output || done) {
            cursor = slice.nextOffset;
            const ended = done && cursor >= slice.total;
            send({ output: slice.output, status: slice.status, cursor, total: slice.total, done: ended });
            if (ended) finish();
            return;
          }
          await new Promise<void>(resolve => {
            releaseWait = resolve;
            pollTimer = schedule(() => { pollTimer = undefined; releaseWait = undefined; resolve(); }, 500);
          });
        }
      } catch {
        if (!closed) { send({ error: "Job stream unavailable", cursor, done: true }); finish(); }
      }
    },
    cancel() { finish(false); },
  }, { highWaterMark: 0 });
}
