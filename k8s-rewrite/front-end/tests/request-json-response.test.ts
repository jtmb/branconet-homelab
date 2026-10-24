import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "node:http";
import { requestJson } from "../src/lib/use-query";
import { configurationList, configurationRemoved, configurationSaved } from "../src/lib/configuration-response";
import { MutationState, MutationTask } from "../src/lib/mutation-task";
import { QueryFailure, QueryStore } from "../src/lib/query-store";

const marker = "synthetic-response-body-not-for-errors";
const row = { id: "configuration-fixture", key: "fixture_key", value: "", category: " fixture category " };
type Reply = { status?: number; body: string; drop?: boolean };

async function fixture(run: (base: string, calls: string[], replies: Map<string, Reply>) => Promise<void>) {
  const calls: string[] = [], replies = new Map<string, Reply>();
  const server = createServer((request, response) => {
    const url = request.url!; calls.push(url);
    const reply = replies.get(url);
    if (!reply) { response.writeHead(404); response.end(); return; }
    request.resume();
    if (reply.drop) { request.socket.destroy(); return; }
    response.writeHead(reply.status ?? 200, { "Content-Type": "application/json", "Connection": "close" });
    response.end(reply.body);
  });
  await new Promise<void>((resolve, reject) => { server.once("error", reject); server.listen(0, "127.0.0.1", resolve); });
  const address = server.address(); assert(address && typeof address !== "string");
  try { await run(`http://127.0.0.1:${address.port}`, calls, replies); }
  finally { await new Promise<void>((resolve, reject) => { server.close(error => error ? reject(error) : resolve()); server.closeAllConnections(); }); }
}
async function until(condition: () => boolean) {
  const end = Date.now() + 3000;
  while (!condition()) { assert(Date.now() < end, "Synthetic HTTP observation deadline exceeded"); await new Promise(resolve => setTimeout(resolve, 5)); }
}
const invalid = (error: unknown) => error instanceof QueryFailure && error.status === 502 && !error.message.includes(marker) && error.data === undefined;

test("real HTTP malformed success is rejected; generic valid JSON and empty204 remain compatible", { timeout: 10000 }, async () => {
  await fixture(async (base, _calls, replies) => {
    for (const [name, body] of [["malformed", '{"private":"' + marker], ["empty", ""]]) {
      replies.set("/" + name, { body });
      await assert.rejects(requestJson(base + "/" + name), invalid);
    }
    for (const value of [null, true, 17, "synthetic", [], {}]) {
      replies.set("/valid", { body: JSON.stringify(value) });
      assert.deepEqual(await requestJson(base + "/valid"), value);
    }
    replies.set("/empty204", { status: 204, body: "" });
    assert.equal(await requestJson(base + "/empty204"), undefined);
    assert.throws(() => configurationList(undefined), invalid);
    assert.throws(() => configurationSaved(undefined, row), invalid);
  });
});

test("real HTTP malformed/null/primitive errors preserve401 clearing and403 session invalidation", { timeout: 10000 }, async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "window"), target = new EventTarget();
  const originalClear = QueryStore.prototype.clear, originalInvalidate = QueryStore.prototype.invalidate;
  let cleared = 0, invalidated = 0, ended = 0;
  target.addEventListener("bortus-session-ended", () => ended++);
  Object.defineProperty(globalThis, "window", { configurable: true, value: target });
  QueryStore.prototype.clear = function (match) { cleared++; return originalClear.call(this, match); };
  QueryStore.prototype.invalidate = function (match) {
    assert(match);
    assert(match("/api/auth/session")); assert(!match("/api/vars")); invalidated++;
    return originalInvalidate.call(this, match);
  };
  try {
    await fixture(async (base, _calls, replies) => {
      for (const status of [401, 403]) for (const body of ['{"private":"' + marker, "null", '"' + marker + '"']) {
        replies.set("/error", { status, body });
        await assert.rejects(requestJson(base + "/error"), (error: unknown) => error instanceof QueryFailure
          && error.status === status && error.message === `Request failed (${status})`);
      }
      assert.equal(cleared, 3); assert.equal(ended, 3); assert.equal(invalidated, 3);
    });
  } finally {
    QueryStore.prototype.clear = originalClear; QueryStore.prototype.invalidate = originalInvalidate;
    if (descriptor) Object.defineProperty(globalThis, "window", descriptor); else Reflect.deleteProperty(globalThis, "window");
  }
});

test("real HTTP configuration DELETE needs a true acknowledgment before closing confirmation", { timeout: 10000 }, async () => {
  await fixture(async (base, calls, replies) => {
    for (const [index, reply] of [
      { body: '{"private":"' + marker }, { body: "{}" }, { body: "null" },
      { body: "true" }, { body: JSON.stringify({ success: false }) }, { status: 204, body: "" },
    ].entries()) {
      const url = "/delete-" + index; replies.set(url, reply);
      let confirmationOpen = true, removed = false, state: MutationState = { busy: false, error: "" };
      const task = new MutationTask({ request: requestJson, changed: value => { state = value; } });
      const complete = (value: unknown) => { configurationRemoved(value); confirmationOpen = false; removed = true; };
      await task.run(base + url, { method: "DELETE" }, complete);
      assert.equal(calls.filter(call => call === url).length, 1);
      assert.equal(confirmationOpen, true); assert.equal(removed, false); assert(state.error); assert(!state.error.includes(marker));
      assert.match(state.error, /may already have been (saved|removed).*Refresh before trying again/);
      replies.set(url, { body: JSON.stringify({ success: true, extraMetadata: "allowed" }) });
      await task.run(base + url, { method: "DELETE" }, complete);
      assert.equal(confirmationOpen, false); assert.equal(removed, true);
      assert.equal(calls.filter(call => call === url).length, 2); task.dispose();
    }
  });
});

test("real HTTP wrong-shape configuration reads retain prior metadata and expose a fixed error", { timeout: 10000 }, async () => {
  await fixture(async (base, _calls, replies) => {
    const store = new QueryStore({ load: async url => configurationList(await requestJson(base + url)) });
    replies.set("/list", { body: JSON.stringify([row]) });
    const stop = store.subscribe("/list", () => {});
    try {
      await until(() => !!store.snapshot("/list").data);
      const retained = store.snapshot("/list").data;
      for (const value of [{}, null, { variables: [row] }, [null], [{ ...row, value: 1 }], [{ ...row, id: "" }]]) {
        replies.set("/list", { body: JSON.stringify(value) }); store.invalidate();
        await until(() => !store.snapshot("/list").refreshing);
        const snapshot = store.snapshot("/list");
        assert.equal(snapshot.data, retained); assert.equal(snapshot.status, 502);
        assert.equal(snapshot.error, "Invalid configuration response. Refresh before trying again.");
      }
      replies.set("/list", { body: "[]" }); store.invalidate();
      await until(() => !store.snapshot("/list").refreshing);
      assert.deepEqual(store.snapshot("/list").data, []); assert.equal(store.snapshot("/list").error, undefined);
    } finally { stop(); }
  });
});

test("real HTTP unverified configuration writes cannot complete the draft callback or replay; explicit valid retry succeeds", { timeout: 10000 }, async () => {
  await fixture(async (base, calls, replies) => {
    const refused: Reply[] = [
      { body: '{"private":"' + marker }, { body: "{}" }, { body: "null" },
      { body: JSON.stringify({ success: false, variable: row }) }, { body: JSON.stringify({ success: true }) },
      { body: JSON.stringify({ success: true, variable: { ...row, id: "different-id" } }) },
      { body: JSON.stringify({ success: true, variable: { ...row, key: "different_key" } }) },
      { body: JSON.stringify({ success: true, variable: { ...row, value: marker } }) },
      { body: JSON.stringify({ success: true, variable: { ...row, category: row.category.trim() } }) },
      { status: 204, body: "" }, { body: "", drop: true },
    ];
    for (const [index, reply] of refused.entries()) {
      const url = "/save-" + index; replies.set(url, reply);
      let draft = { ...row }, saved = false, state: MutationState = { busy: false, error: "" };
      const task = new MutationTask({ request: requestJson, changed: value => { state = value; } });
      const complete = (value: unknown) => { configurationSaved(value, row); draft = { ...row, value: "cleared" }; saved = true; };
      const pending = task.run(base + url, { method: "POST" }, complete);
      await task.run(base + url, { method: "POST" }, complete);
      await pending;
      assert.equal(calls.filter(call => call === url).length, 1);
      assert.equal(saved, false); assert.deepEqual(draft, row); assert.equal(state.busy, false);
      assert(state.error); assert(!state.error.includes(marker));
      if (!reply.drop) assert.match(state.error, /may already have been saved.*Refresh before trying again/);
      replies.set(url, { status: 201, body: JSON.stringify({ success: true, variable: row }) });
      await task.run(base + url, { method: "POST" }, complete);
      assert.equal(saved, true); assert.equal(calls.filter(call => call === url).length, 2);
      assert.deepEqual(state, { busy: false, error: "" }); task.dispose();
    }
    replies.set("/create", { status: 201, body: JSON.stringify({ success: true, variable: row }) });
    const { key, value, category } = row;
    configurationSaved(await requestJson(base + "/create", { method: "POST" }), { key, value, category });
  });
});
