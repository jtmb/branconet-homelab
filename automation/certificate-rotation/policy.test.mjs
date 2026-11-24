import test from "node:test"
import assert from "node:assert/strict"
import { decide, REQUESTED } from "./policy.mjs"

const NOW = 1794868800
const OLD = "a".repeat(64), NEW = "b".repeat(64)
function fixture(mode = "auto") {
  return {
    enrollment: { mode, certificateUID: "cert", secretUID: "secret", deploymentUID: "deployment" },
    facts: {
      certificate: { uid: "cert", resourceVersion: "7", ready: true, generation: 2, observedGeneration: 2, revision: 2 },
      secret: { uid: "secret", resourceVersion: "8" },
      deployment: { uid: "deployment", resourceVersion: "9", replicas: 1, strategy: "Recreate",
        paused: false, templateAnnotations: { "unrelated.example/owner": "preserve" } },
      issued: { ownerUID: "cert", revision: 2, ready: true, cryptographicallyVerified: true,
        fingerprint: NEW, notBefore: NOW - 30, notAfter: NOW + 3600 },
      projected: { fingerprint: NEW }, served: { trusted: true, fingerprint: OLD },
    },
  }
}

test("new issued/projected leaf requests only guarded annotation rollout, preserving unrelated data", () => {
  const { enrollment, facts } = fixture()
  const result = decide(enrollment, facts, NOW)
  assert.equal(result.state, "request_rollout")
  assert.deepEqual(result.patch, [
    { op: "test", path: "/metadata/uid", value: "deployment" },
    { op: "test", path: "/metadata/resourceVersion", value: "9" },
    { op: "add", path: "/spec/template/metadata/annotations",
      value: { "unrelated.example/owner": "preserve", [REQUESTED]: NEW } },
  ])
  assert.equal(result.binding.secretRV, "8")
  assert.equal(facts.deployment.templateAnnotations[REQUESTED], undefined)
})

test("observation mode never emits a mutation", () => {
  const { enrollment, facts } = fixture("observe")
  const result = decide(enrollment, facts, NOW)
  assert.equal(result.state, "observing")
  assert.equal(result.patch, null)
})

test("recreated enrolled objects require attention instead of inheriting authority", () => {
  for (const [key, reason] of [["certificate", "certificate_recreated"],
                             ["secret", "secret_recreated"], ["deployment", "deployment_recreated"]]) {
    const { enrollment, facts } = fixture()
    facts[key].uid = "replacement"
    assert.deepEqual(decide(enrollment, facts, NOW), { state: "attention", reason, patch: null })
  }
})

test("unissued, unverified, wrong-owner or stale-generation facts cannot roll a workload", () => {
  const changes = [
    f => { f.certificate.ready = false },
    f => { f.certificate.observedGeneration = 1 },
    f => { f.issued.cryptographicallyVerified = false },
    f => { f.issued.ownerUID = "other" },
    f => { f.issued.revision = 1 },
    f => { f.issued.fingerprint = "invalid" },
    f => { f.secret.resourceVersion = undefined },
  ]
  for (const change of changes) {
    const { enrollment, facts } = fixture()
    change(facts)
    assert.equal(decide(enrollment, facts, NOW).patch, null)
  }
})

test("projection delay is waiting, not installation success or permission to restart", () => {
  const { enrollment, facts } = fixture()
  facts.projected.fingerprint = OLD
  assert.equal(decide(enrollment, facts, NOW).reason, "projection_pending")
  assert.equal(decide(enrollment, facts, NOW).patch, null)
})

test("endpoint trust gaps never cause blind restarts or success", () => {
  for (const served of [null, { trusted: false, fingerprint: OLD }, { trusted: true, fingerprint: "bad" }]) {
    const { enrollment, facts } = fixture()
    facts.served = served
    assert.equal(decide(enrollment, facts, NOW).state, "attention")
    assert.equal(decide(enrollment, facts, NOW).patch, null)
  }
})

test("retry after uncertain patch does not repeat an already requested rollout", () => {
  const { enrollment, facts } = fixture()
  facts.deployment.templateAnnotations[REQUESTED] = NEW
  const result = decide(enrollment, facts, NOW)
  assert.equal(result.reason, "requested_rollout_not_yet_verified")
  assert.equal(result.patch, null)
  facts.served.fingerprint = NEW
  assert.equal(decide(enrollment, facts, NOW).state, "verified")
})

test("future/expired/near-expiry leaves and paused/non-single-writer workloads are refused", () => {
  const changes = [
    f => { f.issued.notBefore = NOW + 10 },
    f => { f.issued.notAfter = NOW + 60 },
    f => { f.deployment.paused = true },
    f => { f.deployment.replicas = 2 },
    f => { f.deployment.strategy = "RollingUpdate" },
  ]
  for (const change of changes) {
    const { enrollment, facts } = fixture()
    change(facts)
    assert.equal(decide(enrollment, facts, NOW).state, "attention")
    assert.equal(decide(enrollment, facts, NOW).patch, null)
  }
})
