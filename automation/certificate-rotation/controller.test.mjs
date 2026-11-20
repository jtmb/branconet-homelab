import test, { before, after } from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import { execFileSync } from "node:child_process"
import { createHash, X509Certificate } from "node:crypto"
import { collect, runOnce } from "./controller.mjs"
import { REQUESTED } from "./policy.mjs"

let dir, ca, cert, fingerprint
const hash = data => createHash("sha256").update(data).digest("hex")
before(() => {
  const root = process.env.BORTUS_ROTATION_TEST_TMP
  assert.ok(root?.startsWith("/mnt/h/AgentArtifacts/projects/branconet/"))
  dir = fs.mkdtempSync(path.join(root, "rotation-"))
  fs.chmodSync(dir, 0o700)
  const openssl = args => execFileSync("openssl", args, { stdio: "ignore", timeout: 10000 })
  const p = file => path.join(dir, file)
  openssl(["req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
    "-nodes", "-days", "1", "-subj", "/CN=rotation-test-ca",
    "-addext", "basicConstraints=critical,CA:TRUE", "-keyout", p("ca.key"), "-out", p("ca.pem")])
  openssl(["req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
    "-nodes", "-subj", "/CN=notifications.lan", "-keyout", p("leaf.key"), "-out", p("leaf.csr")])
  fs.writeFileSync(p("extensions"), "subjectAltName=DNS:notifications.lan\nbasicConstraints=critical,CA:FALSE\n" +
    "keyUsage=digitalSignature\nextendedKeyUsage=serverAuth\n")
  openssl(["x509", "-req", "-in", p("leaf.csr"), "-CA", p("ca.pem"), "-CAkey", p("ca.key"),
    "-CAcreateserial", "-days", "1", "-extfile", p("extensions"), "-out", p("leaf.pem")])
  ca = fs.readFileSync(p("ca.pem")); cert = fs.readFileSync(p("leaf.pem"))
  fingerprint = hash(new X509Certificate(cert).raw)
})
after(() => {
  if (!dir) return
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name), stat = fs.lstatSync(p)
    assert.ok(stat.isFile() && !stat.isSymbolicLink() && stat.nlink === 1)
    fs.unlinkSync(p)
  }
  fs.rmdirSync(dir)
})

function fixture() {
  const c = { mode: "auto", namespace: "bortus-notifications", certificateName: "ntfy",
    secretName: "ntfy-tls", deploymentName: "ntfy", certificateUID: "cert", secretUID: "secret",
    deploymentUID: "deploy", caFingerprint: hash(new X509Certificate(ca).raw),
    allowedDNS: ["notifications.lan"], serverName: "notifications.lan", endpointAddress: "192.168.0.252",
    expectedImage: "docker.io/jtmb92/bortus@sha256:" + "e".repeat(64) }
  const certObj = { metadata: { uid: "cert", resourceVersion: "1", generation: 2 },
    spec: { secretName: "ntfy-tls" },
    status: { revision: 2, conditions: [{ type: "Ready", status: "True", observedGeneration: 2 }] } }
  const secret = { kind: "PartialObjectMetadata", metadata: { uid: "secret", resourceVersion: "2" } }
  const deploy = { metadata: { uid: "deploy", resourceVersion: "3" },
    spec: { replicas: 1, strategy: { type: "Recreate" }, template: { metadata: { annotations: {} },
      spec: { volumes: [{ name: "tls", secret: { secretName: "ntfy-tls" } }],
        containers: [{ name: "ntfy", image: c.expectedImage }] } } } }
  const request = { metadata: { ownerReferences: [{ uid: "cert", kind: "Certificate" }],
    annotations: { "cert-manager.io/certificate-name": "ntfy", "cert-manager.io/certificate-revision": "2" } },
    status: { certificate: cert.toString("base64"), conditions: [{ type: "Ready", status: "True" }] } }
  const calls = []
  const io = {
    get: async p => {
      calls.push({ method: "GET", path: p })
      return structuredClone(p.includes("/certificaterequests/") ? request
        : p.includes("/deployments/") ? deploy : certObj)
    },
    metadata: async p => { calls.push({ method: "METADATA", path: p }); return structuredClone(secret) },
    publicCA: async () => ca, publicLeaf: async () => cert,
    served: async () => ({ trusted: true, fingerprint: "a".repeat(64) }),
    patch: async (p, ops) => { calls.push({ method: "PATCH", path: p, operations: ops }) },
  }
  return { c, io, calls, request, secret, deploy }
}

test("actual signed public leaf is bound to issued owner/revision and one exact CAS mutation", async () => {
  const { c, io, calls } = fixture()
  const facts = await collect(c, io)
  assert.equal(facts.issued.fingerprint, fingerprint)
  assert.equal(facts.issued.cryptographicallyVerified, true)
  const result = await runOnce(c, io)
  assert.equal(result.state, "requested")
  const patches = calls.filter(c => c.method === "PATCH")
  assert.equal(patches.length, 1)
  assert.equal(patches[0].operations[0].value, "deploy")
  assert.equal(patches[0].operations[2].value[REQUESTED], fingerprint)
})

test("full Secret fallback is rejected instead of handling/persisting private fields", async () => {
  const { c, io, secret, calls } = fixture()
  secret.kind = "Secret"; secret.data = { "tls.key": "SYNTHETIC-SENTINEL" }
  await assert.rejects(runOnce(c, io), /metadata_contract_failed/)
  assert.equal(calls.filter(c => c.method === "PATCH").length, 0)
})

test("wrong CA, owner, revision or DNS cannot create a rollout", async () => {
  for (const change of [
    f => { f.c.caFingerprint = "0".repeat(64) },
    f => { f.request.metadata.ownerReferences[0].uid = "other" },
    f => { f.request.metadata.annotations["cert-manager.io/certificate-revision"] = "1" },
    f => { f.c.serverName = "wrong.lan"; f.c.allowedDNS = ["wrong.lan"] },
    f => { f.deploy.spec.template.spec.containers[0].image = "unexpected" },
    f => { f.deploy.spec.template.spec.volumes[0].secret.secretName = "unrelated" },
  ]) {
    const f = fixture(); change(f)
    await assert.rejects(runOnce(f.c, f.io))
    assert.equal(f.calls.filter(c => c.method === "PATCH").length, 0)
  }
})

test("CA certificate cannot substitute for a signed serving leaf", async () => {
  const { c, io, request } = fixture()
  request.status.certificate = ca.toString("base64")
  await assert.rejects(runOnce(c, io), /issued_leaf_trust_failed/)
})

test("observation/verified states never patch; projected mismatches wait", async () => {
  const f = fixture(); f.c.mode = "observe"
  assert.equal((await runOnce(f.c, f.io)).state, "observing")
  f.c.mode = "auto"; f.io.served = async () => ({ trusted: true, fingerprint })
  assert.equal((await runOnce(f.c, f.io)).state, "verified")
  f.io.publicLeaf = async () => ca
  assert.equal((await runOnce(f.c, f.io)).reason, "projection_pending")
  assert.equal(f.calls.filter(c => c.method === "PATCH").length, 0)
})

test("Secret revision drift between collection and dispatch prevents patch", async () => {
  const { c, io, secret, calls } = fixture()
  let read = 0
  io.metadata = async () => ({ ...secret, metadata: { ...secret.metadata, resourceVersion: String(++read) } })
  assert.equal((await runOnce(c, io)).reason, "facts_changed_reconcile")
  assert.equal(calls.filter(c => c.method === "PATCH").length, 0)
})

test("ambiguous patch outcome is not repeated when durable annotation is observed next run", async () => {
  const { c, io, deploy } = fixture()
  let patches = 0
  io.patch = async () => {
    patches++
    deploy.spec.template.metadata.annotations[REQUESTED] = fingerprint
    throw new Error("synthetic_uncertain_response")
  }
  await assert.rejects(runOnce(c, io))
  assert.equal((await runOnce(c, io)).reason, "requested_rollout_not_yet_verified")
  assert.equal(patches, 1)
})
