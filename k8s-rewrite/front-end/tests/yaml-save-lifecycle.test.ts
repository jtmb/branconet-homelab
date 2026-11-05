import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";

type Element = { type: unknown; props: Record<string, unknown> };
type Props = { open: boolean; yaml: string; title: string; readOnly: boolean; onSave: (value: string) => Promise<void>; onClose: () => void };
function fixture() {
  const slots: unknown[] = [], effects = new Map<number, { deps: unknown[]; cleanup?: () => void }>();
  let index = 0, tree: unknown, closes = 0, defer = false;
  let resolveSave!: () => void, rejectSave!: (error: Error) => void;
  const pending = new Promise<void>((resolve, reject) => { resolveSave = resolve; rejectSave = reject; });
  let props: Props = { open: true, yaml: "public original", title: "Original", readOnly: false, onSave: () => pending, onClose: () => { closes++; } };
  let scheduled: (() => void)[] = [];
  const react = {
    useRef: (initial: unknown) => { const key = index++; if (!(key in slots)) slots[key] = { current: initial }; return slots[key]; },
    useState: (initial: unknown) => { const key = index++; if (!(key in slots)) slots[key] = initial; return [slots[key], (value: unknown) => { slots[key] = typeof value === "function" ? value(slots[key]) : value; }]; },
    useEffect: (run: () => (() => void) | void, deps: unknown[]) => {
      const key = index++, old = effects.get(key);
      if (!old || deps.some((value, i) => !Object.is(value, old.deps[i]))) scheduled.push(() => { old?.cleanup?.(); effects.set(key, { deps, cleanup: run() || undefined }); });
    },
  };
  const source = readFileSync(resolve("src/app/(dashboard)/yaml-modal.tsx"), "utf8");
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
  const componentModule = { exports: {} as { default: (props: unknown) => unknown } }, require = createRequire(resolve("package.json"));
  runInNewContext(output, { module: componentModule, exports: componentModule.exports, require: (name: string) => name === "react" ? react : name === "@/components/ui/modal" ? { Modal: "Modal" } : require(name) });
  const render = () => {
    for (let pass = 0; pass < 2; pass++) { index = 0; scheduled = []; tree = componentModule.exports.default(props); if (!defer) for (const run of scheduled) run(); }
  };
  const walk = (node: unknown): Element[] => Array.isArray(node) ? node.flatMap(walk) : node && typeof node === "object" && "props" in node ? [node as Element, ...walk((node as Element).props.children), ...walk((node as Element).props.actions)] : [];
  const elements = () => walk(tree);
  const start = () => {
    (elements().find(e => e.type === "button" && e.props.children === "Edit")!.props.onClick as () => void)(); render();
    (elements().find(e => e.type === "textarea")!.props.onChange as (event: unknown) => void)({ target: { value: "public draft" } }); render();
    const result = (elements().find(e => e.type === "button" && e.props.children === "Save")!.props.onClick as () => Promise<void>)(); render(); return result;
  };
  render();
  return { start, elements, closes: () => closes, settle: (outcome: string) => outcome === "success" ? resolveSave() : rejectSave(new Error("Fixed save refusal")),
    replace: (patch: Partial<Props>) => { defer = true; props = { ...props, ...patch }; render(); },
    flush: () => { defer = false; render(); }, render, original: { ...props },
  };
}

test("YAML save cannot settle onto a changed rendered identity before passive cleanup", async () => {
  for (const patch of [{ yaml: "public replacement" }, { title: "Replacement" }, { readOnly: true }, { open: false }]) {
    for (const outcome of ["success", "error"]) {
      const f = fixture(), save = f.start(); f.replace(patch); f.settle(outcome); await save; f.render();
      assert.equal(f.closes(), 0, "An old save must not close a newly rendered identity");
      assert.equal(f.elements().filter(e => e.props.role === "alert").length, 0, "An old refusal must not populate replacement error state");
      f.flush();
    }
  }
});

test("close/reopen or title ABA before passive cleanup does not revive an old save", async () => {
  for (const patch of [{ open: false }, { title: "Temporary replacement" }]) for (const outcome of ["success", "error"]) {
    const f = fixture(), save = f.start(); f.replace(patch); f.replace(f.original); f.settle(outcome); await save; f.render();
    assert.equal(f.closes(), 0); assert.equal(f.elements().filter(e => e.props.role === "alert").length, 0); f.flush();
  }
});

test("ordinary callback rerender retains a held save when rendered identity is unchanged", async () => {
  for (const outcome of ["success", "error"]) {
    const f = fixture(), save = f.start(); f.replace({ onSave: async () => {}, onClose: () => {} }); f.settle(outcome); await save; f.render();
    assert.equal(f.closes(), outcome === "success" ? 1 : 0);
    assert.equal(f.elements().filter(e => e.props.role === "alert").length, outcome === "error" ? 1 : 0);
  }
});
