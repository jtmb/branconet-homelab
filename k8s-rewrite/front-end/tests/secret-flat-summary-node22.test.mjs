import infrastructureAssert from 'node:assert/strict';
import { createHash as infrastructureHash } from 'node:crypto';
import { readFileSync as infrastructureRead, existsSync as infrastructureExists } from 'node:fs';
import { createRequire as infrastructureRequire, Module as InfrastructureModule } from 'node:module';
import { fileURLToPath as infrastructurePath } from 'node:url';
infrastructureAssert.equal(process.version, 'v22.23.3');
infrastructureAssert.equal(process.platform, 'linux');
infrastructureAssert.notEqual(process.getuid(), 0);
const infrastructureTS = infrastructureRequire(import.meta.url)('typescript');
infrastructureAssert.equal(infrastructureTS.version, '5.9.3');
const infrastructurePins = {
  "src/lib/cluster-secrets.ts": "229d39c4d9af1d10858c86d280dd59a7f281d9892bb8b0381a97e1b642e09a5c",
  "src/lib/secret-ascii-span.ts": "94eaa99e9acb826fb3d42c55e7921642bfbbc972aa5011f72ee8ff46abdbcd39",
  "src/lib/secret-flat-summary.ts": "fb13d8b6cfea7bcd01a2ea48b88c93ea34879b0c271b6a4fea1bfe621284a3fe",
  "src/lib/secret-summary-json.ts": "63dcda3bdfbd379815c310fb879c29d99cdc6c237c7d88867fe9b701c24ad01e",
  "tests/secret-flat-summary.test.ts": "c74aef3eadce175d03a6e944f0f82f89279ee5ffaf1b7fbd71a2df60c2832a40"
};
for (const [file, hash] of Object.entries(infrastructurePins)) infrastructureAssert.equal(infrastructureHash('sha256').update(infrastructureRead(new URL('../' + file, import.meta.url))).digest('hex'), hash, file);
infrastructureAssert.equal(infrastructureExists(new URL('../native/secret-flat-selector.node', import.meta.url)), false);
const infrastructureCache = new Map();
const infrastructureFiles = new Set(Object.keys(infrastructurePins).filter(file => file.startsWith('src/')));
const infrastructureBuiltins = new Set(['node:fs', 'node:path', 'node:buffer']);
function infrastructureLoad(file) {
  infrastructureAssert.ok(infrastructureFiles.has(file), file);
  if (infrastructureCache.has(file)) return infrastructureCache.get(file).exports;
  const filename = infrastructurePath(new URL('../' + file, import.meta.url));
  const result = infrastructureTS.transpileModule(infrastructureRead(filename, 'utf8'), { fileName: filename, reportDiagnostics: true, compilerOptions: { target: infrastructureTS.ScriptTarget.ES2022, module: infrastructureTS.ModuleKind.CommonJS, esModuleInterop: true } });
  infrastructureAssert.equal(result.diagnostics.length, 0);
  const compiled = new InfrastructureModule(filename);
  infrastructureCache.set(file, compiled);
  compiled.require = name => {
    if (infrastructureBuiltins.has(name)) return infrastructureRequire(import.meta.url)(name);
    infrastructureAssert.ok(/^\.\/[a-z-]+$/.test(name), name);
    return infrastructureLoad('src/lib/' + name.slice(2) + '.ts');
  };
  compiled._compile(result.outputText, filename);
  return compiled.exports;
}
const infrastructureCluster = infrastructureLoad('src/lib/cluster-secrets.ts');
const infrastructureSummary = infrastructureLoad('src/lib/secret-summary-json.ts');
const infrastructureFlat = infrastructureLoad('src/lib/secret-flat-summary.ts');
infrastructureAssert.equal(infrastructureCache.size, 4);
const infrastructureOrder = [
  "portable flat fallback preserves generic projection across every split without private fields",
  "native parser ABI receives exact chunks; native faults never invoke portable decoder fallback",
  "flat Store visits share budget and retain namespace ordering; generic and values paths remain independent",
  "native loader permits only ENOENT fallback; filesystem/load/ABI faults fail closed without retry",
  "actual missing/nonregular/inaccessible module paths distinguish filesystem errors from absence"
];
let count = 0;
const control = (name, ...args) => {
  infrastructureAssert.equal(name, infrastructureOrder[count++]);
  return test(name, ...args);
};
// BEGIN EXACT ORIGINAL TYPE-ERASED PROJECTION
import test from "node:test";
import assert from "node:assert/strict";
const { createFlatSummaryParser, createNativeSelectorLoader, parseFlatSecretSummaryPage } = infrastructureFlat;
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
const { parseSecretSummaryPage } = infrastructureSummary;
const { SecretError, SecretStore } = infrastructureCluster;
const raw = Buffer.from('{"apiVersion":"v1","kind":"SecretList","metadata":{"continue":"cursor"},"items":[{"apiVersion":"v1","kind":"Secret","metadata":{"namespace":"apps","name":"public","uid":"uid","resourceVersion":"rv","unknown":{"nested":"PRIVATE_METADATA"}},"type":"Opaque","data":{"__proto__":"PRIVATE_VALUE","":"","snow-雪":"AA=="}}]}');
const project = (chunks) => {
    const page = parseSecretSummaryPage(chunks, "apps", 200);
    return { items: page.items.map(s => ({ namespace: s.metadata.namespace, name: s.metadata.name, resourceVersion: s.metadata.resourceVersion, type: s.type, immutable: s.immutable, keys: s.keys })), cursor: page.cursor };
};
control("portable flat fallback preserves generic projection across every split without private fields", () => {
    const fallback = createFlatSummaryParser();
    for (let split = 0; split <= raw.length; split++) {
        const chunks = [raw.subarray(0, split), Buffer.alloc(0), raw.subarray(split)];
        assert.deepEqual(fallback(chunks, "apps", 200), project(chunks));
    }
    assert.deepEqual(parseFlatSecretSummaryPage([raw], "apps", 200), project([raw]));
    assert.equal(JSON.stringify(project([raw])).includes("PRIVATE_"), false);
});
control("native parser ABI receives exact chunks; native faults never invoke portable decoder fallback", () => {
    const expected = project([raw]);
    let calls = 0;
    const parser = createFlatSummaryParser({ flat(chunks, limit, namespace) { calls++; assert.equal(chunks[0], raw); assert.equal(limit, 200); assert.equal(namespace, "apps"); return expected; } });
    assert.equal(parser([raw], "apps", 200), expected);
    assert.equal(calls, 1);
    const decoder = TextDecoder.prototype.decode;
    TextDecoder.prototype.decode = () => { throw Error("Fallback must not run after a native fault"); };
    try {
        const failing = createFlatSummaryParser({ flat() { calls++; throw Error("PRIVATE_DYNAMIC_NATIVE_ERROR"); } });
        assert.throws(() => failing([raw], "apps", 200), e => e instanceof SecretError && e.status === 503 && e.message === "Invalid Kubernetes Secret summary response");
        assert.equal(calls, 2);
    }
    finally {
        TextDecoder.prototype.decode = decoder;
    }
});
control("flat Store visits share budget and retain namespace ordering; generic and values paths remain independent", async () => {
    const forbidden = async () => { throw Error("Unexpected native value or mutation operation"); };
    const transport = { read: forbidden, create: forbidden, replace: forbidden, async listFlatSummaries(namespace, options) {
            options.budget.consumeItems(1);
            options.visit({ namespace, name: "public", resourceVersion: "rv", type: "Opaque", immutable: false, keys: ["__proto__"] });
            return [];
        }, list: async () => { throw Error("Full values must not be read"); }, listSummaries: async () => { throw Error("Generic metadata must not be read"); } };
    const rows = await new SecretStore(transport, ["apps", "other"], undefined, 8).list();
    assert.deepEqual(rows.map(row => row.namespace), ["apps", "other"]);
    assert.equal(rows.length, 2);
});
const fixed = (error) => error instanceof SecretError && error.status === 503 && error.message === "Invalid Kubernetes Secret summary response";
control("native loader permits only ENOENT fallback; filesystem/load/ABI faults fail closed without retry", () => {
    let loads = 0;
    const read = () => { loads++; return { flat() { return project([raw]); } }; };
    assert.equal(createNativeSelectorLoader("missing", () => { throw Object.assign(Error("PRIVATE_FS"), { code: "ENOENT" }); }, read)(), undefined);
    for (const code of ["EACCES", "ENOTDIR", "EIO"])
        assert.throws(createNativeSelectorLoader("file", () => { throw Object.assign(Error("PRIVATE_FS"), { code }); }, read), fixed);
    assert.equal(loads, 0);
    assert.throws(createNativeSelectorLoader("dir", () => ({ isFile: () => false }), read), fixed);
    assert.equal(loads, 0);
    for (const load of [() => { loads++; throw Error("PRIVATE_LOAD_ERROR"); }, () => { loads++; return { flat: false }; }]) {
        const loader = createNativeSelectorLoader("file", () => ({ isFile: () => true }), load);
        const before = loads;
        assert.throws(loader, fixed);
        assert.equal(loads, before + 1);
    }
});
control("actual missing/nonregular/inaccessible module paths distinguish filesystem errors from absence", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "bortus-native-loader-"));
    const sealed = path.join(dir, "sealed");
    let loads = 0;
    try {
        const load = () => { loads++; throw Error("Unexpected native loading"); };
        assert.equal(createNativeSelectorLoader(path.join(dir, "absent.node"), fs.lstatSync, load)(), undefined);
        const file = path.join(dir, "plain");
        fs.writeFileSync(file, "public");
        assert.throws(createNativeSelectorLoader(path.join(file, "child.node"), fs.lstatSync, load), fixed);
        assert.throws(createNativeSelectorLoader(dir, fs.lstatSync, load), fixed);
        fs.mkdirSync(sealed);
        fs.writeFileSync(path.join(sealed, "public.node"), "public");
        if (process.platform !== "win32") {
            fs.chmodSync(sealed, 0);
            assert.throws(() => fs.lstatSync(path.join(sealed, "public.node")), (error) => error.code === "EACCES");
            assert.throws(createNativeSelectorLoader(path.join(sealed, "public.node"), fs.lstatSync, load), fixed);
        }
        assert.equal(loads, 0);
    }
    finally {
        if (fs.existsSync(sealed))
            fs.chmodSync(sealed, 0o700);
        assert.equal(path.dirname(dir), os.tmpdir());
        assert(path.basename(dir).startsWith("bortus-native-loader-"));
        fs.rmSync(dir, { recursive: true, force: true });
    }
});
// END EXACT ORIGINAL TYPE-ERASED PROJECTION
infrastructureAssert.equal(count, 5);
