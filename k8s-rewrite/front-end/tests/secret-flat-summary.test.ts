import test from "node:test";
import assert from "node:assert/strict";
import { createFlatSummaryParser, createNativeSelectorLoader, parseFlatSecretSummaryPage } from "../src/lib/secret-flat-summary";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { parseSecretSummaryPage } from "../src/lib/secret-summary-json";
import { SecretError, SecretStore, type SecretTransport } from "../src/lib/cluster-secrets";

const raw = Buffer.from('{"apiVersion":"v1","kind":"SecretList","metadata":{"continue":"cursor"},"items":[{"apiVersion":"v1","kind":"Secret","metadata":{"namespace":"apps","name":"public","uid":"uid","resourceVersion":"rv","unknown":{"nested":"PRIVATE_METADATA"}},"type":"Opaque","data":{"__proto__":"PRIVATE_VALUE","":"","snow-雪":"AA=="}}]}');
const project = (chunks: Buffer[]) => {
  const page = parseSecretSummaryPage(chunks, "apps", 200);
  return { items: page.items.map(s => ({ namespace: s.metadata.namespace, name: s.metadata.name, resourceVersion: s.metadata.resourceVersion, type: s.type, immutable: s.immutable, keys: s.keys })), cursor: page.cursor };
};
test("portable flat fallback preserves generic projection across every split without private fields", () => {
  const fallback = createFlatSummaryParser();
  for (let split = 0; split <= raw.length; split++) {
    const chunks = [raw.subarray(0, split), Buffer.alloc(0), raw.subarray(split)];
    assert.deepEqual(fallback(chunks, "apps", 200), project(chunks));
  }
  assert.deepEqual(parseFlatSecretSummaryPage([raw], "apps", 200), project([raw]));
  assert.equal(JSON.stringify(project([raw])).includes("PRIVATE_"), false);
});
test("native parser ABI receives exact chunks; native faults never invoke portable decoder fallback", () => {
  const expected = project([raw]); let calls = 0;
  const parser = createFlatSummaryParser({ flat(chunks, limit, namespace) { calls++; assert.equal(chunks[0], raw); assert.equal(limit, 200); assert.equal(namespace, "apps"); return expected; } });
  assert.equal(parser([raw], "apps", 200), expected); assert.equal(calls, 1);
  const decoder = TextDecoder.prototype.decode;
  TextDecoder.prototype.decode = () => { throw Error("Fallback must not run after a native fault"); };
  try {
    const failing = createFlatSummaryParser({ flat() { calls++; throw Error("PRIVATE_DYNAMIC_NATIVE_ERROR"); } });
    assert.throws(() => failing([raw], "apps", 200), e => e instanceof SecretError && e.status === 503 && e.message === "Invalid Kubernetes Secret summary response");
    assert.equal(calls, 2);
  } finally { TextDecoder.prototype.decode = decoder; }
});
test("flat Store visits share budget and retain namespace ordering; generic and values paths remain independent", async () => {
  const forbidden = async (): Promise<never> => { throw Error("Unexpected native value or mutation operation"); };
  const transport: SecretTransport = { read: forbidden, create: forbidden, replace: forbidden, async listFlatSummaries(namespace, options) {
    options!.budget!.consumeItems(1);
    options!.visit!({ namespace, name: "public", resourceVersion: "rv", type: "Opaque", immutable: false, keys: ["__proto__"] });
    return [];
  }, list: async () => { throw Error("Full values must not be read"); }, listSummaries: async () => { throw Error("Generic metadata must not be read"); } };
  const rows = await new SecretStore(transport, ["apps", "other"], undefined, 8).list();
  assert.deepEqual(rows.map(row => row.namespace), ["apps", "other"]);
  assert.equal(rows.length, 2);
});
const fixed = (error: unknown) => error instanceof SecretError && error.status === 503 && error.message === "Invalid Kubernetes Secret summary response";
test("native loader permits only ENOENT fallback; filesystem/load/ABI faults fail closed without retry", () => {
  let loads = 0;
  const read = () => { loads++; return { flat() { return project([raw]); } }; };
  assert.equal(createNativeSelectorLoader("missing", () => { throw Object.assign(Error("PRIVATE_FS"), { code: "ENOENT" }); }, read)(), undefined);
  for (const code of ["EACCES", "ENOTDIR", "EIO"]) assert.throws(createNativeSelectorLoader("file", () => { throw Object.assign(Error("PRIVATE_FS"), { code }); }, read), fixed);
  assert.equal(loads, 0);
  assert.throws(createNativeSelectorLoader("dir", () => ({ isFile: () => false }), read), fixed); assert.equal(loads, 0);
  for (const load of [() => { loads++; throw Error("PRIVATE_LOAD_ERROR"); }, () => { loads++; return { flat: false }; }]) {
    const loader = createNativeSelectorLoader("file", () => ({ isFile: () => true }), load);
    const before: number = loads; assert.throws(loader, fixed); assert.equal(loads, before + 1);
  }
});
test("actual missing/nonregular/inaccessible module paths distinguish filesystem errors from absence", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "bortus-native-loader-"));
  const sealed = path.join(dir, "sealed"); let loads = 0;
  try {
    const load = () => { loads++; throw Error("Unexpected native loading"); };
    assert.equal(createNativeSelectorLoader(path.join(dir, "absent.node"), fs.lstatSync, load)(), undefined);
    const file = path.join(dir, "plain"); fs.writeFileSync(file, "public");
    assert.throws(createNativeSelectorLoader(path.join(file, "child.node"), fs.lstatSync, load), fixed);
    assert.throws(createNativeSelectorLoader(dir, fs.lstatSync, load), fixed);
    fs.mkdirSync(sealed); fs.writeFileSync(path.join(sealed, "public.node"), "public");
    if (process.platform !== "win32") {
      fs.chmodSync(sealed, 0);
      assert.throws(() => fs.lstatSync(path.join(sealed, "public.node")), (error: unknown) => (error as NodeJS.ErrnoException).code === "EACCES");
      assert.throws(createNativeSelectorLoader(path.join(sealed, "public.node"), fs.lstatSync, load), fixed);
    }
    assert.equal(loads, 0);
  } finally {
    if (fs.existsSync(sealed)) fs.chmodSync(sealed, 0o700);
    assert.equal(path.dirname(dir), os.tmpdir()); assert(path.basename(dir).startsWith("bortus-native-loader-"));
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
