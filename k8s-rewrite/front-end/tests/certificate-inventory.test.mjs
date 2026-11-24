import { test } from "node:test";
import assert from "node:assert/strict";
import { certificateInventory, certificateRow, certificateRequestRow } from "../src/lib/certificate-inventory.ts";

const now = Date.parse("2026-11-16T12:00:00Z");
const certificate = () => ({
  metadata: { uid: "certificate-1", name: "ingress", namespace: "whoami" },
  spec: { dnsNames: ["whoami.branconet.lan"], issuerRef: { kind: "ClusterIssuer", name: "local-ca" } },
  status: { notAfter: "2027-01-16T12:00:00Z", renewalTime: "2027-01-01T12:00:00Z", conditions: [{ type: "Ready", status: "True" }] },
});
const csr = () => ({
  metadata: { uid: "csr-1", name: "csr-node01", creationTimestamp: "2026-11-16T12:00:00Z" },
  spec: { username: "system:node:node01", signerName: "kubernetes.io/kubelet-serving", request: "synthetic-request-never-returned" },
});

test("certificate health respects cert-manager renewal schedule, readiness and expiry", () => {
  const value = certificate();
  assert.equal(certificateRow(value, now).health, "healthy");
  value.status.renewalTime = "2026-11-15T00:00:00Z";
  assert.equal(certificateRow(value, now).health, "warning");
  value.status.conditions.push({ type: "Issuing", status: "True" });
  assert.equal(certificateRow(value, now).health, "renewing");
  value.status.notAfter = "2026-11-15T00:00:00Z";
  assert.equal(certificateRow(value, now).health, "expired");
  value.status.notAfter = "malformed";
  value.status.conditions = [];
  assert.equal(certificateRow(value, now).health, "unknown");
});

test("CSR lifecycle never conflates approval, issuance and installed verification", () => {
  const value = csr();
  assert.equal(certificateRequestRow(value).state, "pending");
  value.status = { conditions: [{ type: "Approved", status: "True" }] };
  assert.equal(certificateRequestRow(value).state, "approved");
  value.status.certificate = "synthetic-public-certificate";
  const issued = certificateRequestRow(value);
  assert.equal(issued.state, "issued");
  assert.match(issued.message, /installation.*not established/);
  value.status.conditions.push({ type: "Denied", status: "True" });
  assert.equal(certificateRequestRow(value).state, "denied");
  const body = JSON.stringify(issued);
  assert.ok(!body.includes("synthetic-public-certificate"));
  assert.ok(!body.includes("synthetic-request-never-returned"));
});

test("unavailable and malformed sources stay unknown while independent sources remain usable", async () => {
  const report = await certificateInventory(async args => {
    if (args[1].startsWith("certificatesigningrequests")) throw Error("private raw backend details");
    return { items: [certificate()] };
  }, now);
  assert.equal(report.certificates.length, 1);
  assert.equal(report.requests.length, 0);
  assert.equal(report.sources[1].available, false);
  assert.match(report.warnings.join(" "), /Coverage is unknown/);
  assert.ok(!JSON.stringify(report).includes("private raw backend"));
  assert.equal(report.automation.mode, "unavailable");
  assert.match(report.warnings.join(" "), /Consumers have not been mapped/);
});

test("pagination and response-shape failures cannot turn partial coverage into healthy inventory", async () => {
  for (const value of [{ items: null }, { items: [null] }, { items: [certificate()], metadata: { continue: "next" } },
    { items: [certificate()], metadata: { remainingItemCount: 5 } }, { items: [{ metadata: {} }] }]) {
    const report = await certificateInventory(async () => value, now);
    assert.equal(report.sources[0].available, false);
    assert.equal(report.certificates.length, 0);
  }
});

test("complete empty inventory is distinct from unavailable inventory and uses fixed read-only resources", async () => {
  const calls = [];
  const report = await certificateInventory(async args => { calls.push(args); return { items: [] }; }, now);
  assert.deepEqual(calls, [
    ["get", "certificates.cert-manager.io", "-A"],
    ["get", "certificatesigningrequests.certificates.k8s.io"],
  ]);
  assert.ok(report.sources.every(source => source.available));
  assert.equal(report.sampledAt, "2026-11-16T12:00:00.000Z");
  assert.equal(report.certificates.length, 0);
});

test("Kubernetes typed null-items empty lists stay available without accepting malformed untyped data", async () => {
  const report = await certificateInventory(async args => ({
    kind: args[1].startsWith("certificatesigningrequests") ? "CertificateSigningRequestList" : "CertificateList",
    items: null,
  }), now);
  assert.ok(report.sources.every(source => source.available));
  assert.deepEqual(report.certificates, []);
  assert.deepEqual(report.requests, []);
});
