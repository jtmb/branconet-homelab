import assert from "node:assert/strict";
import test from "node:test";
import { requestJson } from "../src/lib/use-query";
import { QueryFailure, QueryStore } from "../src/lib/query-store";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(yes => { resolve = yes; });
  return { promise, resolve };
}
const flush = async () => { for (let i = 0; i < 16; i++) await Promise.resolve(); };
const sessionUrl = "/api/auth/session", nodesUrl = "/api/nodes";
const session = { authenticated: true, role: "write", engineAdmin: false };
function response(status: number, body: unknown | Promise<unknown>): Response {
  return { status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) } as Response;
}
interface Read { url: string; signal: AbortSignal; reply: ReturnType<typeof deferred<Response>> }

async function environment(run: (store: QueryStore, events: string[], reads: Read[]) => Promise<void>) {
  const originalFetch = globalThis.fetch, descriptor = Object.getOwnPropertyDescriptor(globalThis, "window");
  const clear = QueryStore.prototype.clear, invalidate = QueryStore.prototype.invalidate;
  const events: string[] = [], target = new EventTarget(), reads: Read[] = [];
  let captured: QueryStore | undefined;
  target.addEventListener("bortus-session-ended", () => events.push("ended"));
  Object.defineProperty(globalThis, "window", { configurable: true, value: target });
  QueryStore.prototype.clear = function (match) { captured = this; events.push("clear"); return clear.call(this, match); };
  QueryStore.prototype.invalidate = function (match) { events.push("invalidate"); return invalidate.call(this, match); };
  globalThis.fetch = async () => response(401, {});
  try {
    await assert.rejects(requestJson(nodesUrl), error => error instanceof QueryFailure && error.status === 401);
    assert(captured); events.length = 0;
    globalThis.fetch = (url, init) => {
      assert.equal(init?.cache, "no-store");
      const read = { url: String(url), signal: init!.signal as AbortSignal, reply: deferred<Response>() };
      reads.push(read);
      return read.reply.promise; // Deliberately ignores abort; this is the late-transport witness.
    };
    await run(captured, events, reads);
  } finally {
    if (captured) { captured.setVisible(true); clear.call(captured); }
    for (const read of reads) read.reply.resolve(response(200, read.url === sessionUrl ? session : { revision: "cleanup" }));
    await flush();
    QueryStore.prototype.clear = clear; QueryStore.prototype.invalidate = invalidate;
    globalThis.fetch = originalFetch;
    if (descriptor) Object.defineProperty(globalThis, "window", descriptor); else Reflect.deleteProperty(globalThis, "window");
  }
}
async function seed(store: QueryStore, reads: Read[]) {
  const stopNodes = store.subscribe(nodesUrl, () => {}), stopSession = store.subscribe(sessionUrl, () => {});
  assert.equal(reads.length, 2);
  reads[0].reply.resolve(response(200, { revision: "initial" })); reads[1].reply.resolve(response(200, session));
  await flush();
  assert.equal(store.snapshot(nodesUrl).status, 200); assert.equal(store.snapshot(sessionUrl).status, 200);
  return () => { stopNodes(); stopSession(); };
}

for (const status of [401, 403]) for (const url of [nodesUrl, sessionUrl]) {
  test(`obsolete ${url} fetch ${status} cannot notify or replace a newer metadata generation`, async () => {
    await environment(async (store, events, reads) => {
      const stop = await seed(store, reads);
      try {
        store.invalidate(key => key === url); const old = reads[2];
        store.invalidate(key => key === url); const replacement = reads[3];
        assert.equal(old.signal.aborted, true); assert.equal(replacement.signal.aborted, false);
        replacement.reply.resolve(response(200, url === sessionUrl ? session : { revision: "replacement" })); await flush();
        const nodes = store.snapshot(nodesUrl), currentSession = store.snapshot(sessionUrl);
        events.length = 0;
        old.reply.resolve(response(status, { error: "Synthetic obsolete denial" })); await flush();
        assert.deepEqual(events, [], "An obsolete metadata denial must not publish session effects");
        assert.equal(store.snapshot(nodesUrl), nodes); assert.equal(store.snapshot(sessionUrl), currentSession);
        assert.equal(replacement.signal.aborted, false); assert.equal(reads.length, 4);
      } finally { stop(); }
    });
  });
}

for (const retire of ["invalidate", "hide", "clear"] as const) {
  test(`obsolete false-session body after ${retire} cannot clear current metadata or end its session`, async () => {
    await environment(async (store, events, reads) => {
      const stop = await seed(store, reads), body = deferred<unknown>();
      try {
        store.invalidate(key => key === sessionUrl); const old = reads[2];
        old.reply.resolve(response(200, body.promise)); await flush();
        if (retire === "invalidate") store.invalidate(key => key === sessionUrl);
        else if (retire === "hide") { store.setVisible(false); store.setVisible(true); }
        else { store.clear(); store.refreshActive(); }
        assert.equal(old.signal.aborted, true);
        for (const read of reads.slice(3)) read.reply.resolve(response(200, read.url === sessionUrl ? session : { revision: "replacement" }));
        await flush();
        const nodes = store.snapshot(nodesUrl), currentSession = store.snapshot(sessionUrl), count = reads.length;
        events.length = 0;
        body.resolve({ authenticated: false }); await flush();
        assert.deepEqual(events, [], "An obsolete session body must not publish session effects");
        assert.equal(store.snapshot(nodesUrl), nodes); assert.equal(store.snapshot(sessionUrl), currentSession);
        assert.equal(reads.length, count);
      } finally { body.resolve({ authenticated: false }); stop(); }
    });
  });
}

for (const status of [401, 403]) {
  test(`current metadata ${status} retains existing notifications before held body settlement`, async () => {
    await environment(async (store, events, reads) => {
      const stop = await seed(store, reads), body = deferred<unknown>();
      try {
        store.invalidate(key => key === nodesUrl); events.length = 0;
        reads[2].reply.resolve(response(status, body.promise)); await flush();
        assert.deepEqual(events, status === 401 ? ["clear", "ended"] : ["invalidate"]);
        if (status === 401) {
          assert.equal(store.snapshot(nodesUrl).data, undefined); assert.equal(store.snapshot(sessionUrl).data, undefined);
        } else {
          assert.deepEqual(store.snapshot(nodesUrl).data, { revision: "initial" });
          assert.equal(reads.length, 4); assert.equal(reads[3].url, sessionUrl);
        }
        body.resolve({ error: "Synthetic current denial" }); await flush();
        if (status === 403) assert.equal(store.snapshot(nodesUrl).status, 403);
      } finally { body.resolve({}); stop(); }
    });
  });

  test(`direct canceled requestJson ${status} keeps its original denial notification contract`, async () => {
    await environment(async (_store, events) => {
      const controller = new AbortController(); controller.abort();
      globalThis.fetch = async (_url, init) => { assert.equal(init?.signal, controller.signal); return response(status, { error: "Synthetic direct denial" }); };
      await assert.rejects(requestJson(nodesUrl, { signal: controller.signal }), error => error instanceof QueryFailure && error.status === status && error.message === "Synthetic direct denial");
      assert.deepEqual(events, status === 401 ? ["clear", "ended"] : ["invalidate"]);
    });
  });

  test(`inner transport timeout does not suppress a current metadata ${status} notification`, async () => {
    await environment(async (store, events, reads) => {
      const stop = await seed(store, reads), originalSchedule = globalThis.setTimeout;
      const timeouts: (() => void)[] = [];
      try {
        globalThis.setTimeout = ((run: () => void, delay: number, ...args: unknown[]) => {
          if (delay === 20000) { timeouts.push(run); return originalSchedule(() => {}, 20000); }
          return originalSchedule(run, delay, ...args);
        }) as typeof setTimeout;
        store.invalidate(key => key === nodesUrl); assert.equal(timeouts.length, 1);
        const current = reads[2]; events.length = 0; timeouts[0](); assert.equal(current.signal.aborted, true);
        current.reply.resolve(response(status, { error: "Synthetic timeout-late denial" })); await flush();
        assert.deepEqual(events, status === 401 ? ["clear", "ended"] : ["invalidate"]);
      } finally { globalThis.setTimeout = originalSchedule; stop(); }
    });
  });
}

test("current false-session metadata clears other metadata and publishes session-ended", async () => {
  await environment(async (store, events, reads) => {
    const stop = await seed(store, reads);
    try {
      store.invalidate(key => key === sessionUrl); events.length = 0;
      reads[2].reply.resolve(response(200, { authenticated: false })); await flush();
      assert.deepEqual(events, ["clear", "ended"]);
      assert.equal(store.snapshot(nodesUrl).data, undefined);
      assert.deepEqual(store.snapshot(sessionUrl).data, { authenticated: false });
    } finally { stop(); }
  });
});

for (const status of [409, 503]) {
  test(`ordinary metadata ${status} retains previous data and existing error settlement`, async () => {
    await environment(async (store, events, reads) => {
      const stop = await seed(store, reads);
      try {
        store.invalidate(key => key === nodesUrl); events.length = 0;
        reads[2].reply.resolve(response(status, { error: "Synthetic ordinary failure" })); await flush();
        assert.deepEqual(events, []);
        const snapshot = store.snapshot(nodesUrl);
        assert.deepEqual(snapshot.data, { revision: "initial" }); assert.equal(snapshot.status, status);
        assert.equal(snapshot.error, "Synthetic ordinary failure"); assert.equal(snapshot.refreshing, false);
        assert.deepEqual(store.snapshot(sessionUrl).data, session);
      } finally { stop(); }
    });
  });
}
