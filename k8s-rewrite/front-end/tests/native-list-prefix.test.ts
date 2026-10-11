import { test } from "node:test";
import assert from "node:assert/strict";
import { rejectedSecretListItemCount } from "../src/lib/secret-client";

const header = '{"apiVersion":"v1","kind":"SecretList","metadata":{"continue":"public-cursor"},"items":[';
const hint = (text: string, limit = 200) => rejectedSecretListItemCount([Buffer.from(text)], limit);

test("rejected-prefix hints count only completed top-level objects across every byte boundary", () => {
  const item = '{"data":{"public":"quoted \\\" ],{ \\u1234 \\n \\\\"},"metadata":{"name":"multibyte-雪😀"},"nested":[true,false,null,-1.25e+2,{"items":[{},{}]}]}';
  const raw = Buffer.from(header + item + "," + item + ',{"data":{"unfinished":"public');
  for (let split = 0; split <= raw.length; split++) assert.equal(rejectedSecretListItemCount([raw.subarray(0, split), Buffer.alloc(0), raw.subarray(split)], 200), 2, `split ${split}`);
  assert.equal(rejectedSecretListItemCount(Array.from(raw, (_, index) => raw.subarray(index, index + 1)), 200), 2);
  assert.equal(hint(header + '{"a":1,"a":2},{"unfinished":'), 1, "nested names are grammar-checked, not compared for uniqueness");
});

test("ambiguous headers closed arrays incomplete first items and malformed prefixes have no hint", () => {
  const refused = [
    header, header + "{}]", header + "{},]", header + "{}{}", header + '{"first":',
    header + '{"a":01},{', header + '{"a":1e},{', header + '{"a":truefalse},{',
    header + '{"a":"\\x"},{', header + '{"a":"\\u00zz"},{', header + '{"a":"\u0001"},{',
    header + '{"a":1,},{', header + '{"a":[1,]},{', header + '{"a" 1},{',
    header.replace('"kind":"SecretList",', '"kind":"SecretList","kind":"SecretList",') + "{},{",
    header.replace('"apiVersion":"v1",', '"apiVersion":"v1","apiVersion":"v1",') + "{},{",
    header.replace('"metadata":', '"unknown":') + "{},{",
    header.replace('"kind"', '"k\\u0069nd"') + "{},{",
    header.replace('"SecretList"', '"OtherList"') + "{},{",
    '{"items":[{},{', '{"apiVersion":"v1","items":[{},{',
    header + '{"a":' + "[".repeat(33) + "0" + "]".repeat(33) + "},{",
  ];
  for (const raw of refused) assert.equal(hint(raw), undefined);
  for (const bytes of [[0xc0, 0x80], [0xe0, 0x80, 0x80], [0xed, 0xa0, 0x80], [0xf4, 0x90, 0x80, 0x80], [0x80]]) {
    assert.equal(rejectedSecretListItemCount([Buffer.from(header + '{} ,{"a":"'), Buffer.from(bytes)], 200), undefined);
  }
  assert.equal(hint(header + '{} ,{"a":"\\'), 1, "a valid unfinished escape does not accept the second item");
});

test("hint work is bounded and never concatenates decodes parses or retains native objects", () => {
  const raw = Buffer.from(header + '{"data":{"public":"' + "x".repeat(2 * 1024 * 1024) + '"}},{"unfinished":"');
  const concat = Buffer.concat, decode = TextDecoder.prototype.decode, parse = JSON.parse;
  Buffer.concat = () => assert.fail("Rejected hint must not concatenate bytes");
  TextDecoder.prototype.decode = () => assert.fail("Rejected hint must not decode native bytes");
  JSON.parse = () => assert.fail("Rejected hint must not materialize native objects");
  try {
    assert.equal(rejectedSecretListItemCount([raw.subarray(0, 1), raw.subarray(1)], 200), 1);
    assert.equal(rejectedSecretListItemCount([Buffer.alloc(4 * 1024 * 1024 + 1)], 200), undefined);
    assert.equal(rejectedSecretListItemCount(Array(16385).fill(Buffer.alloc(0)), 200), undefined);
    for (const limit of [0, -1, 201, NaN, 1.1]) assert.equal(rejectedSecretListItemCount([raw], limit), undefined);
    assert.equal(hint(header + '{},{},{', 1), undefined);
  } finally { Buffer.concat = concat; TextDecoder.prototype.decode = decode; JSON.parse = parse; }
});
