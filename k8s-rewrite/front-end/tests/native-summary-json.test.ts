import test from "node:test";
import assert from "node:assert/strict";
import { parseSecretSummaryPage } from "../src/lib/secret-summary-json";

const metadata = { namespace: "apps", name: "public", uid: "public-uid", resourceVersion: "public-rv", annotations: { "bortus.io/kv-state": '{"format":1}' }, labels: { public: "label" } };
const page = (data: unknown = { public: "VALUE_SENTINEL" }, extra: Record<string, unknown> = {}) => JSON.stringify({ apiVersion: "v1", kind: "SecretList", metadata: { continue: "public-cursor" }, items: [{ apiVersion: "v1", kind: "Secret", metadata, data, type: "Opaque", immutable: true, ...extra }] });
const parse = (text: string) => parseSecretSummaryPage([Buffer.from(text)], "apps", 200);
const refuse = (raw: string | Buffer) => assert.throws(() => parseSecretSummaryPage([Buffer.isBuffer(raw) ? raw : Buffer.from(raw)], "apps", 200), error => {
  assert.equal((error as Error).message, "Invalid Kubernetes Secret summary response"); return true;
});

test("fatal selected-field decoder is document-owned and no decode failure contaminates the next document", () => {
  const Original = TextDecoder;
  let constructions = 0, decodes = 0, failAt = Infinity;
  class ObservedDecoder extends Original {
    constructor(label?: string, options?: TextDecoderOptions) {
      super(label, options); constructions++; assert.equal(options?.fatal, true);
    }
    decode(...args: Parameters<TextDecoder["decode"]>) {
      if (++decodes === failAt) throw new Error("PRIVATE_DYNAMIC_DECODER_ERROR");
      return super.decode(...args);
    }
  }
  Object.defineProperty(globalThis, "TextDecoder", { value: ObservedDecoder, writable: true, configurable: true });
  try {
    const raw = Buffer.from(page({ binary: "AA==", public: "VALUE_SENTINEL" }, { metadata: { ...metadata, annotations: { public: "snow-雪😀\n\"\\" } } }));
    const chunks = Array.from(raw, (_, i) => raw.subarray(i, i + 1));
    const expected = parseSecretSummaryPage(chunks, "apps", 200);
    assert.equal(constructions, 1); assert.ok(decodes > 10);
    assert.equal(JSON.stringify(expected).includes("VALUE_SENTINEL"), false);
    failAt = decodes + 3;
    assert.throws(() => parseSecretSummaryPage(chunks, "apps", 200), error => {
      assert.equal((error as Error).message, "Invalid Kubernetes Secret summary response"); return true;
    });
    assert.equal(constructions, 2); failAt = Infinity;
    assert.deepEqual(parseSecretSummaryPage(chunks, "apps", 200), expected);
    assert.equal(constructions, 3);
  } finally { Object.defineProperty(globalThis, "TextDecoder", { value: Original, writable: true, configurable: true }); }
});

test("summary retains exact metadata/key identity across every byte/chunk split, without value DTOs", () => {
  const data = JSON.parse('{"__proto__":"VALUE_SENTINEL","constructor":"","toString":"AA==","":"snow-雪😀","binary":"\\u0000\\n\\\"\\\\"}');
  const raw = Buffer.from(page(data, { stringData: { private: "VALUE_SENTINEL" }, unknown: [{ private: "VALUE_SENTINEL", number: -1.25e3, nested: [true, false, null] }] }));
  const expected = { items: [{ metadata, type: "Opaque", immutable: true, keys: ["", "__proto__", "binary", "constructor", "toString"] }], cursor: "public-cursor" };
  for (let i = 0; i <= raw.length; i++) assert.deepEqual(parseSecretSummaryPage([raw.subarray(0, i), Buffer.alloc(0), raw.subarray(i)], "apps", 200), expected);
  assert.deepEqual(parseSecretSummaryPage(Array.from(raw, (_, i) => raw.subarray(i, i + 1)), "apps", 200), expected);
  assert.equal(Object.hasOwn(expected.items[0], "data"), false);
  assert.equal(Object.prototype.hasOwnProperty.call({}, "public"), false);
});

test("accepted values and unknown-field values are never decoded or JSON-materialized", () => {
  const raw = Buffer.from(page({ public: "VALUE_SENTINEL".repeat(100000) }, { stringData: { text: "VALUE_SENTINEL" }, unknown: { values: ["VALUE_SENTINEL", { more: "VALUE_SENTINEL" }] } }));
  const decode = TextDecoder.prototype.decode, json = JSON.parse;
  TextDecoder.prototype.decode = function (...args) {
    const value = Reflect.apply(decode, this, args); assert.equal(value.includes("VALUE_SENTINEL"), false, "only selected metadata/key/header bytes may be decoded"); return value;
  };
  JSON.parse = (text, reviver) => { assert.equal(text.includes("VALUE_SENTINEL"), false); return json(text, reviver); };
  try {
    const result = parseSecretSummaryPage([raw.subarray(0, 100), raw.subarray(100, 10003), raw.subarray(10003)], "apps", 200);
    assert.deepEqual(result.items[0].keys, ["public"]); assert.equal(JSON.stringify(result).includes("VALUE_SENTINEL"), false);
  } finally { TextDecoder.prototype.decode = decode; JSON.parse = json; }
});

test("complete validation rejects malformed skipped values and invalid UTF8 even after valid metadata", () => {
  const prefix = page().replace('"VALUE_SENTINEL"', '"REPLACE"');
  for (const value of ['"\\x"', '"\\u00gg"', '"\u0000"', '01', '1e', 'truefalse', '[1,]', '{"a":1,}', '"unfinished', '"\\']) refuse(prefix.replace('"REPLACE"', value));
  for (const bytes of [[0xc0, 0x80], [0xe0, 0x80, 0x80], [0xed, 0xa0, 0x80], [0xf4, 0x90, 0x80, 0x80], [0x80], [0xf0, 0x9f]]) {
    const parts = prefix.split('REPLACE'); refuse(Buffer.concat([Buffer.from(parts[0]), Buffer.from(bytes), Buffer.from(parts[1])]));
  }
  for (const raw of [page() + "x", page().slice(0, -1), page({}, { unknown: JSON.parse("[".repeat(34) + "0" + "]".repeat(34)) })]) refuse(raw);
});

test("all256 raw byte classes and word/chunk boundaries retain strict string grammar", () => {
  const text = page().replace('"VALUE_SENTINEL"', '"A~Z"'); const at = Buffer.from(text).indexOf(126);
  for (let byte = 0; byte < 256; byte++) {
    const raw = Buffer.from(text); raw[at] = byte;
    for (const split of [at - 1, at, at + 1, at + 2]) {
      const run = () => parseSecretSummaryPage([raw.subarray(0, split), raw.subarray(split)], "apps", 200);
      if (byte >= 32 && byte < 128 && byte !== 34 && byte !== 92) assert.deepEqual(run().items[0].keys, ["public"]);
      else assert.throws(run);
    }
  }
});

test("escaped schema member names work; ambiguous/schema/cursor/item/byte/chunk limits fail closed", () => {
  assert.deepEqual(parse(page({}).replace('"data"', '"d\\u0061ta"')).items[0].keys, []);
  const raw = page();
  for (const text of [raw.replace('"kind":"SecretList"', '"kind":"SecretList","kind":"SecretList"'), raw.replace('"data":', '"data":{},"data":'),
    raw.replace('"apiVersion":"v1"', '"apiVersion":"v2"'), raw.replace('"kind":"Secret"', '"kind":"Other"'), raw.replace('"namespace":"apps"', '"namespace":"other"'),
    raw.replace('"name":"public"', '"name":"invalid_name"'), page(null), page([]), page({ k: 1 }), page({}, { immutable: "true" }), page({}, { type: [] }), page({}, { metadata: "private" }),
    raw.replace('"continue":"public-cursor"', '"continue":1'), raw.replace('"continue":"public-cursor"', '"continue":"' + "a".repeat(8193) + '"'),
    '{"kind":"SecretList","apiVersion":"v1"}', raw.replace('"items":[', '"items":{')]) refuse(text);
  assert.throws(() => parseSecretSummaryPage([Buffer.alloc(4 * 1024 * 1024 + 1)], "apps", 200));
  assert.throws(() => parseSecretSummaryPage(Array.from({ length: 16385 }, () => Buffer.alloc(0)), "apps", 200));
  assert.throws(() => parseSecretSummaryPage([Buffer.from(raw)], "apps", 0));
  const two = JSON.parse(raw); two.items.push(two.items[0]); assert.throws(() => parseSecretSummaryPage([Buffer.from(JSON.stringify(two))], "apps", 1));
  assert.deepEqual(parse('{"items":[],"unknown":{"values":[true,false,null,-0,1e+2]},"kind":"SecretList","apiVersion":"v1"}'), { items: [], cursor: "" });
});
