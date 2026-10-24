import test from "node:test";
import assert from "node:assert/strict";
import { dataChange, nativeAdopt, nativeReconcile, nativeRollback, nativeDelete, nativeDestroy } from "../src/lib/kv-schemas";
const cases = [[dataChange, { fields: [] }], [nativeAdopt, { legacyAliases: [] }], [nativeReconcile, {}], [nativeRollback, { version: 1 }], [nativeDelete, { confirmPath: "services/api" }], [nativeDestroy, { confirmPath: "services/api", versions: [1] }]] as const;
test("native request contracts accept captured positive path revision while preserving older head/RV bodies", () => {
  for (const [schema, payload] of cases) {
    const oldBody = { ...payload, resourceVersion: "native-rv", expectedHead: 1 };
    assert(schema.safeParse(oldBody).success);
    assert(schema.safeParse({ ...oldBody, pathRevision: 2 }).success);
    assert(!schema.safeParse({ ...oldBody, pathRevision: 2, unexpectedPrivateField: "synthetic-marker" }).success);
  }
});
test("native request contracts reject invalid revision spelling before native work", () => {
  for (const [schema, payload] of cases) for (const pathRevision of [0, -1, 1.5, "2", null, Number.MAX_SAFE_INTEGER + 1])
    assert(!schema.safeParse({ ...payload, resourceVersion: "native-rv", expectedHead: 1, pathRevision }).success);
});
