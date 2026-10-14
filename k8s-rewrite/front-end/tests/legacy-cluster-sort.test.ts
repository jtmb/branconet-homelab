import { test } from "node:test";
import assert from "node:assert/strict";
import { sortLegacyClusterRows } from "../src/lib/legacy-cluster-sort";

const rows = Object.freeze([
  Object.freeze({ name: "twelve", namespace: "apps", restarts: 12 }),
  Object.freeze({ name: "two", namespace: "apps", restarts: 2 }),
  Object.freeze({ name: "missing", namespace: "apps", restarts: null }),
  Object.freeze({ name: "seven", namespace: "apps", restarts: 7 }),
  Object.freeze({ name: "zero", namespace: "apps", restarts: 0 }),
]);
const names = (values: readonly { name: string }[]) => values.map(row => row.name);

test("legacy Pod restarts retain numeric zero and null-last in both directions without changing rows", () => {
  const asc = sortLegacyClusterRows(rows, "pods", "restarts", "asc"), desc = sortLegacyClusterRows(rows, "pods", "restarts", "desc");
  assert.deepEqual(names(asc), ["zero", "two", "seven", "twelve", "missing"]);
  assert.deepEqual(names(desc), ["twelve", "seven", "two", "zero", "missing"]);
  assert.notEqual(asc, rows); assert.deepEqual(names(rows), ["twelve", "two", "missing", "seven", "zero"]);
  for (const row of asc) assert.equal(row, rows.find(original => original.name === row.name));
});

test("legacy Pod and Deployment Ready compare both count components and keep identity ties ascending", () => {
  const input = [{ name: "b", namespace: "apps", ready: "2/12" }, { name: "a", namespace: "apps", ready: "2/12" },
    { name: "wide", namespace: "apps", ready: "2/20" }, { name: "zero", namespace: "apps", ready: "0/12" },
    { name: "seven", namespace: "apps", ready: "7/12" }, { name: "twelve", namespace: "apps", ready: "12/12" }, { name: "missing", namespace: "apps", ready: "unknown" }];
  for (const resource of ["pods", "deployments"] as const) {
    assert.deepEqual(names(sortLegacyClusterRows(input, resource, "ready", "asc")), ["zero", "a", "b", "wide", "seven", "twelve", "missing"]);
    assert.deepEqual(names(sortLegacyClusterRows(input, resource, "ready", "desc")), ["twelve", "seven", "wide", "a", "b", "zero", "missing"]);
  }
});

test("legacy Deployment numeric wire fields sort actual 0,2,7,12 and missing values", () => {
  for (const key of ["upToDate", "available", "restarts"]) {
    const input = rows.map(row => ({ name: row.name, namespace: row.namespace, [key]: row.restarts }));
    assert.deepEqual(names(sortLegacyClusterRows(input, "deployments", key, "asc")), ["zero", "two", "seven", "twelve", "missing"]);
    assert.deepEqual(names(sortLegacyClusterRows(input, "deployments", key, "desc")), ["twelve", "seven", "two", "zero", "missing"]);
  }
});

test("legacy RAM reads the rendered memory field rather than an absent mem property", () => {
  const input = rows.map(row => ({ name: row.name, hostname: row.name, memory: row.restarts, mem: 99, cpu: row.restarts, pods: row.restarts }));
  for (const key of ["mem", "cpu", "pods"]) {
    assert.deepEqual(names(sortLegacyClusterRows(input, "nodes", key, "asc")), ["zero", "two", "seven", "twelve", "missing"]);
    assert.deepEqual(names(sortLegacyClusterRows(input, "nodes", key, "desc")), ["twelve", "seven", "two", "zero", "missing"]);
  }
});

test("legacy storage compares binary quantities, decimals and unknowns without rewriting displayed values", () => {
  const input = [{ name: "twelve", capacity: "12Gi" }, { name: "two", capacity: "2048Mi" }, { name: "seven", capacity: "7Gi" },
    { name: "zero", capacity: "0" }, { name: "half", capacity: "0.5Gi" }, { name: "missing", capacity: "unknown" }];
  assert.deepEqual(names(sortLegacyClusterRows(input, "storage", "capacity", "asc")), ["zero", "half", "two", "seven", "twelve", "missing"]);
  assert.deepEqual(names(sortLegacyClusterRows(input, "storage", "capacity", "desc")), ["twelve", "seven", "two", "half", "zero", "missing"]);
  assert.equal(input[1].capacity, "2048Mi");
});

test("legacy Deployment Age uses exact created timestamps despite equal coarse age labels", () => {
  const input = [{ name: "late", created: "2020-12-31T00:00:00Z", age: "5y" }, { name: "early", created: "2020-01-01T00:00:00Z", age: "5y" },
    { name: "b", created: "2020-06-01T00:00:00Z", age: "5y" }, { name: "a", created: "2020-06-01T00:00:00Z", age: "5y" }, { name: "missing", created: null, age: "-" }];
  assert.deepEqual(names(sortLegacyClusterRows(input, "deployments", "age", "asc")), ["early", "a", "b", "late", "missing"]);
  assert.deepEqual(names(sortLegacyClusterRows(input, "deployments", "age", "desc")), ["late", "a", "b", "early", "missing"]);
});

test("legacy elapsed-age fields compare units and refuse unknown ages as missing", () => {
  const input = [{ name: "day", age: "1d" }, { name: "hours", age: "12h" }, { name: "minutes", age: "7m" }, { name: "zero", age: "0s" }, { name: "missing", age: "-" }];
  for (const resource of ["nodes", "ingresses"] as const) {
    assert.deepEqual(names(sortLegacyClusterRows(input, resource, "age", "asc")), ["zero", "minutes", "hours", "day", "missing"]);
    assert.deepEqual(names(sortLegacyClusterRows(input, resource, "age", "desc")), ["day", "hours", "minutes", "zero", "missing"]);
  }
});

test("legacy text and equal-value sorts retain deterministic name/namespace identity ties", () => {
  const input = [{ name: "same", namespace: "z", status: "Running" }, { name: "same", namespace: "a", status: "Running" }, { name: "alpha", namespace: "apps", status: "Running" }];
  for (const resource of ["pods", "services", "namespaces", "storageClasses"] as const) {
    for (const direction of ["asc", "desc"] as const) assert.deepEqual(sortLegacyClusterRows(input, resource, "status", direction), [input[2], input[1], input[0]]);
  }
  const nodes = [{ hostname: "z", cpu: 2 }, { hostname: "a", cpu: 2 }];
  assert.deepEqual(sortLegacyClusterRows(nodes, "nodes", "cpu", "desc"), [nodes[1], nodes[0]]);
});
