import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Actual public parent declaration, synthetic metadata/hook slots and inert
// children only. No effects, mounted React, DOM, requests or native execution.
type Element = { type: string; props: Record<string, unknown> };
const dir = "src/app/(dashboard)/secrets/kv/";
function declarations(file: string, names: string[]) {
  const source = ts.createSourceFile(file, readFileSync(dir + file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const selected = source.statements.filter(node => ts.isFunctionDeclaration(node) && names.includes(node.name?.text ?? ""));
  assert.equal(selected.length, names.length);
  return selected.map(node => node.getText(source)).join("\n");
}
const output = ts.transpileModule(declarations("kv-ui.tsx", ["usable", "fresh", "QueryState"]) + "\n" + declarations("kv-browser.tsx", ["KvBrowser"]) + "\nmodule.exports = KvBrowser;", {
  fileName: "metadata-success.tsx", compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
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
const mount = { id: "explicit-mount", name: "synthetic", namespaces: ["exact-space"], revision: 7 };
const messages = ["Mount created.", "Mount metadata updated.", "Path metadata registered. Native values were not changed; initialization/adoption remains separate."];
function model(options: { message?: string; editor?: typeof mount | "new"; registration?: typeof mount; connected?: boolean; canWrite?: boolean; canKvWrite?: boolean; status?: number; absentRefs?: boolean } = {}) {
  const slots: unknown[] = [[], [], "", "draft-search", "draft-mount-search", options.editor, options.registration, undefined, options.message ?? "", false, 0];
  const writes: number[] = [], queries: string[] = [], focuses: string[] = [];
  let index = 0, refIndex = 0, invalidations = 0;
  const refs = Array.from({ length: 5 }, (_, i) => ({ current: options.absentRefs ? null : { isConnected: i === 4 ? options.connected !== false : true, focus: () => focuses.push(i === 4 ? "form-trigger" : i === 2 ? "path-search" : "other") } }));
  const component = { exports: undefined as unknown as () => Element };
  const jsx = (type: string | ((props: Element["props"]) => Element), props: Element["props"]): Element => typeof type === "function" ? type(props) : { type, props };
  runInNewContext(output, {
    module: component, exports: {}, Date, URLSearchParams,
    require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx }; },
    useState: () => { const slot = index++; return [slots[slot], (value: unknown) => { writes.push(slot); slots[slot] = typeof value === "function" ? value(slots[slot]) : value; }]; },
    useRef: () => refs[refIndex++], useCallback: (callback: unknown) => callback,
    useEffect: () => { /* No mounted effects or session lifecycle claim. */ },
    useSession: () => ({ data: { authenticated: true }, updatedAt: Date.now(), loading: false, refreshing: false, canWrite: options.canWrite ?? true, canKvWrite: options.canKvWrite ?? true }),
    useQuery: (url: string) => { queries.push(url); assert(["/api/kv/mounts", "/api/kv/paths"].includes(url)); return { data: { items: url.endsWith("mounts") ? [mount] : [], nextCursor: null }, updatedAt: Date.now(), loading: false, refreshing: false, status: options.status ?? 200, error: options.status ? `Synthetic ${options.status}` : undefined, refetch: () => { throw new Error("Unselected query retry"); } }; },
    refetchKvMetadata: () => { invalidations++; },
    MountForm: "MountForm", RegisterForm: "RegisterForm", PathDetail: "PathDetail", KvAdministration: "KvAdministration",
    Link: "a", MetadataTable: "MetadataTable", CursorControls: "CursorControls", input: "input", button: "button", surface: "surface",
  });
  function render() { index = 0; refIndex = 0; return walk(component.exports()); }
  function node(type: string, label?: string) { const found = render().find(item => item.type === type && (label === undefined || text(item) === label)); assert(found, `${type} ${label ?? ""} missing`); return found; }
  return { render, node, slots, writes, queries, focuses, invalidations: () => invalidations,
    dismiss: () => { const item = node("button", "Dismiss success message"); assert.equal(item.props.type, "button"); (item.props.onClick as () => void)(); } };
}
test("idle metadata parent exposes no success notice or dismiss control", () => {
  const m = model(); assert.equal(m.render().some(item => item.type === "button" && text(item) === "Dismiss success message"), false);
  assert.equal(m.render().some(item => item.type === "p" && messages.includes(text(item))), false); assert.deepEqual(m.writes, []); assert.deepEqual(m.focuses, []);
});
for (const message of messages) {
  test(`${message}: exact existing success text retains a single status`, () => {
    const m = model({ message }); const notices = m.render().filter(item => item.props.role === "status" && text(item) === message);
    assert.equal(notices.length, 1); assert.equal(notices[0].type, "p"); assert.equal(walk(notices[0]).some(item => item.type === "button"), false);
    assert.deepEqual(m.writes, []); assert.deepEqual(m.focuses, []); assert.equal(m.invalidations(), 0);
  });
  for (const connected of [true, false]) test(`${message}: explicit dismissal preserves open metadata intent and returns to ${connected ? "trigger" : "search fallback"}`, () => {
    const m = model({ message, connected, registration: mount }); const captured = m.slots.slice(); m.dismiss();
    assert.equal(m.slots[8], ""); assert.deepEqual(m.writes, [8]);
    for (let i = 0; i < captured.length; i++) if (i !== 8) assert.equal(m.slots[i], captured[i]);
    assert.deepEqual(m.focuses, [connected ? "form-trigger" : "path-search"]); assert.equal(m.invalidations(), 0);
    assert.equal(m.render().some(item => item.type === "button" && text(item) === "Dismiss success message"), false);
    assert.equal(m.queries.every(url => ["/api/kv/mounts", "/api/kv/paths"].includes(url)), true);
  });
}
for (const editor of ["new", mount] as const) test(`${typeof editor === "string" ? "create" : "edit"} saved callback keeps text, close and one invalidation`, () => {
  const m = model({ editor }); const message = typeof editor === "string" ? messages[0] : messages[1];
  (m.node("MountForm").props.saved as (text: string) => void)(message);
  assert.equal(m.slots[8], message); assert.equal(m.slots[5], undefined); assert.equal(m.slots[6], undefined);
  assert.deepEqual(m.focuses, ["form-trigger"]); assert.equal(m.invalidations(), 1); assert.deepEqual(m.writes, [8, 5, 6]);
});
test("registration saved callback preserves exact metadata-only sentence and close/refresh", () => {
  const m = model({ registration: mount }); (m.node("RegisterForm").props.saved as () => void)();
  assert.equal(m.slots[8], messages[2]); assert.equal(m.slots[5], undefined); assert.equal(m.slots[6], undefined);
  assert.deepEqual(m.focuses, ["form-trigger"]); assert.equal(m.invalidations(), 1); assert.deepEqual(m.writes, [8, 5, 6]);
});
for (const form of ["MountForm", "RegisterForm"]) for (const connected of [true, false]) test(`${form} explicit cancel preserves notice and uses ${connected ? "trigger" : "fallback"}`, () => {
  const m = model({ message: messages[0], editor: form === "MountForm" ? mount : undefined, registration: form === "RegisterForm" ? mount : undefined, connected });
  (m.node(form).props.close as () => void)(); assert.equal(m.slots[8], messages[0]); assert.equal(m.slots[5], undefined); assert.equal(m.slots[6], undefined);
  assert.deepEqual(m.focuses, [connected ? "form-trigger" : "path-search"]); assert.equal(m.invalidations(), 0); assert.deepEqual(m.writes, [5, 6]);
});
test("scoped writer keeps registration separate from administrator mount editing", () => {
  const m = model({ editor: mount, registration: mount, canWrite: false, canKvWrite: true });
  assert.equal(m.render().some(item => item.type === "MountForm"), false); assert.equal(m.render().some(item => item.type === "RegisterForm"), true);
});
for (const status of [409, 503]) test(`ordinary ${status} list failure retains prior success and captured form`, () => {
  const m = model({ status, message: messages[1], editor: mount });
  assert.equal(m.node("p", messages[1]).props.role, "status"); assert.equal(m.node("MountForm").props.original, mount);
  assert.equal(m.render().filter(item => item.props.role === "alert").length, 2); assert.deepEqual(m.writes, []); assert.equal(m.invalidations(), 0);
});
test("dismissal tolerates absent focus refs without new requests or clearing forms", () => {
  const m = model({ message: messages[0], editor: mount, absentRefs: true }); m.dismiss();
  assert.deepEqual(m.writes, [8]); assert.equal(m.slots[5], mount); assert.deepEqual(m.focuses, []); assert.equal(m.invalidations(), 0);
});
