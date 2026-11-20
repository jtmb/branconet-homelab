/**
 * One bounded observation/guarded rollout. No issuer/approval/host operations.
 * Mounted public leaf/CA only; native private key is never read.
 */
import fs from "node:fs/promises"
import https from "node:https"
import tls from "node:tls"
import { X509Certificate, createHash } from "node:crypto"
import { pathToFileURL } from "node:url"
import { isIP } from "node:net"
import { decide } from "./policy.mjs"

const name = /^[a-z0-9]([-a-z0-9.]*[a-z0-9])?$/
const hash = value => createHash("sha256").update(value).digest("hex")
const ready = value => value?.status?.conditions?.some(c => c.type === "Ready" && c.status === "True")
const leaf = value => new X509Certificate(value)
const error = reason => { throw new Error(reason) }

function checkConfig(c) {
  const address = typeof c.endpointAddress === "string" ? c.endpointAddress.split(".").map(Number) : []
  const privateAddress = isIP(c.endpointAddress ?? "") === 4 && (
    address[0] === 10 || address[0] === 127 || (address[0] === 172 && address[1] >= 16 && address[1] <= 31)
    || (address[0] === 192 && address[1] === 168))
  if (!["observe", "auto"].includes(c.mode)
      || ![c.namespace, c.certificateName, c.secretName, c.deploymentName].every(v => typeof v === "string" && name.test(v))
      || !/^[0-9a-f]{64}$/.test(c.caFingerprint)
      || !Array.isArray(c.allowedDNS) || c.allowedDNS.length < 1
      || !c.allowedDNS.every(v => typeof v === "string" && name.test(v) && !v.includes("*"))
      || !c.allowedDNS.includes(c.serverName)
      || !privateAddress
      || !/^docker\.io\/jtmb92\/bortus@sha256:[0-9a-f]{64}$/.test(c.expectedImage)) error("invalid_enrollment")
}

export async function collect(c, io) {
  checkConfig(c)
  const prefix = `/apis/cert-manager.io/v1/namespaces/${c.namespace}`
  const cert = await io.get(`${prefix}/certificates/${c.certificateName}`)
  if (cert.spec?.secretName !== c.secretName) error("certificate_consumer_changed")
  const secret = await io.metadata(`/api/v1/namespaces/${c.namespace}/secrets/${c.secretName}`)
  if (secret.kind !== "PartialObjectMetadata" || "data" in secret || "stringData" in secret) {
    error("metadata_contract_failed")
  }
  const deploy = await io.get(`/apis/apps/v1/namespaces/${c.namespace}/deployments/${c.deploymentName}`)
  const pod = deploy.spec?.template?.spec
  if (!pod?.volumes?.some(v => v.secret?.secretName === c.secretName)
      || pod.containers?.length !== 1 || pod.containers[0].image !== c.expectedImage) {
    error("deployment_consumer_changed")
  }
  if (!Number.isSafeInteger(cert.status?.revision) || cert.status.revision < 1) error("issued_leaf_unknown")
  // cert-manager uses annotations, not a certificate-name label, and names
  // requests <certificate>-<revision>. Fetch only that public object; no list.
  const request = await io.get(`${prefix}/certificaterequests/${c.certificateName}-${cert.status.revision}`)
  if (!request.metadata.ownerReferences?.some(o => o.uid === cert.metadata.uid && o.kind === "Certificate")
      || request.metadata.annotations?.["cert-manager.io/certificate-name"] !== c.certificateName
      || Number(request.metadata.annotations?.["cert-manager.io/certificate-revision"]) !== cert.status.revision
      || !ready(request) || !request.status?.certificate) error("issued_leaf_unknown")
  const issued = leaf(Buffer.from(request.status.certificate, "base64"))
  const ca = leaf(await io.publicCA())
  const projected = leaf(await io.publicLeaf())
  if (!ca.ca || issued.ca || hash(ca.raw) !== c.caFingerprint || !issued.verify(ca.publicKey)) {
    error("issued_leaf_trust_failed")
  }
  const sans = issued.subjectAltName?.split(", ").map(s => s.startsWith("DNS:") ? s.slice(4) : null)
  if (!sans?.length || sans.some(s => !s || !c.allowedDNS.includes(s))
      || !issued.checkHost(c.serverName, { subject: "never" })) error("issued_leaf_identity_failed")
  const endpoint = await io.served()
  return {
    certificate: { uid: cert.metadata.uid, resourceVersion: cert.metadata.resourceVersion,
      generation: cert.metadata.generation,
      observedGeneration: cert.status.conditions?.find(v => v.type === "Ready")?.observedGeneration,
      revision: cert.status.revision, ready: ready(cert) },
    secret: { uid: secret.metadata.uid, resourceVersion: secret.metadata.resourceVersion },
    deployment: { uid: deploy.metadata.uid, resourceVersion: deploy.metadata.resourceVersion,
      replicas: deploy.spec.replicas, strategy: deploy.spec.strategy?.type,
      paused: deploy.spec.paused === true,
      templateAnnotations: deploy.spec.template.metadata.annotations ?? {} },
    issued: { ownerUID: cert.metadata.uid, revision: cert.status.revision, ready: true,
      cryptographicallyVerified: true, fingerprint: hash(issued.raw),
      notBefore: Math.floor(Date.parse(issued.validFrom) / 1000),
      notAfter: Math.floor(Date.parse(issued.validTo) / 1000) },
    projected: { fingerprint: hash(projected.raw) },
    served: { trusted: endpoint.trusted === true, fingerprint: endpoint.fingerprint },
  }
}

export async function runOnce(c, io, nowSeconds = Math.floor(Date.now() / 1000)) {
  const first = await collect(c, io)
  const decision = decide(c, first, nowSeconds)
  if (!decision.patch) return decision
  const fresh = await collect(c, io)
  const current = decide(c, fresh, nowSeconds)
  if (current.state !== "request_rollout"
      || JSON.stringify(current.binding) !== JSON.stringify(decision.binding)
      || JSON.stringify(current.patch) !== JSON.stringify(decision.patch)) {
    return { state: "waiting", reason: "facts_changed_reconcile", patch: null }
  }
  // Exactly one request. An ambiguous HTTP failure is not retried here; the
  // next invocation observes the durable template annotation first.
  await io.patch(`/apis/apps/v1/namespaces/${c.namespace}/deployments/${c.deploymentName}`, current.patch)
  return { state: "requested", reason: "awaiting_served_fingerprint", fingerprint: current.fingerprint, patch: null }
}

export function transport(c, token, apiCA, servingCA) {
  async function api(path, method = "GET", body, metadata = false) {
    if (!path.startsWith(`/api/v1/namespaces/${c.namespace}/`)
        && !path.startsWith(`/apis/apps/v1/namespaces/${c.namespace}/`)
        && !path.startsWith(`/apis/cert-manager.io/v1/namespaces/${c.namespace}/`)) error("api_scope_violation")
    const rawBody = body ? JSON.stringify(body) : undefined
    return new Promise((resolve, reject) => {
      const req = https.request({ hostname: "192.168.0.4", port: 6443, path, method,
        ca: apiCA, minVersion: "TLSv1.2", agent: false, timeout: 3000,
        headers: { Authorization: "Bearer " + token,
          Accept: metadata ? "application/json;as=PartialObjectMetadata;g=meta.k8s.io;v=v1" : "application/json",
          ...(body ? { "Content-Type": "application/json-patch+json", "Content-Length": Buffer.byteLength(rawBody) } : {}) } },
      res => {
        const pieces = []; let bytes = 0
        res.on("data", chunk => {
          bytes += chunk.length
          if (bytes > 256 * 1024) req.destroy(new Error("api_response_limit"))
          else pieces.push(chunk)
        })
        res.on("end", () => {
          if (res.statusCode !== 200) return reject(new Error("api_failed"))
          try { resolve(JSON.parse(Buffer.concat(pieces))) } catch { reject(new Error("api_invalid_json")) }
        })
        res.on("error", () => reject(new Error("api_unavailable")))
      })
      req.on("timeout", () => req.destroy(new Error("api_timeout")))
      req.on("error", () => reject(new Error("api_unavailable")))
      req.end(rawBody)
    })
  }
  return {
    get: path => api(path), metadata: path => api(path, "GET", undefined, true),
    patch: (path, operations) => api(path, "PATCH", operations),
    publicCA: () => fs.readFile("/serving/ca.crt"),
    publicLeaf: () => fs.readFile("/serving/tls.crt"),
    served: () => new Promise((resolve, reject) => {
      const socket = tls.connect({ host: c.endpointAddress, port: 443, servername: c.serverName,
        ca: servingCA, minVersion: "TLSv1.2", rejectUnauthorized: true }, () => {
        const fingerprint = hash(socket.getPeerCertificate(true).raw)
        socket.end(); resolve({ trusted: true, fingerprint })
      })
      socket.setTimeout(3000, () => socket.destroy(new Error("endpoint_timeout")))
      socket.on("error", () => reject(new Error("endpoint_trust_unknown")))
    }),
  }
}

async function main() {
  const c = JSON.parse(await fs.readFile("/controller/enrollment.json", "utf8"))
  checkConfig(c)
  const token = (await fs.readFile("/var/run/rotation/token", "utf8")).trim()
  if (!/^[A-Za-z0-9_.-]{1,8192}$/.test(token)) error("token_invalid")
  const apiCA = await fs.readFile("/var/run/rotation/ca.crt")
  const servingCA = await fs.readFile("/serving/ca.crt")
  const result = await runOnce(c, transport(c, token, apiCA, servingCA))
  console.log(JSON.stringify(result))
}

// ConfigMap volumes use symlinks. Node resolves the main module's real path,
// while argv[1] may retain the projected path; do not silently skip the CLI.
const entry = process.argv[1]
const isMain = entry && (import.meta.url === pathToFileURL(entry).href
  || import.meta.url === pathToFileURL(await fs.realpath(entry)).href)
if (isMain) {
  main().catch(() => {
    // Never serialize exception text, backend documents, headers or file data.
    console.log(JSON.stringify({ state: "attention", reason: "observation_or_mutation_unknown" }))
    process.exitCode = 1
  })
}
