import assert from "node:assert/strict";
import test from "node:test";
import { requestJson } from "../src/lib/use-query";
import { QueryFailure, QueryStore } from "../src/lib/query-store";

function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (error: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
async function flush() { for (let i = 0; i < 12; i++) await Promise.resolve(); }
function response(status: number, json: () => Promise<unknown>): Response {
  return { status, ok: status >= 200 && status < 300, json } as Response;
}
async function environment(run: (events: string[], store: () => QueryStore | undefined) => Promise<void>) {
  const originalFetch = globalThis.fetch, descriptor = Object.getOwnPropertyDescriptor(globalThis, "window");
  const clear = QueryStore.prototype.clear, invalidate = QueryStore.prototype.invalidate;
  const events: string[] = [], target = new EventTarget();
  let captured: QueryStore | undefined;
  target.addEventListener("bortus-session-ended", () => events.push("ended"));
  Object.defineProperty(globalThis, "window", { configurable: true, value: target });
  QueryStore.prototype.clear = function (match) {
    captured = this; events.push("clear"); return clear.call(this, match);
  };
  QueryStore.prototype.invalidate = function (match) {
    captured = this; assert(match); assert(match("/api/auth/session"));
    assert(!match("/api/nodes")); assert(!match("/api/kv/mounts"));
    events.push("invalidate-session"); return invalidate.call(this, match);
  };
  try { await run(events, () => captured); }
  finally {
    QueryStore.prototype.clear = clear; QueryStore.prototype.invalidate = invalidate;
    if (captured) clear.call(captured);
    globalThis.fetch = originalFetch;
    if (descriptor) Object.defineProperty(globalThis, "window", descriptor); else Reflect.deleteProperty(globalThis, "window");
  }
}
const failure = (status: number, message: string, data?: unknown) => (error: unknown) =>
  error instanceof QueryFailure && error.status === status && error.message === message && error.data === data;

for (const status of [401, 403]) for (const body of ["valid", "malformed", "unreadable"] as const) {
  test(`${status} ${body} denial publishes existing effects before held body settlement`, async () => {
    await environment(async events => {
      const pending = deferred<unknown>(), data = { error: "Synthetic denial", metadata: "public" };
      const controller = new AbortController(); let settled = false, calls = 0;
      globalThis.fetch = async (url, init) => {
        calls++; assert.equal(url, "/api/nodes"); assert.equal(init?.method, "PATCH");
        assert.equal(init?.signal, controller.signal); assert.equal(init?.cache, "no-store");
        return response(status, () => { events.push("json"); return pending.promise; });
      };
      const result = requestJson("/api/nodes", { method: "PATCH", signal: controller.signal });
      void result.then(() => { settled = true; }, () => { settled = true; });
      await flush();
      const beforeSettlement = [...events]; assert.equal(settled, false);
      if (body === "valid") pending.resolve(data);
      else pending.reject(body === "malformed" ? new SyntaxError("Synthetic malformed metadata") : new Error("Synthetic unreadable metadata"));
      await assert.rejects(result, failure(status, body === "valid" ? data.error : `Request failed (${status})`, body === "valid" ? data : undefined));
      assert.deepEqual(beforeSettlement, status === 401 ? ["clear", "ended", "json"] : ["invalidate-session", "json"]);
      assert.deepEqual(events, beforeSettlement); assert.equal(calls, 1);
    });
  });
}

for (const status of [409, 503]) for (const body of ["valid", "malformed", "null"] as const) {
  test(`${status} ${body} ordinary failure preserves body/status without session effects`, async () => {
    await environment(async events => {
      const data = body === "valid" ? { error: "Synthetic ordinary failure" } : null;
      globalThis.fetch = async () => response(status, async () => {
        if (body === "malformed") throw new SyntaxError("Synthetic malformed metadata");
        return data;
      });
      await assert.rejects(requestJson("/api/nodes"), failure(status, body === "valid" ? data!.error : `Request failed (${status})`, body === "malformed" ? undefined : data));
      assert.deepEqual(events, []);
    });
  });
}

test("generic JSON/204 and malformed success preserve existing response contracts", async () => {
  await environment(async events => {
    for (const data of [null, true, 17, "synthetic", [], {}]) {
      globalThis.fetch = async () => response(200, async () => data);
      assert.equal(await requestJson("/api/nodes"), data);
    }
    let parsed = false;
    globalThis.fetch = async () => response(204, async () => { parsed = true; throw new Error("must not read204"); });
    assert.equal(await requestJson("/api/nodes"), undefined); assert.equal(parsed, false);
    globalThis.fetch = async () => response(200, async () => { throw new SyntaxError("Synthetic malformed metadata"); });
    await assert.rejects(requestJson("/api/nodes"), failure(502, "Server response could not be verified. Any change may already have been saved. Refresh before trying again."));
    assert.deepEqual(events, []);
  });
});

for (const status of [401, 403]) for (const rejectsOnAbort of [true, false]) test(`${status} held denial fences the actual shared metadata generation (${rejectsOnAbort ? "abort rejection" : "late fulfillment"})`, async () => {
  await environment(async (events, captured) => {
    globalThis.fetch = async () => response(401, async () => ({}));
    await assert.rejects(requestJson("/api/nodes"), error => error instanceof QueryFailure);
    const store = captured(); assert(store); events.length = 0;
    const reads: { url: string; signal: AbortSignal; body: ReturnType<typeof deferred<unknown>> }[] = [];
    const held = deferred<unknown>();
    globalThis.fetch = async (url, init) => {
      if (init?.method === "PATCH") return response(status, () => held.promise);
      const read = { url: String(url), signal: init!.signal as AbortSignal, body: deferred<unknown>() };
      reads.push(read);
      if (rejectsOnAbort) read.signal.addEventListener("abort", () => read.body.reject(new Error("Synthetic metadata abort")), { once: true });
      return response(200, () => read.body.promise);
    };
    const endNodes = store.subscribe("/api/nodes", () => {}), endSession = store.subscribe("/api/auth/session", () => {});
    try {
      await flush(); assert.equal(reads.length, 2);
      reads[0].body.resolve({ name: "synthetic metadata" });
      reads[1].body.resolve({ authenticated: true, role: "write", engineAdmin: false });
      await flush(); assert.equal(store.snapshot("/api/nodes").status, 200);
      assert.equal(store.snapshot("/api/auth/session").status, 200);
      store.refreshActive(); await flush(); assert.equal(reads.length, 4);
      const denied = requestJson("/api/nodes", { method: "PATCH" });
      await flush();
      const beforeSettlement = {
        events: [...events], nodes: store.snapshot("/api/nodes"), session: store.snapshot("/api/auth/session"),
        sessionAborted: reads[3].signal.aborted, nodesAborted: reads[2].signal.aborted,
      };
      held.reject(new Error("Synthetic canceled denial body"));
      await assert.rejects(denied, failure(status, `Request failed (${status})`));
      if (status === 401) {
        assert.deepEqual(beforeSettlement.events, ["clear", "ended"]);
        assert.equal(beforeSettlement.nodes.data, undefined); assert.equal(beforeSettlement.session.data, undefined);
        assert.equal(beforeSettlement.nodesAborted, true);
      } else {
        assert.deepEqual(beforeSettlement.events, ["invalidate-session"]);
        assert.deepEqual(beforeSettlement.nodes.data, { name: "synthetic metadata" });
        assert.equal(beforeSettlement.session.errorStale, true);
        assert.equal(beforeSettlement.nodesAborted, false);
      }
      assert.equal(beforeSettlement.sessionAborted, true);
      reads[2].body.resolve({ name: "late metadata" });
      reads[3].body.resolve({ authenticated: true, role: "write", engineAdmin: true });
      await flush();
      if (status === 401) {
        assert.equal(store.snapshot("/api/nodes").data, undefined);
        assert.equal(store.snapshot("/api/auth/session").data, undefined);
      } else {
        assert.deepEqual(store.snapshot("/api/nodes").data, { name: "late metadata" });
        assert.deepEqual(store.snapshot("/api/auth/session").data, { authenticated: true, role: "write", engineAdmin: false });
        assert.equal(reads.length, 5);
        reads[4].body.resolve({ authenticated: true, role: "write", engineAdmin: false });
        await flush();
        assert.equal(store.snapshot("/api/auth/session").stale, false);
      }
    } finally {
      endNodes(); endSession();
      for (const read of reads) read.body.resolve({ authenticated: false });
      await flush();
    }
  });
});
