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
function fixture(spec: unknown = { containers: [{ name: "app" }] }) {
  const slots: unknown[] = [], effects = new Map<number, Effect>();
  let index = 0, dirty = false, canWrite = true, tree: unknown;
  let scheduled: (() => void)[] = [];
  const reads: { url: string; signal: AbortSignal; resolve: (value: unknown) => void; reject: (error: Error) => void }[] = [];
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
      requestJson: (url: string, init: { signal: AbortSignal }) => new Promise((resolve, reject) => reads.push({ url, signal: init.signal, resolve, reject })),
    },
    "@/lib/shell-manager": { openShell: () => {} },
    "./confirm-dialog": { __esModule: true, default: "Confirmation" },
  };
  const source = readFileSync(resolve("src/app/(dashboard)/resource-actions-menu.tsx"), "utf8");
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
  const componentModule = { exports: {} as { default: (props: unknown) => unknown } };
  const require = createRequire(resolve("package.json"));
  runInNewContext(output, {
    module: componentModule, exports: componentModule.exports, AbortController, Error, URLSearchParams,
    require: (name: string) => name in modules ? modules[name] : require(name),
    setTimeout: (run: () => void) => { timers.add(run); return run; },
    clearTimeout: (timer: unknown) => timers.delete(timer),
  });
  const render = () => {
    let count = 0;
    do {
      assert(++count < 10, "Component effects did not settle");
      dirty = false; index = 0; scheduled = [];
      tree = componentModule.exports.default({ resourceType: "pod", resource: { metadata: { name: "fixture-pod", namespace: "apps" }, spec } });
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
  const reject = async (read: number) => {
    reads[read].reject(new Error("Pod logs unavailable"));
    for (let i = 0; i < 6; i++) await Promise.resolve();
    render();
  };
  const logModal = () => elements().find(e => e.type === "PrivateModal" && Array.isArray(e.props.containers));
  const chooseContainer = (name: string) => {
    const modal = logModal(); assert(modal);
    (modal.props.onContainerChange as (name: string) => void)(name); render();
  };
  const closeLogs = () => { const modal = logModal(); assert(modal); (modal.props.onClose as () => void)(); render(); };
  render();
  return { reads, select, settle, reject, chooseContainer, closeLogs, logModal, elements, access: (value: boolean) => { canWrite = value; render(); }, timers };
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

test("multiple containers require a choice; switching clears previous content and fences the first reply", async () => {
  const f = fixture({ containers: [{ name: "qbittorrent" }, { name: "gluetun" }], initContainers: [{ name: "setup" }], ephemeralContainers: [{ name: "debug" }] });
  f.select("View Logs"); assert.equal(f.reads.length, 0);
  assert.deepEqual(Array.from(f.logModal()!.props.containers as string[]), ["qbittorrent", "gluetun", "setup", "debug"]);
  f.chooseContainer("unexpected"); assert.equal(f.reads.length, 0);
  f.chooseContainer("gluetun"); assert.equal(new URL(f.reads[0].url, "http://fixture").searchParams.get("container"), "gluetun");
  f.chooseContainer("qbittorrent"); assert.equal(f.reads[0].signal.aborted, true); assert.equal(f.logModal()!.props.logs, undefined);
  await f.settle(1, { logs: "current qbittorrent snapshot" }); await f.settle(0, { logs: "late gluetun snapshot" });
  assert.equal(f.logModal()!.props.logs, "current qbittorrent snapshot");
  f.chooseContainer("gluetun"); assert.equal(f.logModal()!.props.logs, undefined);
  f.closeLogs(); assert.equal(f.reads[2].signal.aborted, true); await f.settle(2, { logs: "closed snapshot" });
  assert.equal(f.logModal(), undefined);
});

test("list action resolves public Pod names once; absent metadata never triggers an unselected log read", async () => {
  const f = fixture(null); f.select("View Logs");
  assert.equal(f.reads.length, 1); assert.equal(f.reads[0].url, "/api/cluster/pods/apps/fixture-pod");
  await f.settle(0, { pod: { spec: { containers: [{ name: "qbittorrent" }, { name: "gluetun" }] } } });
  assert.equal(f.reads.length, 1); f.chooseContainer("gluetun");
  assert.equal(new URL(f.reads[1].url, "http://fixture").searchParams.get("container"), "gluetun");
  await f.reject(1); assert.equal(f.logModal()!.props.logs, undefined); assert.equal(f.logModal()!.props.error, "Pod logs unavailable");
  f.chooseContainer("qbittorrent"); assert.equal(f.logModal()!.props.error, undefined);
  f.access(false); assert.equal(f.reads[2].signal.aborted, true); await f.settle(2, { logs: "withdrawn container snapshot" }); f.access(true);
  assert.equal(f.logModal(), undefined);
  const failed = fixture(null); failed.select("View Logs"); await failed.reject(0); assert.equal(failed.reads.length, 1); assert.equal(failed.logModal(), undefined);
  const empty = fixture({ containers: [] }); empty.select("View Logs"); assert.equal(empty.reads.length, 0);
  assert.deepEqual(Array.from(empty.logModal()!.props.containers as string[]), []);
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

test("log dialog permits explicit same-container refresh and provides a named container choice", () => {
  const require = createRequire(resolve("package.json"));
  const source = readFileSync(resolve("src/app/(dashboard)/log-modal.tsx"), "utf8");
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
  const componentModule = { exports: {} as { default: (props: unknown) => Element } };
  runInNewContext(output, {
    module: componentModule, exports: componentModule.exports,
    require: (name: string) => name === "@/components/ui/modal" ? { Modal: "Dialog" } : require(name),
  });
  const choices: string[] = [];
  const props = { open: true, onClose: () => {}, title: "Public fixture", containers: ["app", "sidecar"], container: "sidecar", loading: false,
    error: "Pod logs unavailable", onContainerChange: (name: string) => choices.push(name) };
  const walk = (node: unknown): Element[] => Array.isArray(node) ? node.flatMap(walk) : node && typeof node === "object" && "props" in node
    ? [node as Element, ...walk((node as Element).props.children)] : [];
  const elements = walk(componentModule.exports.default(props));
  const label = elements.find(e => e.type === "label"); assert(label);
  assert.equal((label.props.children as unknown[])[0], "Container");
  const select = elements.find(e => e.type === "select"); assert(select);
  assert.equal(select.props.value, "sidecar"); assert.equal(select.props.disabled, false);
  const refresh = elements.find(e => e.type === "button" && e.props.children === "Refresh logs"); assert(refresh);
  assert.equal(refresh.props.disabled, false); (refresh.props.onClick as () => void)();
  assert.deepEqual(choices, ["sidecar"], "Retry must request the same selected container");
  assert.equal(elements.filter(e => e.type === "pre").length, 0, "Failure cannot display false empty output");
  const pending = walk(componentModule.exports.default({ ...props, loading: true, error: undefined }));
  assert.equal(pending.find(e => e.type === "button")!.props.disabled, true);
  assert.equal(pending.find(e => e.type === "select")!.props.disabled, false, "Selection must remain available to abort a held container read");
});