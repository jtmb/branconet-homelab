import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import * as capabilities from "../src/lib/resource-capabilities";

// Execute the actual component with deterministic hook ownership and deferred
// private reads. DOM, Next chunk loading and focus remain actual-browser gates.
type Element = { type: unknown; props: Record<string, unknown> };
type Effect = { deps: unknown[]; cleanup?: () => void };
function fixture() {
  const slots: unknown[] = [], effects = new Map<number, Effect>();
  let index = 0, dirty = false, canWrite = true, tree: unknown;
  let scheduled: (() => void)[] = [];
  const reads: { signal: AbortSignal; resolve: (value: unknown) => void }[] = [];
  const timers = new Set<unknown>();
  const react = {
    useRef: (initial?: unknown) => {
      const key = index++;
      if (!(key in slots)) slots[key] = { current: initial };
      return slots[key];
    },
    useState: (initial: unknown) => {
      const key = index++;
      if (!(key in slots)) slots[key] = initial;
      return [slots[key], (value: unknown) => {
        const next = typeof value === "function" ? value(slots[key]) : value;
        if (!Object.is(next, slots[key])) { slots[key] = next; dirty = true; }
      }];
    },
    useEffect: (run: () => (() => void) | void, deps: unknown[]) => {
      const key = index++, old = effects.get(key);
      if (!old || deps.some((value, i) => !Object.is(value, old.deps[i]))) {
        scheduled.push(() => {
          old?.cleanup?.();
          effects.set(key, { deps, cleanup: run() || undefined });
        });
      }
    },
  };
  const modules: Record<string, unknown> = {
    react,
    "next/dynamic": { __esModule: true, default: () => "PrivateModal" },
    "@radix-ui/react-dropdown-menu": { Root: "Root", Trigger: "Trigger", Portal: "Portal", Content: "Content", Item: "Item" },
    "lucide-react": { MoreHorizontal: "Icon" },
    "@/lib/resource-capabilities": capabilities,
    "@/lib/use-query": {
      useSession: () => ({ canWrite, data: { capabilities: { podExec: false } } }),
      refetchCluster: () => {},
      requestJson: (_url: string, init: { signal: AbortSignal }) => new Promise(resolve => reads.push({ signal: init.signal, resolve })),
    },
    "@/lib/shell-manager": { openShell: () => {} },
    "./confirm-dialog": { __esModule: true, default: "Confirmation" },
  };
  const source = readFileSync(resolve("src/app/(dashboard)/resource-actions-menu.tsx"), "utf8");
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
  const componentModule = { exports: {} as { default: (props: unknown) => unknown } };
  const require = createRequire(resolve("package.json"));
  runInNewContext(output, {
    module: componentModule, exports: componentModule.exports, AbortController,
    require: (name: string) => name in modules ? modules[name] : require(name),
    setTimeout: (run: () => void) => { timers.add(run); return run; },
    clearTimeout: (timer: unknown) => timers.delete(timer),
  });
  const render = () => {
    let count = 0;
    do {
      assert(++count < 10, "Component effects did not settle");
      dirty = false; index = 0; scheduled = [];
      tree = componentModule.exports.default({ resourceType: "pod", resource: { metadata: { name: "fixture-pod", namespace: "apps" } } });
      for (const run of scheduled) run();
    } while (dirty);
  };
  function walk(node: unknown): Element[] {
    if (Array.isArray(node)) return node.flatMap(child => walk(child));
    if (!node || typeof node !== "object" || !("props" in node)) return [];
    const element = node as Element;
    return [element, ...walk(element.props.children)];
  }
  const elements = () => walk(tree);
  const select = (name: string) => {
    const item = elements().find(element => element.type === "Item" && element.props.children === name);
    assert(item, "Advertised action missing");
    (item.props.onSelect as () => void)(); render();
  };
  const settle = async (read: number, value: unknown) => {
    reads[read].resolve(value);
    for (let i = 0; i < 6; i++) await Promise.resolve();
    render();
  };
  render();
  return { reads, select, settle, elements, access: (value: boolean) => { canWrite = value; render(); }, timers };
}

test("fresh permission withdrawal erases held logs; public action trigger stays available and restore requires another read", async () => {
  const f = fixture(); f.select("View Logs"); await f.settle(0, { logs: "synthetic private log" });
  assert.equal(f.elements().filter(e => e.props.logs === "synthetic private log").length, 1);
  f.access(false);
  assert.equal(f.elements().filter(e => e.type === "PrivateModal").length, 0);
  assert.equal(f.elements().filter(e => e.type === "Item").length, 0);
  assert.equal(f.elements().filter(e => e.props["aria-label"] === "Actions for fixture-pod").length, 1);
  f.access(true);
  assert.equal(f.elements().filter(e => e.type === "PrivateModal").length, 0);
  assert.equal(f.reads.length, 1, "Restoration must not automatically reveal private content");
  f.select("View Logs"); await f.settle(1, { logs: "new explicit snapshot" });
  assert.equal(f.elements().filter(e => e.props.logs === "new explicit snapshot").length, 1);
});

test("held private read is aborted on withdrawal and cannot repopulate after session restoration", async () => {
  const f = fixture(); f.select("View Logs"); f.access(false);
  assert.equal(f.reads[0].signal.aborted, true);
  f.access(true); f.select("View Logs");
  await f.settle(1, { logs: "current explicit snapshot" });
  await f.settle(0, { logs: "late withdrawn snapshot" });
  assert.equal(f.elements().filter(e => e.props.logs === "late withdrawn snapshot").length, 0);
  assert.equal(f.elements().filter(e => e.props.logs === "current explicit snapshot").length, 1);
});

test("held YAML viewer/editor and confirmations are erased; stale YAML completion is fenced", async () => {
  for (const action of ["View YAML", "Edit YAML"]) {
    const f = fixture(); f.select(action); await f.settle(0, { yaml: "synthetic YAML snapshot" });
    assert.equal(f.elements().filter(e => e.props.yaml === "synthetic YAML snapshot").length, 1);
    f.access(false); f.access(true);
    assert.equal(f.elements().filter(e => e.type === "PrivateModal").length, 0);
    f.select(action); f.access(false); await f.settle(1, { yaml: "late YAML" }); f.access(true);
    assert.equal(f.reads[1].signal.aborted, true);
    assert.equal(f.elements().filter(e => e.type === "PrivateModal").length, 0);
    f.select("Delete"); assert.equal(f.elements().filter(e => e.type === "Confirmation").length, 1);
    f.access(false); f.access(true);
    assert.equal(f.elements().filter(e => e.type === "Confirmation").length, 0);
  }
});
