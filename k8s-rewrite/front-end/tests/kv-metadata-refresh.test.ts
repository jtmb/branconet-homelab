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
  for (const status of [200, 401, 403, 409, 503]) {
    test(`${label} held ${status === 200 ? "poll" : status + " retry"} exposes one pending status and preserves existing error/retry semantics`, async () => {
      const h = fixture(label);
      const metadata = { items: [{ id: "synthetic-public-row", revision: 7 }], nextCursor: "synthetic-next" };
      try {
        h.requests[0].resolve(metadata); await flush();
        assert.equal(h.render().filter(node => node.props.role === "status").length, 0);
        h.tick(1000); assert.equal(h.requests.length, 2, "Automatic polling remains active");
        if (status !== 200) {
          h.requests[1].reject(new QueryFailure("Synthetic fixed failure", status)); await flush();
          const failed = h.render();
          assert.equal(failed.filter(node => node.props.role === "status").length, 0);
          const retry = failed.find(node => node.type === "button"); assert(retry);
          assert.equal(text(retry), `Retry ${label}`); assert.equal(retry.props.disabled, undefined);
          (retry.props.onClick as () => void)(); assert.equal(h.requests.length, 3);
        }
        const held = h.render();
        const statuses = held.filter(node => node.props.role === "status");
        assert.deepEqual(statuses.map(text), [status === 401 ? `Loading ${label}…` : `Refreshing ${label}…`]);
        assert.equal(h.snapshot().refreshing, true);
        assert.equal(h.snapshot().data, status === 401 ? undefined : metadata, "Retained metadata is not replaced by presentation");
        const alerts = held.filter(node => node.props.role === "alert");
        assert.equal(alerts.length, status === 200 ? 0 : 1);
        if (status !== 200) {
          assert.equal(text(alerts[0]).includes("Synthetic fixed failure"), true);
          assert.equal(text(alerts[0]).includes("Previously loaded metadata is shown."), status !== 401 && status !== 403);
          const retry = held.find(node => node.type === "button"); assert(retry);
          assert.equal(text(retry), `Retry ${label}`); assert.equal(retry.props.disabled, undefined);
          const count = h.requests.length; const replaced = h.requests.at(-1)!; (retry.props.onClick as () => void)();
          assert.equal(h.requests.length, count + 1, "Actual refetch invalidates and replaces the request owner");
          assert.equal(replaced.signal.aborted, true); assert.equal(h.requests.at(-1)!.signal.aborted, false);
          replaced.resolve({ items: [{ id: "obsolete-public-row" }], nextCursor: null }); await flush();
          assert.equal(h.snapshot().refreshing, true, "An obsolete ignored-abort response cannot settle the replacement");
          assert.equal(h.snapshot().data, status === 401 ? undefined : metadata);
        }
        assert(h.requests.every(request => request.url === `/api/kv/${label}`));
        h.requests.at(-1)!.resolve({ items: [], nextCursor: null }); await flush();
        assert.equal(h.render().filter(node => node.props.role === "status" || node.props.role === "alert").length, 0);
        assert.equal(h.snapshot().refreshing, false);
      } finally { h.stop(); assert.equal(h.timers.size, 0); }
    });
  }
}
test("initial loading has exactly one loading status, including its existing retained-error alert", () => {
  for (const error of [undefined, "Synthetic fixed failure"]) {
    const nodes = render({ loading: true, refreshing: true, updatedAt: 0, error, status: error ? 503 : undefined }, "mounts", () => {});
    assert.deepEqual(nodes.filter(node => node.props.role === "status").map(text), ["Loading mounts…"]);
    assert.equal(nodes.filter(node => node.props.role === "alert").length, error ? 1 : 0);
  }
});
test("idle success and idle ordinary errors have no pending announcement", () => {
  for (const error of [undefined, "Synthetic fixed failure"]) {
    const nodes = render({ data: { items: [] }, loading: false, refreshing: false, updatedAt: 1000, error, status: error ? 409 : 200 }, "paths", () => {});
    assert.equal(nodes.filter(node => node.props.role === "status").length, 0);
    assert.equal(nodes.filter(node => node.props.role === "alert").length, error ? 1 : 0);
  }
});