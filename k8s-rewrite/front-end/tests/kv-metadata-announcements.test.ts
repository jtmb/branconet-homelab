import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import type { QuerySnapshot } from "../src/lib/query-store";

// Actual public presentation declarations with inert hooks and metadata only.
// No effect execution, DOM, requests, forms, detail, administration or workbench.
type Element = { type: string; props: Record<string, unknown> };
type Render = (props: Record<string, unknown>) => Element;
const dir = "src/app/(dashboard)/secrets/kv/";
function declarations(file: string, names: string[]) {
  const parsed = ts.createSourceFile(file, readFileSync(dir + file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const selected = parsed.statements.filter(statement => ts.isFunctionDeclaration(statement) && names.includes(statement.name?.text ?? ""));
  assert.equal(selected.length, names.length);
  return selected.map(statement => statement.getText(parsed)).join("\n");
}
const output = ts.transpileModule(
  declarations("kv-ui.tsx", ["usable", "fresh", "QueryState", "CursorControls"]) + "\n" + declarations("kv-browser.tsx", ["KvBrowser"]) + "\nmodule.exports = { KvBrowser, QueryState };",
  { fileName: "public-kv-metadata.tsx", compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } },
).outputText;
function walk(value: unknown): Element[] {
  if (Array.isArray(value)) return value.flatMap(walk);
  return value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
}
function text(value: unknown): string {
  if (Array.isArray(value)) return value.map(text).join("");
  if (value && typeof value === "object" && "props" in value) return text((value as Element).props.children);
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
const ready = (data?: unknown): QuerySnapshot => ({ data, loading: false, refreshing: false, updatedAt: Date.now(), status: 200 });
const mount = { id: "synthetic-mount", name: "Synthetic mount", namespaces: ["synthetic-space"], revision: 7 };
const path = { id: "synthetic-path", mountId: mount.id, path: "synthetic/app", namespace: "synthetic-space", name: "synthetic-native", fields: [{ field: "logical", key: "exact" }], retention: 3, revision: 8 };
function harness(mounts: QuerySnapshot, paths: QuerySnapshot, search = "", mountSearch = "") {
  const component = { exports: {} as Record<string, Render> };
  const queryCalls: string[] = [], retries: string[] = [];
  let slot = 0;
  const forbidden = () => { throw new Error("Outside public metadata presentation boundary"); };
  const jsx = (type: string | Render, props: Element["props"]): Element => typeof type === "function" ? type(props) : { type, props };
  runInNewContext(output, {
    module: component, exports: component.exports, Date, URLSearchParams,
    require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx, Fragment: "fragment" }; },
    useState: (initial: unknown) => { const current = slot++; return [current === 3 ? search : current === 4 ? mountSearch : initial, forbidden]; },
    useRef: () => ({ current: null }), useCallback: (callback: unknown) => callback,
    useEffect: () => { /* Source model: effects are deliberately not executed. */ },
    useSession: () => ({ ...ready({ authenticated: true }), canWrite: false, canKvWrite: false }),
    useQuery: (url: string) => { queryCalls.push(url); assert(["/api/kv/mounts", "/api/kv/paths"].includes(url)); return { ...(url.endsWith("mounts") ? mounts : paths), refetch: () => retries.push(url) }; },
    refetchKvMetadata: forbidden, MountForm: forbidden, RegisterForm: forbidden, PathDetail: forbidden,
    KvWorkbench: forbidden, KvAdministration: forbidden,
    Link: (props: Element["props"]) => ({ type: "a", props }),
    MetadataTable: (props: Element["props"]) => ({ type: "metadata-table", props }),
    input: "input", button: "button", surface: "surface",
  });
  return { component, queryCalls, retries };
}
for (const kind of ["mounts", "paths"]) {
  for (const filtered of [false, true]) {
    test(`${kind} ${filtered ? "filtered" : "empty"} result exposes only its existing permitted-page status`, () => {
      const data = ready({ items: filtered ? [kind === "mounts" ? mount : path] : [], nextCursor: "synthetic-next" });
      const other = ready({ items: [kind === "mounts" ? path : mount], nextCursor: null });
      const h = harness(kind === "mounts" ? data : other, kind === "paths" ? data : other, kind === "paths" && filtered ? "absent" : "", kind === "mounts" && filtered ? "absent" : "");
      const elements = walk(h.component.exports.KvBrowser({}));
      const message = elements.find(element => element.type === "p" && text(element) === `No ${filtered ? "matching " : ""}permitted ${kind} in this API page.`);
      assert(message); assert.equal(message.props.role, "status");
      assert.equal(elements.filter(element => element.props.role === "status").length, 1);
      assert.equal(elements.filter(element => element.props.role === "alert").length, 0);
      const next = elements.find(element => element.type === "button" && text(element) === `Next ${kind} page`);
      assert(next); assert.equal(next.props.disabled, false, "An empty permitted page may still have a next cursor");
      for (const table of elements.filter(element => element.type === "metadata-table")) { assert.equal(table.props.role, undefined); assert.equal(table.props["aria-live"], undefined); }
      assert.deepEqual(h.queryCalls, ["/api/kv/mounts", "/api/kv/paths"]); assert.deepEqual(h.retries, []);
    });
  }
  for (const status of [401, 403, 409, 503]) {
    test(`${kind} ${status} error suppresses empty success and keeps explicit retry`, () => {
      const failure = { ...ready({ items: [], nextCursor: "synthetic-next" }), status, error: "Synthetic fixed failure" };
      const other = ready({ items: [kind === "mounts" ? path : mount], nextCursor: null });
      const h = harness(kind === "mounts" ? failure : other, kind === "paths" ? failure : other);
      const elements = walk(h.component.exports.KvBrowser({}));
      assert.equal(elements.some(element => /^No (matching )?permitted/.test(text(element))), false);
      const alert = elements.find(element => element.props.role === "alert"); assert(alert);
      assert.equal(text(alert).includes("Previously loaded metadata is shown."), status !== 401 && status !== 403);
      const retry = walk(alert).find(element => element.type === "button"); assert(retry);
      assert.equal(text(retry), `Retry ${kind}`); (retry.props.onClick as () => void)();
      assert.deepEqual(h.retries, [`/api/kv/${kind}`]);
      const table = elements.find(element => element.type === "metadata-table" && element.props.label === `KV ${kind}`);
      assert.equal(!!table, status !== 401 && status !== 403);
      const next = elements.find(element => element.type === "button" && text(element) === `Next ${kind} page`);
      if (status === 401 || status === 403) assert.equal(next, undefined);
      else { assert(next); assert.equal(next.props.disabled, true); }
    });
  }
}
test("initial loading has status, no premature empty result and no request from rendering", () => {
  const h = harness({ loading: true, refreshing: true, updatedAt: 0 }, { loading: true, refreshing: true, updatedAt: 0 });
  const elements = walk(h.component.exports.KvBrowser({}));
  assert.deepEqual(elements.filter(element => element.props.role === "status").map(text), ["Loading mounts…", "Loading paths…"]);
  assert.equal(elements.some(element => /^No (matching )?permitted/.test(text(element))), false);
  assert.deepEqual(h.queryCalls, ["/api/kv/mounts", "/api/kv/paths"]); assert.deepEqual(h.retries, []);
});
test("matching current-page metadata remains visible without empty-result announcements", () => {
  const h = harness(ready({ items: [mount], nextCursor: null }), ready({ items: [path], nextCursor: null }), "SYNTHETIC", "SYNTHETIC");
  const elements = walk(h.component.exports.KvBrowser({}));
  assert.equal(elements.filter(element => element.props.role === "status" || element.props.role === "alert").length, 0);
  const tables = elements.filter(element => element.type === "metadata-table"); assert.equal(tables.length, 2);
  assert.deepEqual(Array.from(tables[0].props.rows as { id: string }[], row => row.id), [mount.id]);
  assert.deepEqual(Array.from(tables[1].props.rows as { id: string }[], row => row.id), [path.id]);
});
