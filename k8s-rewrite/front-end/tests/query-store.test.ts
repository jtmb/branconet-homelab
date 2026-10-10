import assert from "node:assert/strict";
import test from "node:test";
import { QueryFailure, QueryStore } from "../src/lib/query-store";
import { compareValues, quantityNumber } from "../src/lib/table-sort";

function fixture() {
  let time = 1000, next = 0;
  const timers = new Map<number, { run: () => void; at: number }>();
  const requests: { url: string; signal: AbortSignal; resolve: (data: unknown) => void; reject: (error: Error) => void }[] = [];
  const store = new QueryStore({
    load: (url, signal) => new Promise((resolve, reject) => requests.push({ url, signal, resolve, reject })),
    now: () => time,
    schedule: ((run: () => void, delay: number) => { const id = ++next; timers.set(id, { run, at: time + delay }); return id; }) as unknown as typeof setTimeout,
    cancel: ((id: number) => { timers.delete(id); }) as unknown as typeof clearTimeout,
  });
  const tick = (delay: number) => {
    time += delay;
    for (const [id, timer] of [...timers]) if (timer.at <= time) { timers.delete(id); timer.run(); }
  };
  return { store, requests, timers, tick };
}
const flush = async () => { await Promise.resolve(); await Promise.resolve(); };

test("shared subscriptions never overlap polling; hidden/unmounted requests abort and late results cannot replace new state", async () => {
  const { store, requests, timers, tick } = fixture();
  const first = store.subscribe("/pods", () => {});
  const second = store.subscribe("/pods", () => {});
  assert.equal(requests.length, 1);
  tick(60000);
  assert.equal(requests.length, 1);
  assert.equal(timers.size, 0);
  store.setVisible(false);
  assert.equal(requests[0].signal.aborted, true);
  tick(60000);
  assert.equal(requests.length, 1);
  store.setVisible(true);
  assert.equal(requests.length, 2);
  requests[1].resolve({ pods: ["new"] });
  await flush();
  requests[0].resolve({ pods: ["old"] });
  await flush();
  assert.deepEqual(store.snapshot("/pods").data, { pods: ["new"] });
  assert.equal(timers.size, 1);
  tick(9999); assert.equal(requests.length, 2);
  tick(1); assert.equal(requests.length, 3);
  first(); assert.equal(requests[2].signal.aborted, false);
  second(); assert.equal(requests[2].signal.aborted, true);
  assert.equal(timers.size, 0);
  requests[2].resolve({ pods: ["unmounted"] });
  await flush();
  assert.deepEqual(store.snapshot("/pods").data, { pods: ["new"] });
});

test("outage keeps labelled prior data, exponential retries recover, invalidation and sign-out clear pending state", async () => {
  const { store, requests, tick } = fixture();
  const unsubscribe = store.subscribe("/pods", () => {});
  requests[0].resolve({ pods: ["one"] }); await flush();
  tick(10000);
  requests[1].reject(new QueryFailure("Cluster unavailable", 503)); await flush();
  assert.equal(store.snapshot("/pods").status, 503);
  assert.deepEqual(store.snapshot("/pods").data, { pods: ["one"] });
  tick(19999); assert.equal(requests.length, 2);
  tick(1); assert.equal(requests.length, 3);
  requests[2].reject(new QueryFailure("Cluster unavailable", 503)); await flush();
  tick(39999); assert.equal(requests.length, 3);
  store.invalidate();
  assert.equal(requests.length, 4);
  requests[3].resolve({ pods: ["two"] }); await flush();
  assert.equal(store.snapshot("/pods").error, undefined);
  tick(10000); assert.equal(requests.length, 5);
  store.clear();
  assert.equal(requests[4].signal.aborted, true);
  assert.equal(store.snapshot("/pods").data, undefined);
  requests[4].resolve({ pods: ["private old snapshot"] }); await flush();
  assert.equal(store.snapshot("/pods").data, undefined);
  unsubscribe();
});

test("401 discards prior data and metadata query inactivity is bounded", async () => {
  const { store, requests } = fixture();
  const unsubscribe = store.subscribe("/private", () => {});
  requests[0].resolve({ private: "metadata" }); await flush();
  store.invalidate();
  requests[1].reject(new QueryFailure("Unauthorized", 401)); await flush();
  assert.equal(store.snapshot("/private").data, undefined);
  unsubscribe();
  for (let index = 0; index < 40; index++) {
    const stop = store.subscribe("/item/" + index, () => {});
    requests.at(-1)!.resolve({ index }); await flush(); stop();
  }
  assert.equal(store.snapshot("/item/0").data, undefined);
  assert.deepEqual(store.snapshot("/item/39").data, { index: 39 });
});

test("numeric, Kubernetes quantities, count pairs and chronological sorts preserve unknown values last", () => {
  assert.deepEqual([12, 2, 7].sort((a, b) => compareValues(a, b, "number")), [2, 7, 12]);
  assert.deepEqual(["2Gi", "512Mi", "1Gi"].sort((a, b) => compareValues(a, b, "quantity")), ["512Mi", "1Gi", "2Gi"]);
  assert.equal(quantityNumber("250m"), .25);
  assert.equal(quantityNumber("1.5e3"), 1500);
  assert.equal(quantityNumber("broken"), null);
  assert.equal(quantityNumber("1Ei"), 1024 ** 6);
  assert(compareValues("2/12", "12/12", "count") < 0);
  assert(compareValues("2h", "12m", "age") > 0);
  assert(compareValues("2026-01-01", "2025-12-31", "date") > 0);
  assert(compareValues(null, 12, "number", "desc") > 0);
  assert(compareValues("pod-2", "pod-12", "text") < 0);
});

test("default timers retain the browser global receiver", async () => {
  const originalSchedule = globalThis.setTimeout, originalCancel = globalThis.clearTimeout;
  let scheduled = 0, cancelled = 0;
  try {
    globalThis.setTimeout = (function (this: typeof globalThis) {
      assert.equal(this, globalThis);
      scheduled++;
      return {} as ReturnType<typeof setTimeout>;
    }) as typeof setTimeout;
    globalThis.clearTimeout = (function (this: typeof globalThis) {
      assert.equal(this, globalThis);
      cancelled++;
    }) as typeof clearTimeout;
    const store = new QueryStore({ load: async () => ({ metadata: true }) });
    const stop = store.subscribe("/metadata", () => {});
    await flush();
    assert.equal(scheduled, 1);
    stop();
    assert.equal(cancelled, 1);
  } finally {
    globalThis.setTimeout = originalSchedule;
    globalThis.clearTimeout = originalCancel;
  }
});
