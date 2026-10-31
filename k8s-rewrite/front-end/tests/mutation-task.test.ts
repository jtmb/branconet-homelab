import assert from "node:assert/strict";
import test from "node:test";
import { MutationState, MutationTask } from "../src/lib/mutation-task";
function fixture() {
  const states: MutationState[] = [];
  const requests: { signal: AbortSignal; resolve: (value: unknown) => void; reject: (failure: Error) => void }[] = [];
  const timers = new Map<number, () => void>(); let id = 0;
  const task = new MutationTask({
    request: <T>(_url: string, init: RequestInit) => new Promise<T>((resolve, reject) => requests.push({ signal: init.signal!, resolve: value => resolve(value as T), reject })),
    changed: state => states.push(state),
    setTimer: ((run: () => void) => { timers.set(++id, run); return id; }) as unknown as typeof setTimeout,
    clearTimer: ((timer: number) => { timers.delete(timer); }) as unknown as typeof clearTimeout,
  });
  return { task, requests, states, timers };
}
test("one pending mutation prevents duplicate submission; failure stays actionable and explicit retry succeeds", async () => {
  const { task, requests, states, timers } = fixture();
  const saved: unknown[] = [];
  const first = task.run("/users", { method: "POST" }, data => saved.push(data));
  await task.run("/users", { method: "POST" }, data => saved.push(data));
  assert.equal(requests.length, 1); assert.equal(timers.size, 1);
  requests[0].reject(new Error("Last writer cannot be removed")); await first;
  assert.deepEqual(states.at(-1), { busy: false, error: "Last writer cannot be removed" });
  assert.equal(timers.size, 0); assert.equal(saved.length, 0);
  const retry = task.run("/users", { method: "PATCH" }, data => saved.push(data));
  requests[1].resolve({ success: true }); await retry;
  assert.deepEqual(saved, [{ success: true }]); assert.deepEqual(states.at(-1), { busy: false, error: "" });
  assert.equal(timers.size, 0);
});
test("unmount aborts and drops stale completion even after reactivation; a timed out result is never reported saved", async () => {
  const { task, requests, states, timers } = fixture(); let saved = 0;
  const old = task.run("/config", {}, () => saved++);
  task.dispose(); assert(requests[0].signal.aborted); assert.equal(timers.size, 0);
  task.activate(); const current = task.run("/config", {}, () => saved++);
  const priorStates = states.length;
  requests[0].resolve({ success: true }); await old;
  assert.equal(saved, 0); assert.equal(states.length, priorStates); assert.equal(timers.size, 1);
  [...timers.values()][0](); assert(requests[1].signal.aborted);
  requests[1].resolve({ success: true }); await current;
  assert.equal(saved, 0); assert.match(states.at(-1)!.error, /Refresh to check the result/);
  assert.equal(timers.size, 0); assert.equal(requests.length, 2);
});
test("partial failure reported by a successful HTTP response does not produce a saved state", async () => {
  const { task, requests, states } = fixture();
  const pending = task.run<{ success: boolean }>("/reclaim", {}, result => { if (!result.success) throw new Error("Volume update unavailable"); });
  requests[0].resolve({ success: false }); await pending;
  assert.deepEqual(states.at(-1), { busy: false, error: "Volume update unavailable" });
});
