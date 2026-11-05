// DISTINCT NEW4 complete PUBLIC Settings fixture controls, with genuine MutationTask and original hook/component VM.
import infrastructureAssert from 'node:assert/strict';
import { createHash as infrastructureHash } from 'node:crypto';
import { readFileSync as infrastructureRead } from 'node:fs';
import { createRequire as infrastructureRequire, Module as InfrastructureModule } from 'node:module';
const infrastructureTS = infrastructureRequire(import.meta.url)('typescript');
infrastructureAssert.equal(infrastructureTS.version, '5.9.3');
infrastructureAssert.equal(process.version, 'v22.23.3');
for (const [path, hash] of [
  [
    "tests/settings-mutation-lifecycle.test.ts",
    "4808d5b1b2ae1b198bf65e6f60cca6ef6acab6e5cc6a3707a705e9ec726922e4"
  ],
  [
    "src/lib/mutation-task.ts",
    "a344c7e8838cdbbb944067a38bdd9b4546ae115c5c4c495bba40a8ec1ed7a5b4"
  ],
  [
    "src/lib/use-mutation.ts",
    "d898d8fd547ddb8c967bfcb8fab7410aca5ee294ba0cf69ed889c90624c8f4eb"
  ],
  [
    "src/app/(dashboard)/settings/page.tsx",
    "45d71a8e38925d9cb30c1529116018e9f5e5abe033f43f9659d692ac043f6b5b"
  ]
]) infrastructureAssert.equal(infrastructureHash('sha256').update(infrastructureRead(new URL('../' + path, import.meta.url))).digest('hex'), hash, path);
const infrastructureSource = infrastructureRead(new URL('../src/lib/mutation-task.ts', import.meta.url), 'utf8');
const infrastructureResult = infrastructureTS.transpileModule(infrastructureSource, { reportDiagnostics: true,
  compilerOptions: { target: infrastructureTS.ScriptTarget.ES2022, module: infrastructureTS.ModuleKind.CommonJS, strict: true } });
infrastructureAssert.equal(infrastructureResult.diagnostics.length, 0);
const infrastructureFilename = new URL('../src/lib/mutation-task.cjs', import.meta.url).pathname;
const infrastructureMutationModule = new InfrastructureModule(infrastructureFilename);
infrastructureMutationModule.filename = infrastructureFilename;
infrastructureMutationModule._compile(infrastructureResult.outputText, infrastructureFilename);
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
const { MutationTask } = infrastructureMutationModule.exports;
function fixture() {
    const slots = [], effects = new Map();
    let index = 0, dirty = false, canWrite = true, tree, defer = false;
    let scheduled = [];
    const refetches = [], requests = [];
    const react = {
        useRef: (initial) => { const key = index++; if (!(key in slots))
            slots[key] = { current: initial }; return slots[key]; },
        useMemo: (create, deps) => { const key = index++, old = slots[key]; if (!old || deps.some((v, i) => !Object.is(v, old.deps[i])))
            slots[key] = { deps, value: create() }; return slots[key].value; },
        useState: (initial) => { const key = index++; if (!(key in slots))
            slots[key] = initial; return [slots[key], (value) => { const next = typeof value === "function" ? value(slots[key]) : value; if (!Object.is(next, slots[key])) {
                slots[key] = next;
                dirty = true;
            } }]; },
        useEffect: (run, deps) => { const key = index++, old = effects.get(key); if (!old || deps.some((v, i) => !Object.is(v, old.deps[i])))
            scheduled.push(() => { old?.cleanup?.(); effects.set(key, { deps, cleanup: run() || undefined }); }); },
    };
    const volume = { name: "fixture-volume", reclaimPolicy: "Retain", status: "Bound", storageClass: "fixture", capacity: "1Gi", claimRef: "apps/data", age: "2026-10-11" };
    const query = { useSession: () => ({ canWrite, data: { authenticated: true, registrationOpen: false }, refetch: () => refetches.push("session") }),
        useQuery: (url) => ({ data: url === "/api/settings" ? { allow_registration: "false" } : { volumes: [volume] }, loading: false, error: undefined, refetch: () => refetches.push(url) }),
        requestJson: (_url, init) => new Promise((resolve, reject) => requests.push({ signal: init.signal, resolve, reject })),
    };
    const modules = { react, "@/lib/use-query": query, "./use-query": query, "./mutation-task": { MutationTask }, "next/link": { __esModule: true, default: "Link" }, "next/dynamic": { __esModule: true, default: () => "Confirmation" }, "@/components/cluster/resource-list": { ResourceTable: "ResourceTable" }, "@/components/ui/query-status": { QueryStatus: "QueryStatus" }, "../viewport-wrapper": { __esModule: true, default: "Viewport", setViewMode: () => { } } };
    const require = createRequire(resolve("package.json"));
    const load = (path) => {
        const output = ts.transpileModule(readFileSync(resolve(path), "utf8"), { fileName: path, compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
        const componentModule = { exports: {} };
        runInNewContext(output, { module: componentModule, exports: componentModule.exports, Error, localStorage: { getItem: () => null }, require: (name) => name in modules ? modules[name] : require(name) });
        return componentModule.exports;
    };
    modules["@/lib/use-mutation"] = load("src/lib/use-mutation.ts");
    const page = load("src/app/(dashboard)/settings/page.tsx").default;
    const render = () => { let count = 0; do {
        assert(++count < 10);
        index = 0;
        dirty = false;
        scheduled = [];
        tree = page();
        if (!defer)
            for (const run of scheduled)
                run();
    } while (dirty); };
    const walk = (node) => Array.isArray(node) ? node.flatMap(walk) : node && typeof node === "object" && "props" in node ? [node, ...walk(node.props.children)] : [];
    const elements = () => walk(tree);
    render();
    return { requests, refetches, elements,
        start: (action) => {
            if (action === "registration")
                elements().find(e => e.props.role === "switch").props.onClick();
            else {
                const button = elements().find(e => e.type === "ResourceTable").props.renderActions(volume);
                button.props.onClick();
                render();
                elements().find(e => e.type === "select").props.onChange({ target: { value: "Delete" } });
                render();
                elements().find(e => e.type === "Confirmation").props.onConfirm();
            }
            render();
        },
        access: (value, delayed = false) => { canWrite = value; defer = delayed; render(); },
        flush: () => { defer = false; render(); },
        settle: async (outcome, request = 0) => {
            if (outcome === "success")
                requests[request].resolve({ success: true, results: [{ success: true }] });
            else if (outcome === "partial")
                requests[request].resolve({ success: false, results: [{ success: false, error: "Fixed policy refusal" }] });
            else
                requests[request].reject(new Error("Fixed mutation refusal"));
            for (let i = 0; i < 8; i++)
                await Promise.resolve();
            render();
        },
    };
}
control("held Settings mutations cannot notify/refetch after fresh write withdrawal", async () => {
    for (const action of ["registration", "reclaim"])
        for (const outcome of ["success", "error"]) {
            const f = fixture();
            f.start(action);
            f.access(false);
            await f.settle(outcome);
            assert.deepEqual(f.refetches, [], "Withdrawn Settings owner must not refresh after settlement");
            assert.equal(f.elements().filter(e => e.props.role === "status" || e.props.role === "alert").length, 0);
            assert.equal(f.requests[0].signal.aborted, true);
            f.access(true);
            assert.equal(f.requests.length, 1, "Restoration cannot retry an ambiguous operation");
            assert.equal(f.elements().filter(e => e.type === "Confirmation").length, 0);
        }
});
control("Settings permission ABA before passive cleanup cannot revive a held owner", async () => {
    for (const outcome of ["success", "error"]) {
        const f = fixture();
        f.start("registration");
        f.access(false, true);
        f.access(true, true);
        await f.settle(outcome);
        assert.deepEqual(f.refetches, []);
        assert.equal(f.elements().filter(e => e.props.role === "status" || e.props.role === "alert").length, 0);
        f.flush();
    }
});
control("owned Settings true success still refreshes; current refusal remains actionable", async () => {
    for (const outcome of ["success", "error"]) {
        const f = fixture();
        f.start("registration");
        await f.settle(outcome);
        assert.deepEqual(f.refetches, outcome === "success" ? ["/api/settings", "session"] : []);
        assert.equal(f.elements().filter(e => e.props.role === (outcome === "success" ? "status" : "alert")).length, 1);
    }
});
control("owned reclaim partial failure retains its confirmation without a success notice", async () => {
    const f = fixture();
    f.start("reclaim");
    await f.settle("partial");
    assert.deepEqual(f.refetches, ["/api/cluster/volumes/reclaim"]);
    const dialog = f.elements().find(e => e.type === "Confirmation");
    assert(dialog);
    assert.equal(dialog.props.error, "Fixed policy refusal");
    assert.equal(f.elements().filter(e => e.props.role === "status").length, 0);
    assert.equal(f.requests.length, 1, "Partial failure must not automatically retry");
});
// END EXACT ORIGINAL TYPE-ERASED PROJECTION
infrastructureAssert.equal(count, 4);
