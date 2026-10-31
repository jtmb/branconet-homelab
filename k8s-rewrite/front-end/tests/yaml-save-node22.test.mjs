// DISTINCT NEW3 PUBLIC original scoped YAML hook/VM controls; actual React JSX runtime retained.
import infrastructureAssert from 'node:assert/strict';
import { createHash as infrastructureHash } from 'node:crypto';
import { readFileSync as infrastructureRead } from 'node:fs';
import { createRequire as infrastructureRequire } from 'node:module';
infrastructureAssert.equal(infrastructureRequire(import.meta.url)('typescript').version, '5.9.3');
infrastructureAssert.equal(process.version, 'v22.23.3');
for (const [path, hash] of [
  [
    "tests/yaml-save-lifecycle.test.ts",
    "94e8f570f728292bfcfb57fac2f849f48222ecfeddb34292ceb2748359fbbed0"
  ],
  [
    "src/app/(dashboard)/yaml-modal.tsx",
    "b81ca742189930c5010f67425112b3b7baecf88695cc8fe4be582dc119bb482c"
  ]
] ) infrastructureAssert.equal(infrastructureHash('sha256').update(infrastructureRead(new URL('../' + path, import.meta.url))).digest('hex'), hash, path);
let count = 0;
const control = (...args) => { count++; return test(...args); };
// BEGIN EXACT ORIGINAL TYPE-ERASED PROJECTION
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";
function fixture() {
    const slots = [], effects = new Map();
    let index = 0, tree, closes = 0, defer = false;
    let resolveSave, rejectSave;
    const pending = new Promise((resolve, reject) => { resolveSave = resolve; rejectSave = reject; });
    let props = { open: true, yaml: "public original", title: "Original", readOnly: false, onSave: () => pending, onClose: () => { closes++; } };
    let scheduled = [];
    const react = {
        useRef: (initial) => { const key = index++; if (!(key in slots))
            slots[key] = { current: initial }; return slots[key]; },
        useState: (initial) => { const key = index++; if (!(key in slots))
            slots[key] = initial; return [slots[key], (value) => { slots[key] = typeof value === "function" ? value(slots[key]) : value; }]; },
        useEffect: (run, deps) => {
            const key = index++, old = effects.get(key);
            if (!old || deps.some((value, i) => !Object.is(value, old.deps[i])))
                scheduled.push(() => { old?.cleanup?.(); effects.set(key, { deps, cleanup: run() || undefined }); });
        },
    };
    const source = readFileSync(resolve("src/app/(dashboard)/yaml-modal.tsx"), "utf8");
    const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
    const componentModule = { exports: {} }, require = createRequire(resolve("package.json"));
    runInNewContext(output, { module: componentModule, exports: componentModule.exports, require: (name) => name === "react" ? react : name === "@/components/ui/modal" ? { Modal: "Modal" } : require(name) });
    const render = () => {
        for (let pass = 0; pass < 2; pass++) {
            index = 0;
            scheduled = [];
            tree = componentModule.exports.default(props);
            if (!defer)
                for (const run of scheduled)
                    run();
        }
    };
    const walk = (node) => Array.isArray(node) ? node.flatMap(walk) : node && typeof node === "object" && "props" in node ? [node, ...walk(node.props.children), ...walk(node.props.actions)] : [];
    const elements = () => walk(tree);
    const start = () => {
        elements().find(e => e.type === "button" && e.props.children === "Edit").props.onClick();
        render();
        elements().find(e => e.type === "textarea").props.onChange({ target: { value: "public draft" } });
        render();
        const result = elements().find(e => e.type === "button" && e.props.children === "Save").props.onClick();
        render();
        return result;
    };
    render();
    return { start, elements, closes: () => closes, settle: (outcome) => outcome === "success" ? resolveSave() : rejectSave(new Error("Fixed save refusal")),
        replace: (patch) => { defer = true; props = { ...props, ...patch }; render(); },
        flush: () => { defer = false; render(); }, render, original: { ...props }, };
}
control("YAML save cannot settle onto a changed rendered identity before passive cleanup", async () => {
    for (const patch of [{ yaml: "public replacement" }, { title: "Replacement" }, { readOnly: true }, { open: false }]) {
        for (const outcome of ["success", "error"]) {
            const f = fixture(), save = f.start();
            f.replace(patch);
            f.settle(outcome);
            await save;
            f.render();
            assert.equal(f.closes(), 0, "An old save must not close a newly rendered identity");
            assert.equal(f.elements().filter(e => e.props.role === "alert").length, 0, "An old refusal must not populate replacement error state");
            f.flush();
        }
    }
});
control("close/reopen or title ABA before passive cleanup does not revive an old save", async () => {
    for (const patch of [{ open: false }, { title: "Temporary replacement" }])
        for (const outcome of ["success", "error"]) {
            const f = fixture(), save = f.start();
            f.replace(patch);
            f.replace(f.original);
            f.settle(outcome);
            await save;
            f.render();
            assert.equal(f.closes(), 0);
            assert.equal(f.elements().filter(e => e.props.role === "alert").length, 0);
            f.flush();
        }
});
control("ordinary callback rerender retains a held save when rendered identity is unchanged", async () => {
    for (const outcome of ["success", "error"]) {
        const f = fixture(), save = f.start();
        f.replace({ onSave: async () => { }, onClose: () => { } });
        f.settle(outcome);
        await save;
        f.render();
        assert.equal(f.closes(), outcome === "success" ? 1 : 0);
        assert.equal(f.elements().filter(e => e.props.role === "alert").length, outcome === "error" ? 1 : 0);
    }
});
// END EXACT ORIGINAL TYPE-ERASED PROJECTION
infrastructureAssert.equal(count, 3);
