import assert from "node:assert/strict";
import test from "node:test";
import { QueryFailure, QueryStore } from "../src/lib/query-store";

function fixture() {
  let now = 1000, next = 0;
  const timers = new Map<number, { run: () => void; at: number }>();
  const requests: { signal: AbortSignal; resolve: (data: unknown) => void; reject: (error: Error) => void }[] = [];
  const store = new QueryStore({
    now: () => now,
    load: (_url, signal) => new Promise((resolve, reject) => requests.push({ signal, resolve, reject })),
    schedule: ((run: () => void, delay: number) => { const id = ++next; timers.set(id, { run, at: now + delay }); return id; }) as unknown as typeof setTimeout,
    cancel: ((id: number) => { timers.delete(id); }) as unknown as typeof clearTimeout,
  });
  const tick = (delay: number) => { now += delay; for (const [id, timer] of [...timers]) if (timer.at <= now) { timers.delete(id); timer.run(); } };
  return { store, timers, requests, tick };
}
const flush = async () => { await Promise.resolve(); await Promise.resolve(); };
const url = "/api/kv/paths/11111111-1111-4111-8111-111111111111/capabilities";

test("coalesced capability subscribers are notified at expiry while one slow refresh remains pending", async () => {
  const { store, timers, requests, tick } = fixture();
  let notifications = 0;
  const parent = store.subscribe(url, () => notifications++), workbench = store.subscribe(url, () => notifications++);
  assert.equal(requests.length, 1);
  requests[0].resolve({ permissions: { update: true } }); await flush();
  assert.equal(timers.size, 1);
  tick(10000); assert.equal(requests.length, 2);
  const beforeExpiry = notifications, snapshot = store.snapshot(url);
  tick(4999); assert.equal(store.snapshot(url).stale, false);
  tick(1); assert.equal(store.snapshot(url).stale, true);
  assert.notEqual(store.snapshot(url), snapshot); assert.equal(notifications, beforeExpiry + 2);
  assert.deepEqual(store.snapshot(url).data, { permissions: { update: true } });
  assert.equal(requests.length, 2); assert.equal(timers.size, 0);
  requests[1].resolve({ permissions: { update: false } }); await flush();
  assert.equal(store.snapshot(url).stale, false); assert.equal(timers.size, 1);
  parent(); workbench(); assert.equal(timers.size, 0);
});

test("manual invalidation preserves the captured expiry deadline and fences a late old capability reply", async () => {
  const { store, timers, requests, tick } = fixture();
  const stop = store.subscribe(url, () => {});
  requests[0].resolve({ revision: 1 }); await flush();
  tick(14999); assert.equal(requests.length, 2);
  store.invalidate(); assert.equal(requests[1].signal.aborted, true); assert.equal(requests.length, 3);
  tick(1); assert.equal(store.snapshot(url).stale, true); assert.equal(requests.length, 3);
  requests[1].resolve({ revision: 999 }); await flush(); assert.deepEqual(store.snapshot(url).data, { revision: 1 });
  requests[2].resolve({ revision: 2 }); await flush(); assert.equal(store.snapshot(url).stale, false);
  stop(); assert.equal(timers.size, 0);
});

test("hidden capability requests and expiry timers stop; returning does not renew old freshness", async () => {
  const { store, timers, requests, tick } = fixture();
  const stop = store.subscribe(url, () => {});
  requests[0].resolve({ revision: 1 }); await flush(); tick(10000);
  store.setVisible(false); assert.equal(requests[1].signal.aborted, true); assert.equal(timers.size, 0);
  tick(60000); assert.equal(requests.length, 2);
  store.setVisible(true); assert.equal(requests.length, 3); assert.equal(store.snapshot(url).stale, true);
  requests[1].resolve({ revision: 999 }); await flush(); assert.equal(store.snapshot(url).stale, true);
  requests[2].resolve({ revision: 2 }); await flush(); assert.equal(store.snapshot(url).stale, false);
  stop(); assert.equal(timers.size, 0);
});

test("expiry notifications keep the existing retry deadline and never start a second in-flight load", async () => {
  const { store, timers, requests, tick } = fixture();
  const stop = store.subscribe(url, () => {});
  requests[0].resolve({ revision: 1 }); await flush(); tick(10000);
  requests[1].reject(new QueryFailure("Unavailable", 503)); await flush();
  tick(5000); assert.equal(store.snapshot(url).stale, true); assert.equal(requests.length, 2); assert.equal(timers.size, 1);
  tick(14999); assert.equal(requests.length, 2); tick(1); assert.equal(requests.length, 3);
  stop(); assert.equal(requests[2].signal.aborted, true); assert.equal(timers.size, 0);
});
