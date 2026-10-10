import { test } from "node:test";
import assert from "node:assert/strict";
import { createJobStream, JOB_CHUNK_CHARS, type JobSlice } from "../src/lib/job-stream";
import { appendLogTail, LOG_TAIL_CHARS } from "../src/lib/log-tail";

const flush = () => new Promise<void>(resolve => setImmediate(resolve));
function runtime() {
  let next = 0;
  const pending = new Map<number, { callback: () => void; delay: number }>();
  return {
    pending,
    schedule: ((callback: () => void, delay: number) => { const id = ++next; pending.set(id, { callback, delay }); return id; }) as unknown as typeof setTimeout,
    cancel: ((id: number) => { pending.delete(id); }) as unknown as typeof clearTimeout,
    fire(delay: number) { [...pending].filter(([, value]) => value.delay === delay).forEach(([id, value]) => { pending.delete(id); value.callback(); }); },
  };
}
const decode = (frame: Uint8Array) => JSON.parse(new TextDecoder().decode(frame).match(/data: (.+)\n/)![1]);
async function readFrame(reader: ReadableStreamDefaultReader<Uint8Array>) {
  while (true) {
    const frame = await reader.read();
    if (frame.done || !new TextDecoder().decode(frame.value).startsWith(":")) return frame;
  }
}
const slice = (output: string, cursor: number, status = "success"): JobSlice => ({ output, nextOffset: cursor + Array.from(output).length, total: cursor + Array.from(output).length, status });

test("already-aborted requests do no reads; completion during the first pending read starts no poll timer", async () => {
  const early = new AbortController(), earlyTimers = runtime(); early.abort();
  let reads = 0;
  const earlyReader = createJobStream({ signal: early.signal, cursor: 0, ...earlyTimers, authorize: async () => true,
    load: async () => { reads++; return slice("", 0); } }).getReader();
  assert.equal((await earlyReader.read()).done, true); assert.equal(reads, 0); assert.equal(earlyTimers.pending.size, 0);
  const timers = runtime();
  let resolveSlice!: (value: JobSlice) => void;
  const reader = createJobStream({ signal: new AbortController().signal, cursor: 0, ...timers, authorize: async () => true,
    load: async () => new Promise<JobSlice>(resolve => { resolveSlice = resolve; }) }).getReader();
  const pending = readFrame(reader); await flush(); resolveSlice(slice("completed during read", 0));
  assert.equal(decode((await pending).value!).done, true); assert.equal(timers.pending.size, 0); assert.equal((await reader.read()).done, true);
});

test("completed startup drains bounded Unicode output with backpressure and no polling leak", async () => {
  const timers = runtime(), signal = new AbortController();
  const source = Array.from("🌍".repeat(JOB_CHUNK_CHARS * 3 + 7));
  let reads = 0;
  const reader = createJobStream({ signal: signal.signal, cursor: 0, ...timers, authorize: async () => true,
    load: async cursor => { reads++; const output = source.slice(cursor, cursor + JOB_CHUNK_CHARS).join(""); return { output, nextOffset: cursor + Array.from(output).length, total: source.length, status: "success" }; } }).getReader();
  await flush(); assert.equal(reads, 0);
  let output = "", doneFrames = 0;
  while (true) {
    const frame = await readFrame(reader); if (frame.done) break;
    assert(frame.value.byteLength <= 32768);
    const body = decode(frame.value); output += body.output; if (body.done) doneFrames++;
  }
  assert.equal(output, source.join("")); assert.equal(reads, 4); assert.equal(doneFrames, 1); assert.equal(timers.pending.size, 0);
});
test("slow reads never overlap; poll follows completion and fresh authorization revokes before the next DB read", async () => {
  const timers = runtime(), signal = new AbortController();
  let resolveSlice!: (value: JobSlice) => void, reads = 0, authorized = true;
  const reader = createJobStream({ signal: signal.signal, cursor: 0, ...timers, authorize: async () => authorized,
    load: async () => { reads++; return new Promise<JobSlice>(resolve => { resolveSlice = resolve; }); } }).getReader();
  const first = readFrame(reader); await flush();
  timers.fire(500); await flush(); assert.equal(reads, 1); assert.equal([...timers.pending.values()].filter(v => v.delay === 500).length, 0);
  resolveSlice(slice("", 0, "running")); await flush();
  assert.equal([...timers.pending.values()].filter(v => v.delay === 500).length, 1);
  authorized = false; timers.fire(500);
  const frame = await first; assert.equal(decode(frame.value!).error, "Session ended"); assert.equal(reads, 1);
  assert.equal((await readFrame(reader)).done, true); assert.equal(timers.pending.size, 0);
});
test("reader cancel and request abort clean timers, unsubscribe and discard late DB results", async () => {
  for (const method of ["cancel", "abort"] as const) {
    const timers = runtime(), signal = new AbortController();
    let resolveSlice!: (value: JobSlice) => void;
    const reader = createJobStream({ signal: signal.signal, cursor: 0, ...timers, authorize: async () => true,
      load: async () => new Promise<JobSlice>(resolve => { resolveSlice = resolve; }) }).getReader();
    const pendingRead = readFrame(reader); await flush();
    if (method === "cancel") await reader.cancel(); else signal.abort();
    assert.equal((await pendingRead).done, true); assert.equal(timers.pending.size, 0);
    resolveSlice(slice("late result", 0)); await flush(); assert.equal((await readFrame(reader)).done, true);
  }
});
test("resume/reset, missing/error/deadline close with fixed errors and clear every timer", async () => {
  const timers = runtime(), signal = new AbortController();
  const reader = createJobStream({ signal: signal.signal, cursor: 9, ...timers, authorize: async () => true,
    load: async cursor => ({ output: cursor > 2 ? "" : "ok", nextOffset: cursor > 2 ? cursor : 2, total: 2, status: "success" }) }).getReader();
  assert.equal(decode((await readFrame(reader)).value!).reset, true);
  assert.equal(decode((await readFrame(reader)).value!).output, "ok"); assert.equal((await readFrame(reader)).done, true); assert.equal(timers.pending.size, 0);
  for (const load of [async () => null, async () => { throw new Error("synthetic-secret-exception"); }]) {
    const timers = runtime();
    const reader = createJobStream({ signal: new AbortController().signal, cursor: 0, ...timers, authorize: async () => true, load }).getReader();
    const body = decode((await readFrame(reader)).value!); assert(body.done); assert(!JSON.stringify(body).includes("synthetic-secret-exception"));
    assert.equal((await readFrame(reader)).done, true); assert.equal(timers.pending.size, 0);
  }
  const timeoutRuntime = runtime();
  const timeoutReader = createJobStream({ signal: new AbortController().signal, cursor: 0, ...timeoutRuntime, authorize: async () => true,
    load: async () => slice("", 0, "running") }).getReader();
  const pending = readFrame(timeoutReader); await flush(); timeoutRuntime.fire(1800000);
  assert.equal(decode((await pending).value!).done, true); assert.equal(timeoutRuntime.pending.size, 0);
});
test("log rendering retains a bounded valid-Unicode text tail and strips ANSI without per-event DOM growth", () => {
  const tail = appendLogTail("x".repeat(1000000), "\x1b[31m🌍 final\x1b[0m");
  assert(tail.truncated); assert(tail.output.length <= LOG_TAIL_CHARS); assert(tail.output.endsWith("🌍 final")); assert(!tail.output.includes("\x1b"));
  const boundary = appendLogTail("", "🌍".repeat(LOG_TAIL_CHARS)); assert(!/^[\uDC00-\uDFFF]/.test(boundary.output));
});
