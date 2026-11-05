import test from "node:test";
import assert from "node:assert/strict";
import { parseSecretSummaryPage } from "../src/lib/secret-summary-json";

const metadata = '{"namespace":"apps","name":"public","uid":"public-uid","resourceVersion":"public-rv"}';
const item = '{"apiVersion":"v1","kind":"Secret","metadata":' + metadata + ',"data":{"__proto__":"VALUE_SENTINEL"},"stringData":{},"type":"Opaque","immutable":true}';
const page = (body = item, extra = "") => '{"apiVersion":"v1","kind":"SecretList","metadata":{},"items":[' + body + ']' + extra + '}';
const escaped = (key: string) => key[0] + "\\u" + key.charCodeAt(1).toString(16).padStart(4, "0") + key.slice(2);

test("known schema duplicates reject literal and escaped names at every chunk boundary", () => {
  const root = { apiVersion: '"v1"', kind: '"SecretList"', metadata: "{}", items: "[]" };
  const fields = { apiVersion: '"v1"', kind: '"Secret"', metadata, data: "{}", stringData: "{}", type: '"Opaque"', immutable: "false" };
  const cases: string[] = [];
  for (const [key, value] of Object.entries(root)) for (const name of [key, escaped(key)]) cases.push(page(item, ',"' + name + '":' + value));
  for (const [key, value] of Object.entries(fields)) for (const name of [key, escaped(key)]) cases.push(page(item.slice(0, -1) + ',"' + name + '":' + value + '}'));
  for (const text of cases) {
    const raw = Buffer.from(text);
    for (let cut = 0; cut <= raw.length; cut++) assert.throws(() => parseSecretSummaryPage([raw.subarray(0, cut), Buffer.alloc(0), raw.subarray(cut)], "apps", 200), error => {
      assert.equal((error as { status: number }).status, 503);
      assert.equal((error as Error).message, "Invalid Kubernetes Secret summary response");
      return true;
    });
  }
});

test("unknown duplicate and prototype-like names remain fully validated and discarded", () => {
  for (const key of ["__proto__", "constructor", "toString", "has", "add", "fields", "seen"]) {
    const unknown = ',"' + key + '":0,"' + key + '":{"private":"VALUE_SENTINEL"}';
    const raw = Buffer.from(page(item.slice(0, -1) + unknown + '}', unknown));
    const expected = { items: [{ metadata: JSON.parse(metadata), type: "Opaque", immutable: true, keys: ["__proto__"] }], cursor: "" };
    for (let cut = 0; cut <= raw.length; cut++) assert.deepEqual(parseSecretSummaryPage([raw.subarray(0, cut), raw.subarray(cut)], "apps", 200), expected);
    const bad = Buffer.from(page(item.slice(0, -1) + unknown + ',"' + key + '":[1,]}'));
    assert.throws(() => parseSecretSummaryPage([bad], "apps", 200), /Invalid Kubernetes Secret summary response/);
    assert.equal(JSON.stringify(expected).includes("VALUE_SENTINEL"), false);
    assert.equal(Object.hasOwn(Object.prototype, "private"), false);
  }
});
