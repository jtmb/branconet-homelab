import test from "node:test";
import assert from "node:assert/strict";
import { nativeAsciiValueSpan } from "../src/lib/secret-ascii-span";
import { parseSecretSummaryPage } from "../src/lib/secret-summary-json";
import { rejectedSecretListItemCount } from "../src/lib/secret-client";

const prefix = '{"apiVersion":"v1","kind":"SecretList","items":[';
const itemStart = '{"apiVersion":"v1","kind":"Secret","metadata":{"namespace":"apps","name":"public","uid":"public-uid","resourceVersion":"public-rv"},"data":{"__proto__":"';
const suffix = '"},"unknown":{"nested":["' + "Z".repeat(5000) + '"]}}';
const cuts = (raw: Buffer, at: number) => [
  [raw], [raw.subarray(0, at), Buffer.alloc(0), raw.subarray(at)],
  [raw.subarray(0, at + 1), raw.subarray(at + 1)],
  Array.from({ length: Math.ceil(raw.length / 4096) }, (_, i) => raw.subarray(i * 4096, (i + 1) * 4096)),
];

test("native spans never cross quote escape control high-byte or bounded-window boundaries", () => {
  for (const size of [4095, 4096, 4097, 8192]) {
    assert.equal(nativeAsciiValueSpan(Buffer.alloc(size, 65), 0), size < 4096 ? 0 : 4096);
  }
  for (const boundary of [255, 256, 4095, 4096]) {
    for (const byte of [34, 92]) {
      const raw = Buffer.alloc(8192, 65); raw[boundary] = byte;
      assert.equal(nativeAsciiValueSpan(raw, 0), boundary < 256 ? 0 : Math.min(boundary, 4096));
    }
    for (const byte of [...Array.from({ length: 32 }, (_, i) => i), ...Array.from({ length: 128 }, (_, i) => i + 128)]) {
      const raw = Buffer.alloc(8192, 65); raw[boundary] = byte;
      assert.equal(nativeAsciiValueSpan(raw, 0), boundary < 4096 ? 0 : 4096);
    }
  }
  const raw = Buffer.alloc(8192, 127);
  assert.equal(nativeAsciiValueSpan(raw, 0), 4096, "DEL is legal unescaped JSON ASCII");
  assert.equal(nativeAsciiValueSpan(raw, 4097), 0, "eligibility uses remaining bytes");
});

test("long native and unknown values keep complete byte grammar and exact prototype key metadata", () => {
  const before = Buffer.from(prefix + itemStart + "A".repeat(8192));
  for (const value of [Buffer.from("ASCII"), Buffer.from("雪😀"), Buffer.from('\\uD800\\n\\\"\\\\'), Buffer.from([127])]) {
    const raw = Buffer.concat([before, value, Buffer.from(suffix + "]}")]);
    for (const chunks of cuts(raw, before.length)) {
      const result = parseSecretSummaryPage(chunks, "apps", 200);
      assert.deepEqual(result.items[0].keys, ["__proto__"]);
      assert.equal(result.items[0].metadata.resourceVersion, "public-rv");
      assert.equal(Object.hasOwn(result.items[0], "data"), false);
    }
    const unfinished = Buffer.concat([before, value, Buffer.from(suffix + ',{"unfinished":"')]);
    for (const chunks of cuts(unfinished, before.length)) assert.equal(rejectedSecretListItemCount(chunks, 200), 1);
  }
  for (const bytes of [...Array.from({ length: 32 }, (_, i) => [i]), [0x80], [0xc0, 0x80], [0xe0, 0x80, 0x80], [0xed, 0xa0, 0x80], [0xf4, 0x90, 0x80, 0x80], [0xf0, 0x9f], [92, 120], [92, 117, 48, 48, 103, 103]]) {
    for (const padding of [4095, 4096, 8192]) {
      const head = Buffer.from(prefix + itemStart + "A".repeat(padding));
      const raw = Buffer.concat([head, Buffer.from(bytes), Buffer.from(suffix + "]}")]);
      for (const chunks of cuts(raw, head.length)) {
        assert.throws(() => parseSecretSummaryPage(chunks, "apps", 200), error => {
          assert.equal((error as Error).message, "Invalid Kubernetes Secret summary response"); return true;
        });
        assert.equal(rejectedSecretListItemCount(chunks, 200), undefined);
      }
    }
  }
});

test("long valid incomplete prefixes retain only completed count and never decode or materialize", () => {
  const complete = prefix + itemStart + "A".repeat(8192) + suffix + ",";
  const concat = Buffer.concat, parse = JSON.parse, decode = TextDecoder.prototype.decode, text = Buffer.prototype.toString;
  const inputs = ["", '"', '"' + "B".repeat(8192), '"' + "B".repeat(8192) + "\\", '"' + "B".repeat(8192) + "\\u00"]
    .map(value => Buffer.from(complete + '{"unfinished":' + value));
  Buffer.concat = () => assert.fail("prefix concatenation");
  JSON.parse = () => assert.fail("prefix JSON materialization");
  TextDecoder.prototype.decode = () => assert.fail("prefix decoding");
  Buffer.prototype.toString = () => assert.fail("prefix string materialization");
  try {
    for (const raw of inputs) for (const chunks of cuts(raw, complete.length + 10)) assert.equal(rejectedSecretListItemCount(chunks, 200), 1);
  } finally { Buffer.concat = concat; JSON.parse = parse; TextDecoder.prototype.decode = decode; Buffer.prototype.toString = text; }
});
