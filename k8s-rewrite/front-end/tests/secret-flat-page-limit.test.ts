import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createFlatSummaryParser, createNativeSelectorLoader } from "../src/lib/secret-flat-summary";
import { parseSecretSummaryPage, parsePortableFlatSecretSummaryPage } from "../src/lib/secret-summary-json";
import { SecretError } from "../src/lib/cluster-secrets";

const fixed = (e: unknown) => e instanceof SecretError && e.status === 503 && e.message === "Invalid Kubernetes Secret summary response";
const small = Buffer.from('{"apiVersion":"v1","kind":"SecretList","metadata":{"continue":"cursor"},"items":[{"apiVersion":"v1","kind":"Secret","metadata":{"namespace":"apps","name":"public","uid":"uid","resourceVersion":"rv","unknown":{"nested":"PRIVATE_METADATA"}},"type":"Opaque","data":{"__proto__":"PRIVATE_NATIVE_VALUE","":"","snow-雪":"AA=="}}],"unknown":""}');
const portable = createFlatSummaryParser();
const addon = createNativeSelectorLoader(path.join(process.cwd(), "native/secret-flat-selector.node"))();
// Linux CI builds the actual selector before tests; unsupported developer
// platforms retain the documented absence-only portable path.
if (process.platform === "linux" && process.arch === "x64") assert.ok(addon, "Actual Linux native selector required");
const native = createFlatSummaryParser(addon);
function sized(bytes: number): Buffer {
  const value = small.toString().replace('"unknown":""}', '"unknown":"' + "A".repeat(bytes - small.length) + '"}');
  const raw = Buffer.from(value); assert.equal(raw.length, bytes); return raw;
}

test("flat native and portable pages permit16MiB while the unchanged generic entry retains4MiB", () => {
  const expected = portable([small], "apps", 200);
  for (const bytes of [4 * 1024 * 1024, 4 * 1024 * 1024 + 1, 16 * 1024 * 1024]) {
    const raw = sized(bytes), at = raw.length - 7;
    const chunks = [raw.subarray(0, 13), Buffer.alloc(0), raw.subarray(13, at), raw.subarray(at)];
    assert.deepEqual(portable(chunks, "apps", 200), expected);
    assert.deepEqual(native(chunks, "apps", 200), expected);
    if (bytes > 4 * 1024 * 1024) assert.throws(() => parseSecretSummaryPage(chunks, "apps", 200), fixed);
    else assert.equal(parseSecretSummaryPage(chunks, "apps", 200).items.length, 1);
  }
  const oversized = sized(16 * 1024 * 1024 + 1);
  for (const parser of [portable, native, parsePortableFlatSecretSummaryPage]) assert.throws(() => parser([oversized], "apps", 200), fixed);
});

test("flat16 parity keeps full malformed UTF8/grammar and overwritten-depth refusals across splits", () => {
  const text = small.toString(), nested = (n: number) => "[".repeat(n) + "0" + "]".repeat(n);
  const cases: [Buffer, boolean][] = [
    [small, true],
    [Buffer.from(text.replace('"kind":"SecretList"', '"kind":"SecretList","k\\u0069nd":"SecretList"')), false],
    [Buffer.from(text.replace('"namespace":"apps"', '"namespace":"other"')), false],
    [Buffer.from(text.replace('"uid":"uid"', '"uid":7')), false],
    [Buffer.from(text.replace('"PRIVATE_NATIVE_VALUE"', '"\\uD800"')), true],
    [Buffer.from(text.replace('"PRIVATE_NATIVE_VALUE"', '"\\x"')), false],
    [Buffer.from(text.replace('"unknown":""}', '"unknown":[1,]}')), false],
    [Buffer.from(text.replace('"metadata":{"continue":"cursor"}', '"metadata":{"probe":' + nested(30) + ',"probe":0}')), true],
    [Buffer.from(text.replace('"metadata":{"continue":"cursor"}', '"metadata":{"probe":' + nested(31) + ',"probe":0}')), false],
  ];
  const marker = small.indexOf("PRIVATE_NATIVE_VALUE");
  cases.push([Buffer.concat([small.subarray(0, marker), Buffer.from([0xed, 0xa0, 0x80]), small.subarray(marker + 20)]), false]);
  for (const [raw, accepted] of cases) for (const split of [0, 1, Math.floor(raw.length / 2), raw.length - 1, raw.length]) {
    const chunks = [raw.subarray(0, split), Buffer.alloc(0), raw.subarray(split)];
    if (accepted) assert.deepEqual(native(chunks, "apps", 200), portable(chunks, "apps", 200));
    else for (const parser of [native, portable]) assert.throws(() => parser(chunks, "apps", 200), fixed);
  }
  for (const parser of [native, portable]) {
    assert.deepEqual(parser([...Array.from({ length: 16383 }, () => Buffer.alloc(0)), small], "apps", 200), portable([small], "apps", 200));
    assert.throws(() => parser([...Array.from({ length: 16384 }, () => Buffer.alloc(0)), small], "apps", 200), fixed);
    assert.throws(() => parser([small], "apps", 0), fixed);
    assert.throws(() => parser([small], "apps", 201), fixed);
    assert.deepEqual(parser([small], "apps", 200), portable([small], "apps", 200));
  }
});

test("portable16 never decodes or materializes skipped native/unknown values and always redacts projection", () => {
  const raw = Buffer.from('{"apiVersion":"v1","kind":"SecretList","metadata":{},"items":[{"apiVersion":"v1","kind":"Secret","metadata":{"namespace":"apps","name":"public","resourceVersion":"rv"},"data":{"payload":"PRIVATE_NATIVE_VALUE"},"stringData":{"payload":"PRIVATE_NATIVE_VALUE"},"unknown":{"nested":"PRIVATE_NATIVE_VALUE"}}],"unknown":"PRIVATE_NATIVE_VALUE"}');
  const decode = TextDecoder.prototype.decode, parse = JSON.parse, text = Buffer.prototype.toString;
  TextDecoder.prototype.decode = function (...args) { const value = Reflect.apply(decode, this, args); assert.equal(value.includes("PRIVATE_NATIVE_VALUE"), false); return value; };
  JSON.parse = function (value, ...args) { assert.equal(value.includes("PRIVATE_NATIVE_VALUE"), false); return Reflect.apply(parse, this, [value, ...args]); };
  Buffer.prototype.toString = function (...args: Parameters<Buffer["toString"]>) { const value = text.apply(this, args); assert.equal(value.includes("PRIVATE_NATIVE_VALUE"), false); return value; };
  try {
    for (const parser of [native, portable]) {
      const result = parser([raw.subarray(0, 40), raw.subarray(40)], "apps", 200);
      assert.equal(JSON.stringify(result).includes("PRIVATE_"), false);
      assert.deepEqual(result.items[0].keys, ["payload"]);
    }
  } finally { TextDecoder.prototype.decode = decode; JSON.parse = parse; Buffer.prototype.toString = text; }
});
