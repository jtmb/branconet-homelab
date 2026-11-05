// DISTINCT NEW11 PUBLIC selected-copy controls; historical callbacks remain frozen.
import infrastructureAssert from 'node:assert/strict';
import { readFileSync as nativeReadFileSync } from 'node:fs';
import { createRequire as nativeCreateRequire } from 'node:module';
import { createHash } from 'node:crypto';
import * as infrastructurePath from 'node:path';
import * as infrastructureVm from 'node:vm';
const compilerRequire = nativeCreateRequire(import.meta.url), ts = compilerRequire('typescript');
infrastructureAssert.equal(ts.version, '5.9.3');
const digest = value => createHash('sha256').update(value).digest('hex');
const sourcePins = {"src/lib/resource-capabilities.ts": "48bcb1e2cfa2619facdd494d9123df6368099e6d602ec5b85016dc82c88feda7", "src/app/(dashboard)/resource-actions-menu.tsx": "8632c27a2485727412ddd437edbcaed128ddf830f7bda5c2ce9048406d8d0f6f", "src/components/cluster/deployment-controls.tsx": "01521c20865675386eceb6f749623b41b04e465902f4ee4b2e0b6021034d6513", "src/app/(dashboard)/yaml-modal.tsx": "b81ca742189930c5010f67425112b3b7baecf88695cc8fe4be582dc119bb482c", "src/app/(dashboard)/log-modal.tsx": "8436b74176019a5bbdc6b047905709e43f25728dca3b130e24265b7604908e86"};
const sources = new Map(Object.entries(sourcePins).map(([path, hash]) => {
  const source = nativeReadFileSync(new URL('../' + path, import.meta.url), 'utf8').replaceAll('\r\n', '\n');
  infrastructureAssert.equal(digest(source), hash, path);
  return [path, ts.createSourceFile(path, source, ts.ScriptTarget.ES2022, true, path.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)];
}));
const select = (path, name) => {
  const tree = sources.get(path);
  const found = tree.statements.filter(n => ts.isFunctionDeclaration(n) ? n.name?.text === name : ts.isVariableStatement(n) && n.declarationList.declarations.some(d => ts.isIdentifier(d.name) && d.name.text === name));
  infrastructureAssert.equal(found.length, 1, name);
  return found[0].getText(tree);
};
const registry = ['RESOURCE_CAPABILITIES', 'resourceBase'].map(name => select('src/lib/resource-capabilities.ts', name).replace(/^export\s+/, '')).join('\n');
const loweredRegistry = ts.transpileModule(registry, { reportDiagnostics: true, compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
infrastructureAssert.equal(loweredRegistry.diagnostics.length, 0);
const capabilities = infrastructureVm.runInThisContext(`(function() { "use strict";\n${loweredRegistry.outputText}\nreturn { RESOURCE_CAPABILITIES, resourceBase }; })`, { timeout: 1000 })();
// All selected imports bind only the original fixture's synthetic module map.
// The two dynamic modal bindings are exactly the original dynamic facade's token.
const packages = new Map();
const selections = [
  ['src/app/(dashboard)/resource-actions-menu.tsx', 'ResourceActionsMenu'],
  ['src/components/cluster/deployment-controls.tsx', 'DeploymentControls'],
  ['src/app/(dashboard)/yaml-modal.tsx', 'YamlModal'],
  ['src/app/(dashboard)/log-modal.tsx', 'LogModal'],
];
for (const [path, name] of selections) {
  const tree = sources.get(path);
  const imports = tree.statements.filter(n => ts.isImportDeclaration(n) && n.moduleSpecifier.text !== 'next/dynamic').map(n => n.getText(tree));
  const modals = name === 'ResourceActionsMenu' ? 'const YamlModal = "PrivateModal"; const LogModal = "PrivateModal";\n' : '';
  packages.set(infrastructurePath.resolve(path), imports.join('\n') + '\n' + modals + select(path, name));
}
const reactRoot = infrastructurePath.dirname(compilerRequire.resolve('react/package.json'));
const reactPins = {"package.json": "d4e68a5c96babb20cad1daafea8b78822eae45b341552cf5418d06a5304fa64c", "jsx-runtime.js": "28170e60f2ff0bc045bc7d175f5849e86f68dd02d76d7255369420718b30295a", "index.js": "a216c390bf956cbb906c66d29fdb2e2ad6999464a5ca83e476533a6f25ad0ef3", "cjs/react-jsx-runtime.development.js": "581f93fa33c32b3aa7ea35b85b80258922517de046f5447236047dcc2845d9ff", "cjs/react.development.js": "1ff3a1d9861a87984329584fa1172aea920855d79eb57dae0d1cebe54093d7e3", "cjs/react-jsx-runtime.production.min.js": "76e3364c46895ed2c4a8d5cc332e5e4ef31d6f732d35b1e56826dc5895245452", "cjs/react.production.min.js": "4b35e378f469c4f492c7514bb106b5833746dbbae80496bd4aa9acc6e9ac4b42"};
for (const [path, hash] of Object.entries(reactPins)) infrastructureAssert.equal(digest(nativeReadFileSync(infrastructurePath.join(reactRoot, path))), hash, path);
infrastructureAssert.equal(compilerRequire('react/package.json').version, '18.3.1');
infrastructureAssert.equal(process.env.NODE_ENV, undefined);
infrastructureAssert.equal(globalThis.__REACT_DEVTOOLS_GLOBAL_HOOK__, undefined);
const selectedReadFileSync = (path, encoding) => {
  infrastructureAssert.equal(encoding, 'utf8');
  infrastructureAssert.ok(packages.has(path), 'Only explicitly selected component source may load');
  return packages.get(path);
};
const selectedCreateRequire = path => {
  infrastructureAssert.equal(path, infrastructurePath.resolve('package.json'));
  const fallback = nativeCreateRequire(path);
  return name => { infrastructureAssert.equal(name, 'react/jsx-runtime', 'Only pinned pure JSX fallback may load'); return fallback(name); };
};
let count = 0;
const control = (...args) => { count++; return test(...args); };
// BEGIN EXACT ORIGINAL TYPE-ERASED PROJECTION
import assert from "node:assert/strict";
import test from "node:test";
const readFileSync = selectedReadFileSync;
const createRequire = selectedCreateRequire;
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";


function fixture(spec = { containers: [{ name: "app" }] }, resourceType = "pod", controls = false) {
    const slots = [], effects = new Map();
    let index = 0, dirty = false, canWrite = true, tree, mounted = true, refetches = 0, callbacks = 0, deferredEffects = false, name = "fixture-pod";
    let scheduled = [];
    const reads = [];
    const timers = new Set();
    const react = {
        useRef: (initial) => {
            const key = index++;
            if (!(key in slots))
                slots[key] = { current: initial };
            return slots[key];
        },
        useState: (initial) => {
            const key = index++;
            if (!(key in slots))
                slots[key] = initial;
            return [slots[key], (value) => {
                    const next = typeof value === "function" ? value(slots[key]) : value;
                    if (!Object.is(next, slots[key])) {
                        slots[key] = next;
                        dirty = true;
                    }
                }];
        },
        useEffect: (run, deps) => {
            const key = index++, old = effects.get(key);
            if (!old || deps.some((value, i) => !Object.is(value, old.deps[i]))) {
                scheduled.push(() => {
                    old?.cleanup?.();
                    effects.set(key, { deps, cleanup: run() || undefined });
                });
            }
        },
    };
    const modules = {
        react,
        "next/dynamic": { __esModule: true, default: () => "PrivateModal" },
        "@radix-ui/react-dropdown-menu": { Root: "Root", Trigger: "Trigger", Portal: "Portal", Content: "Content", Item: "Item" },
        "lucide-react": { MoreHorizontal: "Icon" },
        "@/lib/resource-capabilities": capabilities,
        "@/lib/use-query": {
            useSession: () => ({ canWrite, data: { capabilities: { podExec: false } } }),
            refetchCluster: () => { refetches++; },
            requestJson: (url, init) => new Promise((resolve, reject) => reads.push({ url, signal: init.signal, resolve, reject })),
        },
        "@/lib/shell-manager": { openShell: () => { } },
        "./confirm-dialog": { __esModule: true, default: "Confirmation" },
    };
    const source = readFileSync(resolve(controls ? "src/components/cluster/deployment-controls.tsx" : "src/app/(dashboard)/resource-actions-menu.tsx"), "utf8");
    const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
    const componentModule = { exports: {} };
    const require = createRequire(resolve("package.json"));
    runInNewContext(output, {
        module: componentModule, exports: componentModule.exports, AbortController, Error, URLSearchParams,
        require: (name) => name in modules ? modules[name] : require(name),
        setTimeout: (run) => { timers.add(run); return run; },
        clearTimeout: (timer) => timers.delete(timer),
    });
    const render = () => {
        if (!mounted)
            return;
        let count = 0;
        do {
            assert(++count < 10, "Component effects did not settle");
            dirty = false;
            index = 0;
            scheduled = [];
            tree = controls ? componentModule.exports.DeploymentControls({ namespace: "apps", name, desired: 0 })
                : componentModule.exports.default({ resourceType, resource: { metadata: { name, namespace: "apps" }, spec }, onAction: () => { callbacks++; } });
            if (!deferredEffects)
                for (const run of scheduled)
                    run();
        } while (dirty);
    };
    function walk(node) {
        if (Array.isArray(node))
            return node.flatMap(child => walk(child));
        if (!node || typeof node !== "object" || !("props" in node))
            return [];
        const element = node;
        return [element, ...walk(element.props.children)];
    }
    const elements = () => walk(tree);
    const select = (name) => {
        const item = elements().find(element => element.type === "Item" && element.props.children === name);
        assert(item, "Advertised action missing");
        item.props.onSelect();
        render();
    };
    const settle = async (read, value) => {
        reads[read].resolve(value);
        for (let i = 0; i < 6; i++)
            await Promise.resolve();
        render();
    };
    const reject = async (read) => {
        reads[read].reject(new Error("Pod logs unavailable"));
        for (let i = 0; i < 6; i++)
            await Promise.resolve();
        render();
    };
    const logModal = () => elements().find(e => e.type === "PrivateModal" && Array.isArray(e.props.containers));
    const chooseContainer = (name) => {
        const modal = logModal();
        assert(modal);
        modal.props.onContainerChange(name);
        render();
    };
    const closeLogs = () => { const modal = logModal(); assert(modal); modal.props.onClose(); render(); };
    render();
    return { reads, select, settle, reject, chooseContainer, closeLogs, logModal, elements,
        render, access: (value, defer = false) => { canWrite = value; deferredEffects = defer; render(); }, timers,
        retarget: (value, defer = false) => { name = value; deferredEffects = defer; render(); },
        flushEffects: () => { deferredEffects = false; render(); },
        unmount: () => { mounted = false; for (const effect of effects.values())
            effect.cleanup?.(); },
        changes: () => ({ refetches, callbacks }) };
}
control("held mutations cannot notify/refetch after withdrawal or unmount, including confirmations and YAML saves", async () => {
    for (const mode of ["withdraw", "unmount"]) {
        for (const action of ["Restart", "Rollback", "Edit YAML"]) {
            for (const outcome of ["success", "error"]) {
                const f = fixture({ replicas: 1 }, "deployment");
                f.select(action);
                if (action === "Rollback") {
                    const dialog = f.elements().find(e => e.type === "Confirmation");
                    assert(dialog);
                    void dialog.props.onConfirm();
                    f.render();
                }
                else if (action === "Edit YAML") {
                    await f.settle(0, { yaml: "public synthetic YAML" });
                    const dialog = f.elements().find(e => e.type === "PrivateModal");
                    assert(dialog);
                    void dialog.props.onSave("public synthetic replacement").catch(() => { });
                    f.render();
                }
                const pending = f.reads.length - 1;
                if (mode === "withdraw")
                    f.access(false);
                else
                    f.unmount();
                if (outcome === "success")
                    await f.settle(pending, { success: true });
                else
                    await f.reject(pending);
                assert.deepEqual(f.changes(), { refetches: 0, callbacks: 0 }, `${action}/${mode}/${outcome}: late mutation must not own callbacks`);
                assert.equal(f.timers.size, 0, "Late mutation must not publish a notification timer");
                assert.equal(f.reads[pending].signal?.aborted, true, "Every submitted mutation must have an aborted owned signal");
                if (mode === "withdraw") {
                    f.access(true);
                    assert.equal(f.elements().filter(e => e.type === "PrivateModal" || e.type === "Confirmation").length, 0);
                }
            }
        }
    }
});
control("rendered role/target changes fence settlement before passive cleanup runs", async () => {
    for (const controls of [false, true])
        for (const change of ["role", "target"])
            for (const outcome of ["success", "error"]) {
                const f = fixture({ replicas: 1 }, "deployment", controls);
                if (controls) {
                    f.elements().find(e => e.type === "input").props.onChange({ target: { value: "2" } });
                    f.render();
                    void f.elements().find(e => e.type === "form").props.onSubmit({ preventDefault: () => { } });
                    f.render();
                }
                else
                    f.select("Restart");
                if (change === "role")
                    f.access(false, true);
                else
                    f.retarget("replacement", true);
                assert.equal(f.reads[0].signal.aborted, false, "The causal fixture deliberately delays passive cleanup");
                if (outcome === "success")
                    await f.settle(0, { success: true });
                else
                    await f.reject(0);
                assert.deepEqual(f.changes(), { refetches: 0, callbacks: 0 });
                assert.equal(f.timers.size, 0);
                f.flushEffects();
                assert.equal(f.reads[0].signal.aborted, true);
            }
});
control("deployment form fences held success/error across withdrawal and unmount", async () => {
    for (const mode of ["withdraw", "unmount"])
        for (const outcome of ["success", "error"]) {
            const f = fixture(undefined, "deployment", true);
            f.elements().find(e => e.type === "input").props.onChange({ target: { value: "2" } });
            f.render();
            void f.elements().find(e => e.type === "form").props.onSubmit({ preventDefault: () => { } });
            f.render();
            if (mode === "withdraw")
                f.access(false);
            else
                f.unmount();
            if (outcome === "success")
                await f.settle(0, { success: true });
            else
                await f.reject(0);
            assert.equal(f.changes().refetches, 0, "Disposed form must not refetch after settlement");
            assert.equal(f.reads[0].signal?.aborted, true);
            if (mode === "withdraw") {
                f.access(true);
                assert.equal(f.elements().find(e => e.type === "input").props.value, "0");
                assert.equal(f.elements().filter(e => e.props.role === "alert").length, 0);
            }
        }
});
control("owned action success refreshes; refusal retains confirmation and stale callbacks cannot submit", async () => {
    const f = fixture({ replicas: 1 }, "deployment");
    f.select("Rollback");
    const dialog = f.elements().find(e => e.type === "Confirmation");
    const submit = dialog.props.onConfirm;
    void submit();
    f.render();
    await f.reject(0);
    assert.equal(f.elements().filter(e => e.type === "Confirmation").length, 1);
    assert.equal(f.elements().find(e => e.props.role === "status").props.children, "Pod logs unavailable");
    assert.deepEqual(f.changes(), { refetches: 0, callbacks: 0 });
    void f.elements().find(e => e.type === "Confirmation").props.onConfirm();
    f.render();
    await f.settle(1, { success: true });
    assert.deepEqual(f.changes(), { refetches: 1, callbacks: 1 });
    assert.equal(f.elements().filter(e => e.type === "Confirmation").length, 0);
    assert.equal(f.reads.length, 2, "Only an explicit retry may submit again");
    f.unmount();
    void submit();
    await Promise.resolve();
    assert.equal(f.reads.length, 2);
    const scale = fixture(undefined, "deployment", true);
    scale.elements().find(e => e.type === "input").props.onChange({ target: { value: "2" } });
    scale.render();
    const scaleSubmit = scale.elements().find(e => e.type === "form").props.onSubmit;
    void scaleSubmit({ preventDefault: () => { } });
    scale.render();
    await scale.reject(0);
    assert.equal(scale.elements().find(e => e.type === "input").props.value, "2");
    assert.equal(scale.elements().filter(e => e.props.role === "alert").length, 1);
    scale.unmount();
    await scaleSubmit({ preventDefault: () => { } });
    assert.equal(scale.reads.length, 1);
});
control("YAML dialog save settlement cannot close or alter a replacement/unmounted dialog", async () => {
    const slots = [], effects = new Map();
    let index = 0, tree, closes = 0;
    let props = { open: true, yaml: "public original", title: "First", readOnly: false, onClose: () => { closes++; }, onSave: (_value) => Promise.resolve() };
    const react = {
        useRef: (initial) => { const key = index++; if (!(key in slots))
            slots[key] = { current: initial }; return slots[key]; },
        useState: (initial) => { const key = index++; if (!(key in slots))
            slots[key] = initial; return [slots[key], (value) => { slots[key] = typeof value === "function" ? value(slots[key]) : value; }]; },
        useEffect: (run, deps) => { const key = index++, old = effects.get(key); if (!old || deps.some((value, i) => !Object.is(value, old.deps[i]))) {
            old?.cleanup?.();
            effects.set(key, { deps, cleanup: run() || undefined });
        } },
    };
    const source = readFileSync(resolve("src/app/(dashboard)/yaml-modal.tsx"), "utf8");
    const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
    const componentModule = { exports: {} }, require = createRequire(resolve("package.json"));
    runInNewContext(output, { module: componentModule, exports: componentModule.exports, require: (name) => name === "react" ? react : name === "@/components/ui/modal" ? { Modal: "Modal" } : require(name) });
    const render = () => { index = 0; tree = componentModule.exports.default(props); index = 0; tree = componentModule.exports.default(props); };
    const walk = (node) => Array.isArray(node) ? node.flatMap(walk) : node && typeof node === "object" && "props" in node ? [node, ...walk(node.props.children), ...walk(node.props.actions)] : [];
    for (const disposition of ["replace", "unmount"])
        for (const outcome of ["success", "error"]) {
            let resolveSave, rejectSave;
            props = { ...props, title: "First" + disposition + outcome, onSave: () => new Promise((resolve, reject) => { resolveSave = resolve; rejectSave = reject; }) };
            render();
            walk(tree).find(e => e.type === "button" && e.props.children === "Edit").props.onClick();
            render();
            walk(tree).find(e => e.type === "textarea").props.onChange({ target: { value: "public changed" } });
            render();
            const save = walk(tree).find(e => e.type === "button" && e.props.children === "Save").props.onClick();
            if (disposition === "replace") {
                props = { ...props, title: "Replacement", yaml: "public replacement" };
                render();
            }
            else {
                for (const effect of effects.values())
                    effect.cleanup?.();
                effects.clear();
            }
            if (outcome === "success")
                resolveSave();
            else
                rejectSave(new Error("Fixed save refusal"));
            await save;
            assert.equal(closes, 0);
            if (disposition === "replace") {
                render();
                assert.equal(walk(tree).filter(e => e.props.role === "alert").length, 0);
                assert.equal(walk(tree).find(e => e.type === "pre").props.children, "public replacement");
            }
        }
});
control("fresh permission withdrawal erases held logs; public action trigger stays available and restore requires another read", async () => {
    const f = fixture();
    f.select("View Logs");
    await f.settle(0, { logs: "synthetic private log" });
    assert.equal(f.elements().filter(e => e.props.logs === "synthetic private log").length, 1);
    f.access(false);
    assert.equal(f.elements().filter(e => e.type === "PrivateModal").length, 0);
    assert.equal(f.elements().filter(e => e.type === "Item").length, 0);
    assert.equal(f.elements().filter(e => e.props["aria-label"] === "Actions for fixture-pod").length, 1);
    f.access(true);
    assert.equal(f.elements().filter(e => e.type === "PrivateModal").length, 0);
    assert.equal(f.reads.length, 1, "Restoration must not automatically reveal private content");
    f.select("View Logs");
    await f.settle(1, { logs: "new explicit snapshot" });
    assert.equal(f.elements().filter(e => e.props.logs === "new explicit snapshot").length, 1);
});
control("multiple containers require a choice; switching clears previous content and fences the first reply", async () => {
    const f = fixture({ containers: [{ name: "qbittorrent" }, { name: "gluetun" }], initContainers: [{ name: "setup" }], ephemeralContainers: [{ name: "debug" }] });
    f.select("View Logs");
    assert.equal(f.reads.length, 0);
    assert.deepEqual(Array.from(f.logModal().props.containers), ["qbittorrent", "gluetun", "setup", "debug"]);
    f.chooseContainer("unexpected");
    assert.equal(f.reads.length, 0);
    f.chooseContainer("gluetun");
    assert.equal(new URL(f.reads[0].url, "http://fixture").searchParams.get("container"), "gluetun");
    f.chooseContainer("qbittorrent");
    assert.equal(f.reads[0].signal.aborted, true);
    assert.equal(f.logModal().props.logs, undefined);
    await f.settle(1, { logs: "current qbittorrent snapshot" });
    await f.settle(0, { logs: "late gluetun snapshot" });
    assert.equal(f.logModal().props.logs, "current qbittorrent snapshot");
    f.chooseContainer("gluetun");
    assert.equal(f.logModal().props.logs, undefined);
    f.closeLogs();
    assert.equal(f.reads[2].signal.aborted, true);
    await f.settle(2, { logs: "closed snapshot" });
    assert.equal(f.logModal(), undefined);
});
control("list action resolves public Pod names once; absent metadata never triggers an unselected log read", async () => {
    const f = fixture(null);
    f.select("View Logs");
    assert.equal(f.reads.length, 1);
    assert.equal(f.reads[0].url, "/api/cluster/pods/apps/fixture-pod");
    await f.settle(0, { pod: { spec: { containers: [{ name: "qbittorrent" }, { name: "gluetun" }] } } });
    assert.equal(f.reads.length, 1);
    f.chooseContainer("gluetun");
    assert.equal(new URL(f.reads[1].url, "http://fixture").searchParams.get("container"), "gluetun");
    await f.reject(1);
    assert.equal(f.logModal().props.logs, undefined);
    assert.equal(f.logModal().props.error, "Pod logs unavailable");
    f.chooseContainer("qbittorrent");
    assert.equal(f.logModal().props.error, undefined);
    f.access(false);
    assert.equal(f.reads[2].signal.aborted, true);
    await f.settle(2, { logs: "withdrawn container snapshot" });
    f.access(true);
    assert.equal(f.logModal(), undefined);
    const failed = fixture(null);
    failed.select("View Logs");
    await failed.reject(0);
    assert.equal(failed.reads.length, 1);
    assert.equal(failed.logModal(), undefined);
    const empty = fixture({ containers: [] });
    empty.select("View Logs");
    assert.equal(empty.reads.length, 0);
    assert.deepEqual(Array.from(empty.logModal().props.containers), []);
});
control("held private read is aborted on withdrawal and cannot repopulate after session restoration", async () => {
    const f = fixture();
    f.select("View Logs");
    f.access(false);
    assert.equal(f.reads[0].signal.aborted, true);
    f.access(true);
    f.select("View Logs");
    await f.settle(1, { logs: "current explicit snapshot" });
    await f.settle(0, { logs: "late withdrawn snapshot" });
    assert.equal(f.elements().filter(e => e.props.logs === "late withdrawn snapshot").length, 0);
    assert.equal(f.elements().filter(e => e.props.logs === "current explicit snapshot").length, 1);
});
control("held YAML viewer/editor and confirmations are erased; stale YAML completion is fenced", async () => {
    for (const action of ["View YAML", "Edit YAML"]) {
        const f = fixture();
        f.select(action);
        await f.settle(0, { yaml: "synthetic YAML snapshot" });
        assert.equal(f.elements().filter(e => e.props.yaml === "synthetic YAML snapshot").length, 1);
        f.access(false);
        f.access(true);
        assert.equal(f.elements().filter(e => e.type === "PrivateModal").length, 0);
        f.select(action);
        f.access(false);
        await f.settle(1, { yaml: "late YAML" });
        f.access(true);
        assert.equal(f.reads[1].signal.aborted, true);
        assert.equal(f.elements().filter(e => e.type === "PrivateModal").length, 0);
        f.select("Delete");
        assert.equal(f.elements().filter(e => e.type === "Confirmation").length, 1);
        f.access(false);
        f.access(true);
        assert.equal(f.elements().filter(e => e.type === "Confirmation").length, 0);
    }
});
control("log dialog permits explicit same-container refresh and provides a named container choice", () => {
    const require = createRequire(resolve("package.json"));
    const source = readFileSync(resolve("src/app/(dashboard)/log-modal.tsx"), "utf8");
    const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
    const componentModule = { exports: {} };
    runInNewContext(output, {
        module: componentModule, exports: componentModule.exports,
        require: (name) => name === "@/components/ui/modal" ? { Modal: "Dialog" } : require(name),
    });
    const choices = [];
    const props = { open: true, onClose: () => { }, title: "Public fixture", containers: ["app", "sidecar"], container: "sidecar", loading: false,
        error: "Pod logs unavailable", onContainerChange: (name) => choices.push(name) };
    const walk = (node) => Array.isArray(node) ? node.flatMap(walk) : node && typeof node === "object" && "props" in node
        ? [node, ...walk(node.props.children)] : [];
    const elements = walk(componentModule.exports.default(props));
    const label = elements.find(e => e.type === "label");
    assert(label);
    assert.equal(label.props.children[0], "Container");
    const select = elements.find(e => e.type === "select");
    assert(select);
    assert.equal(select.props.value, "sidecar");
    assert.equal(select.props.disabled, false);
    const refresh = elements.find(e => e.type === "button" && e.props.children === "Refresh logs");
    assert(refresh);
    assert.equal(refresh.props.disabled, false);
    refresh.props.onClick();
    assert.deepEqual(choices, ["sidecar"], "Retry must request the same selected container");
    assert.equal(elements.filter(e => e.type === "pre").length, 0, "Failure cannot display false empty output");
    const pending = walk(componentModule.exports.default({ ...props, loading: true, error: undefined }));
    assert.equal(pending.find(e => e.type === "button").props.disabled, true);
    assert.equal(pending.find(e => e.type === "select").props.disabled, false, "Selection must remain available to abort a held container read");
});
// END EXACT ORIGINAL TYPE-ERASED PROJECTION
assert.equal(count, 11);
