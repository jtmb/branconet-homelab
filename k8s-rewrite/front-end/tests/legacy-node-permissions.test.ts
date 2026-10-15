import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { MutationTask } from "../src/lib/mutation-task";
import * as sorting from "../src/lib/legacy-cluster-sort";

// Execute the actual page/useMutation/MutationTask with scoped React and HTTP
// models. This is not DOM, Next session polling or server authorization proof.
type Element = { type: unknown; props: Record<string, unknown> };
type Request = { url: string; method: string; body?: string; signal?: AbortSignal;
  resolve?: (data: unknown) => void; reject?: (error: Error) => void };
function fixture(initialAuthority: boolean, inventoryUnavailable = false) {
  const slots: unknown[] = [], effects = new Map<number, { deps: unknown[]; cleanup?: () => void }>();
  let index = 0, dirty = false, canWrite = initialAuthority, tree: unknown;
  let scheduled: (() => void)[] = [];
  const requests: Request[] = [];
  const inventory = { id: "inventory/id ?", name: "Inventory label", hostname: "fixture-node", ipAddress: "10.0.0.2", role: "worker", status: "pending" };
  const live = ["fixture-node", "live-only"].map(hostname => ({ id: hostname, name: hostname, hostname,
    ipAddress: "10.0.0.2", role: "worker", status: "ready", cpu: 2, memory: 2, pods: 2 }));
  const memo = (create: () => unknown, deps: unknown[]) => { const key = index++, old = slots[key] as { deps: unknown[]; value: unknown } | undefined;
    if (!old || deps.some((value, n) => !Object.is(value, old.deps[n]))) slots[key] = { deps, value: create() };
    return (slots[key] as { value: unknown }).value; };
  const react = {
    useRef: (initial: unknown) => { const key = index++; if (!(key in slots)) slots[key] = { current: initial }; return slots[key]; },
    useState: (initial: unknown) => { const key = index++; if (!(key in slots)) slots[key] = initial;
      return [slots[key], (value: unknown) => { const next = typeof value === "function" ? value(slots[key]) : value; if (!Object.is(next, slots[key])) { slots[key] = next; dirty = true; } }]; },
    useMemo: memo, useCallback: (callback: unknown, deps: unknown[]) => memo(() => callback, deps),
    useEffect: (run: () => (() => void) | void, deps: unknown[]) => { const key = index++, old = effects.get(key);
      if (!old || deps.some((value, n) => !Object.is(value, old.deps[n]))) scheduled.push(() => { old?.cleanup?.(); effects.set(key, { deps, cleanup: run() || undefined }); }); },
  };
  const query = { useSession: () => ({ canWrite }), requestJson: (url: string, init?: RequestInit): Promise<unknown> => {
    const row: Request = { url, method: init?.method ?? "GET", body: init?.body as string | undefined, signal: init?.signal ?? undefined }; requests.push(row);
    if (row.method === "GET") return inventoryUnavailable ? Promise.reject(new Error("Fixed inventory outage")) : Promise.resolve([inventory]);
    return new Promise((resolve, reject) => { row.resolve = resolve; row.reject = reject; });
  } };
  const modules: Record<string, unknown> = { react, "./mutation-task": { MutationTask }, "./use-query": query,
    "@/lib/use-query": query, "next/link": { __esModule: true, default: "Link" },
    "lucide-react": Object.fromEntries(["Server", "Loader2", "Plus", "Trash2", "Save", "Pencil", "Search"].map(name => [name, name])),
    "@/app/(dashboard)/viewport-wrapper": { __esModule: true, default: "Viewport" },
    "@/components/ui/sortable-header": { SortHeader: "SortHeader", useSort: () => ({ sortKey: "hostname", sortDir: "asc", toggle: () => {} }) },
    "@/lib/legacy-cluster-sort": sorting };
  const require = createRequire(resolve("package.json"));
  const load = (path: string) => {
    const output = ts.transpileModule(readFileSync(resolve(path), "utf8"), { fileName: path, compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
    const component = { exports: {} as Record<string, () => unknown> };
    runInNewContext(output, { module: component, exports: component.exports, Error,
      require: (name: string) => name in modules ? modules[name] : require(name),
      fetch: async (url: string) => { requests.push({ url, method: "GET" }); return { ok: true, json: async () => ({ nodes: live }) }; },
      setInterval: () => 1, clearInterval: () => {} });
    return component.exports;
  };
  modules["@/lib/use-mutation"] = load("src/lib/use-mutation.ts");
  const page = load("src/app/cluster/nodes/page.tsx").default;
  const render = () => { let count = 0; do { assert(++count < 12); index = 0; dirty = false; scheduled = []; tree = page(); for (const run of scheduled) run(); } while (dirty); };
  const walk = (value: unknown): Element[] => Array.isArray(value) ? value.flatMap(walk) : value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
  const elements = () => walk(tree), text = (value: unknown): string => typeof value === "string" ? value : Array.isArray(value) ? value.map(text).join("") : value && typeof value === "object" && "props" in value ? text((value as Element).props.children) : "";
  const click = (button: Element) => { (button.props.onClick as () => void)(); render(); };
  const button = (label: string) => { const found = elements().find(e => e.type === "button" && text(e.props.children).trim() === label); assert(found, label); return found; };
  const title = (label: string) => { const found = elements().find(e => e.type === "button" && e.props.title === label); assert(found, label); return found; };
  const input = (placeholder: string) => { const found = elements().find(e => e.type === "input" && e.props.placeholder === placeholder); assert(found, placeholder); return found; };
  const change = (element: Element, value: string) => { (element.props.onChange as (event: unknown) => void)({ target: { value } }); render(); };
  const settle = async () => { for (let n = 0; n < 12; n++) await Promise.resolve(); render(); };
  render();
  return { requests, elements, text, click, button, title, input, change, settle, inventory,
    failInventory: () => { inventoryUnavailable = true; },
    restoreInventory: () => { inventoryUnavailable = false; },
    modalElements: () => walk(elements().find(e => String(e.props.className).startsWith("fixed inset-0"))),
    mutations: () => requests.filter(r => r.method !== "GET"),
    authority: (value: boolean) => { canWrite = value; render(); },
    metadata: () => elements().filter(e => e.type === "Link" && e.props.href !== "/nodes").map(e => ({ href: e.props.href, text: e.props.children })),
    modal: () => elements().some(e => e.type === "h3" && e.props.children === "Edit Node"),
    alerts: () => elements().filter(e => e.props.role === "alert").map(e => text(e.props.children)),
  };
}

test("legacy Nodes unavailable authority hides mutations without losing live metadata", async () => {
  const f = fixture(false); await f.settle();
  assert.deepEqual(f.metadata(), [{ href: "/nodes/fixture-node", text: "fixture-node" }, { href: "/nodes/live-only", text: "live-only" }]);
  assert.equal(f.elements().filter(e => e.type === "button" && (String(e.props.title).includes("inventory ") || f.text(e.props.children).trim() === "Add inventory node")).length, 0);
  assert.equal(f.modal(), false); assert.equal(f.mutations().length, 0);
});

test("legacy Nodes edits exact inventory ID with PUT instead of hostname upsert", async () => {
  const f = fixture(true); await f.settle(); const metadata = f.metadata();
  f.click(f.title("Edit inventory fixture-node")); assert.equal(f.input("Name").props.value, "Inventory label");
  f.change(f.input("Name"), "Renamed label");
  const hostname = f.elements().find(e => e.type === "input" && e.props.value === "fixture-node"); assert(hostname); f.change(hostname, "renamed-host");
  f.click(f.button("Save")); const request = f.mutations()[0];
  assert.equal(request.method, "PUT"); assert.equal(request.url, "/api/nodes/inventory%2Fid%20%3F");
  assert.deepEqual(JSON.parse(request.body!), { name: "Renamed label", hostname: "renamed-host", ipAddress: "10.0.0.2", role: "worker" });
  request.resolve!({ ...f.inventory, hostname: "renamed-host" }); await f.settle();
  assert.equal(f.modal(), false); assert.deepEqual(f.metadata(), metadata); assert.equal(f.mutations().length, 1);
});

test("legacy Nodes deletes inventory only and never assigns shared-IP live-only row an inventory target", async () => {
  const f = fixture(true); await f.settle(); const metadata = f.metadata();
  assert.equal(f.elements().filter(e => String(e.props.title).startsWith("Delete inventory")).length, 1);
  assert.equal(f.elements().filter(e => e.props.title === "Edit inventory live-only").length, 0);
  f.click(f.title("Delete inventory fixture-node")); const request = f.mutations()[0];
  assert.equal(request.method, "DELETE"); assert.equal(request.url, "/api/nodes/inventory%2Fid%20%3F");
  request.resolve!({ success: true }); await f.settle(); assert.deepEqual(f.metadata(), metadata);
  assert.equal(f.requests.some(r => r.url.includes("/api/cluster/remove")), false);
});

test("legacy Nodes failed edit retains draft and actionable error without retry or success refresh", async () => {
  for (const failure of ["Node inventory record not found", "Hostname already registered", "Node inventory update unavailable", "Network request failed"]) {
    const f = fixture(true); await f.settle(); const reads = f.requests.length;
    f.click(f.title("Edit inventory fixture-node")); f.change(f.input("Name"), "held draft"); f.click(f.button("Save"));
    f.mutations()[0].reject!(new Error(failure)); await f.settle();
    assert.equal(f.modal(), true); assert.equal(f.input("Name").props.value, "held draft");
    assert.equal(f.alerts().length, 1); assert(f.alerts()[0].includes(failure)); assert(f.alerts()[0].includes("Refresh inventory"));
    assert.equal(f.modalElements().filter(e => e.props.role === "alert").length, 1, "The single announced error must be visible inside the edit overlay");
    assert.equal(f.requests.length, reads + 1); assert.equal(f.mutations().length, 1);
  }
});

test("legacy Nodes failed add retains draft and successful add alone clears it", async () => {
  const f = fixture(true); await f.settle(); f.click(f.button("Add inventory node"));
  f.change(f.input("Living Room"), "new draft"); f.change(f.input("u4"), "new-host"); f.change(f.input("192.168.0.28"), "10.0.0.3");
  const addSave = () => { const found = f.elements().find(e => e.type === "button" && e.props["aria-label"] === "Save inventory node"); assert(found); return found; };
  f.click(addSave()); assert.equal(f.mutations()[0].method, "POST"); assert.equal(f.mutations()[0].url, "/api/nodes");
  f.mutations()[0].reject!(new Error("Node inventory update unavailable")); await f.settle();
  assert.equal(f.input("Living Room").props.value, "new draft"); assert.equal(f.alerts().length, 1);
  f.click(addSave()); f.mutations()[1].resolve!({ id: "new-inventory" }); await f.settle();
  assert(f.button("Add inventory node")); assert.equal(f.mutations().length, 2);
});

test("legacy Nodes one pending mutation refuses duplicate and retained stale handler calls", async () => {
  const f = fixture(true); await f.settle(); f.click(f.title("Edit inventory fixture-node")); const save = f.button("Save");
  f.click(save); f.click(save); f.click(f.title("Delete inventory fixture-node")); assert.equal(f.mutations().length, 1);
  assert.equal(f.button("Save").props.disabled, true);
  f.mutations()[0].reject!(new Error("Fixed refusal")); await f.settle();
});

test("legacy Nodes authority withdrawal clears add draft and restoration requires explicit entry", async () => {
  const f = fixture(true); await f.settle(); const metadata = f.metadata();
  f.click(f.button("Add inventory node")); f.change(f.input("Living Room"), "new-draft"); f.authority(false);
  assert(!f.elements().some(e => e.props.value === "new-draft")); assert.deepEqual(f.metadata(), metadata);
  f.authority(true); assert(f.button("Add inventory node")); assert(!f.elements().some(e => e.props.placeholder === "Living Room"));
  f.click(f.button("Add inventory node")); assert.equal(f.input("Living Room").props.value, ""); assert.equal(f.mutations().length, 0);
});

test("legacy Nodes withdrawal fences pending edit result and clears draft without removing metadata", async () => {
  for (const outcome of ["success", "error"]) {
    const f = fixture(true); await f.settle(); const metadata = f.metadata();
    f.click(f.title("Edit inventory fixture-node")); f.change(f.input("Name"), "private draft"); f.click(f.button("Save"));
    const request = f.mutations()[0], count = f.requests.length; f.authority(false);
    assert.equal(request.signal!.aborted, true); assert.equal(f.modal(), false);
    f.authority(true);
    if (outcome === "success") request.resolve!({ success: true }); else request.reject!(new Error("Late failure"));
    await f.settle(); assert.equal(f.requests.length, count); assert.equal(f.alerts().length, 0); assert.equal(f.modal(), false);
    assert(!f.elements().some(e => e.props.value === "private draft")); assert.deepEqual(f.metadata(), metadata);
    f.click(f.title("Edit inventory fixture-node")); assert.equal(f.input("Name").props.value, "Inventory label");
  }
});

test("legacy Nodes inventory outage retains readable live rows without guessing mutation IDs", async () => {
  const f = fixture(true, true); await f.settle(); assert.equal(f.metadata().length, 2);
  assert.equal(f.elements().filter(e => String(e.props.title).includes("inventory ")).length, 0);
  assert(f.button("Refresh inventory")); assert.equal(f.mutations().length, 0);
});

test("legacy Nodes delete failure and inventory refresh failure retain last good metadata and explicit retry", async () => {
  const f = fixture(true); await f.settle(); const metadata = f.metadata(), count = f.requests.length;
  f.click(f.title("Delete inventory fixture-node")); f.mutations()[0].reject!(new Error("Node inventory update unavailable")); await f.settle();
  assert.equal(f.alerts().length, 1); assert.equal(f.requests.length, count + 1); assert.deepEqual(f.metadata(), metadata);
  f.failInventory(); f.click(f.button("Refresh inventory")); await f.settle();
  assert.deepEqual(f.metadata(), metadata); assert.equal(f.title("Edit inventory fixture-node").props.disabled, true);
  assert.equal(f.title("Delete inventory fixture-node").props.disabled, true); assert.equal(f.button("Add inventory node").props.disabled, true);
  f.click(f.title("Edit inventory fixture-node")); f.click(f.title("Delete inventory fixture-node")); assert.equal(f.modal(), false); assert.equal(f.mutations().length, 1);
  f.restoreInventory(); f.click(f.button("Refresh inventory")); await f.settle(); assert.equal(f.title("Edit inventory fixture-node").props.disabled, false);
});

test("legacy Nodes inventory read failure during edit keeps draft and visible refresh while refusing Save", async () => {
  const f = fixture(true); await f.settle(); f.click(f.title("Edit inventory fixture-node")); f.change(f.input("Name"), "retained draft");
  // Reach the existing refresh action through a real modeled failed edit first.
  f.click(f.button("Save")); f.mutations()[0].reject!(new Error("Node inventory update unavailable")); await f.settle();
  f.failInventory(); f.click(f.button("Refresh inventory")); await f.settle();
  assert.equal(f.input("Name").props.value, "retained draft"); assert.equal(f.button("Save").props.disabled, true);
  assert.equal(f.modalElements().filter(e => e.props.role === "status").length, 1);
  f.click(f.button("Save")); assert.equal(f.mutations().length, 1);
  f.restoreInventory(); f.click(f.button("Refresh inventory")); await f.settle();
  assert.equal(f.input("Name").props.value, "retained draft"); assert.equal(f.button("Save").props.disabled, false);
});
