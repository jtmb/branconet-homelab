import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { QueryFailure, QueryStore, type QuerySnapshot } from "../src/lib/query-store";

// Actual public QueryState declaration and QueryStore; synthetic metadata only.
// No React DOM, hooks, browser, transport, server, form or native handler executes.
type Element = { type: string; props: Record<string, unknown> };
const file = "src/app/(dashboard)/secrets/kv/kv-ui.tsx";
const parsed = ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const selected = parsed.statements.filter(node => ts.isFunctionDeclaration(node) && ["usable", "QueryState"].includes(node.name?.text ?? ""));
assert.equal(selected.length, 2);
const output = ts.transpileModule(selected.map(node => node.getText(parsed)).join("\n") + "\nmodule.exports = { QueryState };", {
  fileName: "public-metadata-refresh.tsx", compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
function walk(value: unknown): Element[] {
  if (Array.isArray(value)) return value.flatMap(walk);
  return value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
}
function text(value: unknown): string {
  if (Array.isArray(value)) return value.map(text).join("");
  if (value && typeof value === "object" && "props" in value) return text((value as Element).props.children);
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
function render(query: QuerySnapshot, label: string, retry: () => void) {
  const component = { exports: {} as { QueryState: (props: { query: QuerySnapshot; label: string; retry: () => void }) => Element } };
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(output, { module: component, exports: component.exports, button: "button", require: (name: string) => {
    assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx, Fragment: "fragment" };
  } });
  return walk(component.exports.QueryState({ query, label, retry }));
}
function fixture(label: string) {
  let time = 1000, id = 0;
  const timers = new Map<number, { run: () => void; at: number }>();
  const requests: { url: string; signal: AbortSignal; resolve: (data: unknown) => void; reject: (error: Error) => void }[] = [];
  const store = new QueryStore({ load: (url, signal) => new Promise((resolve, reject) => requests.push({ url, signal, resolve, reject })), now: () => time,
    schedule: ((run: () => void, delay: number) => { timers.set(++id, { run, at: time + delay }); return id; }) as unknown as typeof setTimeout,
    cancel: ((timer: number) => { timers.delete(timer); }) as unknown as typeof clearTimeout,
  });
  const url = `/api/kv/${label}`;
  const stop = store.subscribe(url, () => {}, 1000);
  const tick = (delay: number) => { time += delay; for (const [key, timer] of [...timers]) if (timer.at <= time) { timers.delete(key); timer.run(); } };
  return { store, requests, timers, stop, tick, snapshot: () => store.snapshot(url), render: () => render(store.snapshot(url), label, () => store.invalidate(key => key === url)) };
}
const flush = async () => { await Promise.resolve(); await Promise.resolve(); };
for (const label of ["mounts", "paths"]) {
  const staleText = `Previously loaded ${label} metadata is stale.`;
  const statuses = (nodes: Element[]) => nodes.filter(node => node.props.role === "status").map(text);
  test(`${label} original success age expires during held poll without discarding metadata`, async () => {
    const h = fixture(label), metadata = { items: [{ id: "public-synthetic-row" }], nextCursor: "public-synthetic-cursor" };
    try {
      h.requests[0].resolve(metadata); await flush();
      h.tick(1000); assert.equal(h.requests.length, 2);
      h.tick(13999); assert.equal(h.snapshot().stale, false);
      assert.deepEqual(statuses(h.render()), [`Refreshing ${label}…`]);
      h.tick(1); assert.equal(h.snapshot().stale, true);
      assert.deepEqual(statuses(h.render()), [`Refreshing ${label}…`, staleText]);
      assert.equal(h.snapshot().data, metadata); assert.equal(h.snapshot().updatedAt, 1000);
      assert.equal(h.requests.length, 2, "Expiry does not replace or add a request");
      h.requests[1].resolve({ items: [], nextCursor: null }); await flush();
      assert.equal(h.snapshot().stale, false); assert.deepEqual(statuses(h.render()), []);
    } finally { h.stop(); assert.equal(h.timers.size, 0); }
  });
  for (const status of [409, 503]) test(`${label} retained ${status} failure shows expiry without changing alert or Retry ownership`, async () => {
    const h = fixture(label), metadata = { items: [{ id: "public-synthetic-row" }], nextCursor: "public-synthetic-cursor" };
    try {
      h.requests[0].resolve(metadata); await flush(); h.tick(1000);
      h.requests[1].reject(new QueryFailure("Synthetic fixed failure", status)); await flush();
      assert.equal(h.snapshot().stale, false); assert.deepEqual(statuses(h.render()), []);
      h.tick(14000); assert.equal(h.snapshot().stale, true);
      assert.deepEqual(statuses(h.render()), [`Refreshing ${label}…`, staleText]);
      const nodes = h.render(), alert = nodes.find(node => node.props.role === "alert"); assert(alert);
      assert.equal(text(alert), `${label} unavailable: Synthetic fixed failure Previously loaded metadata is shown. Retry ${label}`);
      const retry = nodes.find(node => node.type === "button"); assert(retry);
      assert.equal(text(retry), `Retry ${label}`); assert.equal(retry.props.disabled, undefined);
      const old = h.requests.at(-1)!, before = h.requests.length;
      (retry.props.onClick as () => void)(); assert.equal(h.requests.length, before + 1); assert.equal(old.signal.aborted, true);
      assert.equal(h.snapshot().data, metadata); assert.equal(h.snapshot().updatedAt, 1000);
      old.resolve({ items: [{ id: "obsolete-public-row" }], nextCursor: null }); await flush();
      assert.equal(h.snapshot().data, metadata); assert.equal(h.snapshot().stale, true); assert.equal(h.snapshot().refreshing, true);
      h.requests.at(-1)!.resolve({ items: [], nextCursor: null }); await flush();
      assert.deepEqual(statuses(h.render()), []); assert.equal(h.snapshot().error, undefined); assert.equal(h.snapshot().stale, false);
    } finally { h.stop(); assert.equal(h.timers.size, 0); }
  });
  for (const status of [401, 403]) test(`${label} denial suppresses stale retained metadata presentation`, async () => {
    const h = fixture(label), metadata = { items: [{ id: "public-synthetic-row" }], nextCursor: null };
    try {
      h.requests[0].resolve(metadata); await flush(); h.tick(15000);
      assert.equal(h.snapshot().stale, true);
      h.requests[1].reject(new QueryFailure("Synthetic fixed failure", status)); await flush();
      assert.equal(h.snapshot().data, status === 401 ? undefined : metadata);
      const nodes = h.render(); assert.deepEqual(statuses(nodes), []);
      const alert = nodes.find(node => node.props.role === "alert"); assert(alert);
      assert.equal(text(alert).includes("Previously loaded"), false);
      const retry = nodes.find(node => node.type === "button"); assert(retry); assert.equal(text(retry), `Retry ${label}`);
    } finally { h.stop(); assert.equal(h.timers.size, 0); }
  });
  test(`${label} idle stale and empty permitted pages have one stale status and no invented retry`, () => {
    for (const data of [{ items: [{ id: "public-row" }], nextCursor: "public-cursor" }, { items: [], nextCursor: null }]) {
      const query = { data, loading: false, refreshing: false, updatedAt: 1000, stale: true, status: 200 };
      const nodes = render(query, label, () => {});
      assert.deepEqual(statuses(nodes), [staleText]);
      assert.equal(nodes.filter(node => node.type === "button" || node.props.role === "alert").length, 0);
      assert.equal(query.data, data);
    }
  });
  test(`${label} absent and initial snapshots never claim previously loaded stale metadata`, () => {
    for (const loading of [false, true]) {
      const nodes = render({ loading, refreshing: false, stale: true, updatedAt: 0 }, label, () => {});
      assert.deepEqual(statuses(nodes), loading ? [`Loading ${label}…`] : []);
      assert.equal(nodes.some(node => text(node).includes("Previously loaded")), false);
    }
  });
}