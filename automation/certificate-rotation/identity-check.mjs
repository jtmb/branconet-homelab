/** Qualification only: actual projected identity and denial matrix, no values logged. */
import fs from "node:fs/promises"
import https from "node:https"

async function main() {
  const c = JSON.parse(await fs.readFile("/controller/identity.json", "utf8"))
  const token = (await fs.readFile("/var/run/rotation/token", "utf8")).trim()
  const ca = await fs.readFile("/var/run/rotation/ca.crt")
  async function request(method, path, body, metadata = false) {
    const data = body ? JSON.stringify(body) : undefined
    return new Promise((resolve, reject) => {
      const req = https.request({ hostname: "192.168.0.4", port: 6443, path, method,
        ca, minVersion: "TLSv1.2", agent: false, timeout: 3000,
        headers: { Authorization: "Bearer " + token,
          Accept: metadata ? "application/json;as=PartialObjectMetadata;g=meta.k8s.io;v=v1" : "application/json",
          ...(body ? { "Content-Type": method === "PATCH" ? "application/merge-patch+json" : "application/json",
            "Content-Length": Buffer.byteLength(data) } : {}) } }, res => {
        const blocks = []; let bytes = 0
        res.on("data", b => { bytes += b.length; if (bytes > 128 * 1024) req.destroy(); else blocks.push(b) })
        res.on("end", () => {
          try { resolve({ status: res.statusCode, body: JSON.parse(Buffer.concat(blocks)) }) }
          catch { reject(new Error("invalid_response")) }
        })
        res.on("error", () => reject(new Error("transport_failed")))
      })
      req.on("error", () => reject(new Error("transport_failed")))
      req.on("timeout", () => req.destroy())
      req.end(data)
    })
  }
  const subject = await request("POST", "/apis/authentication.k8s.io/v1/selfsubjectreviews",
    { apiVersion: "authentication.k8s.io/v1", kind: "SelfSubjectReview", spec: {} })
  const info = subject.body.status?.userInfo
  if (subject.status !== 201 || info?.username !== `system:serviceaccount:${c.namespace}:${c.account}`
      || info?.uid !== c.serviceAccountUID) throw new Error("identity_mismatch")
  const certificateName = c.certificateName ?? "synthetic-leaf"
  const secretName = c.secretName ?? "synthetic-leaf"
  const cert = await request("GET", `/apis/cert-manager.io/v1/namespaces/${c.namespace}/certificates/${certificateName}`)
  const metadata = await request("GET", `/api/v1/namespaces/${c.namespace}/secrets/${secretName}`, undefined, true)
  if (cert.status !== 200 || metadata.status !== 200 || metadata.body.kind !== "PartialObjectMetadata"
      || "data" in metadata.body) throw new Error("allow_contract_failed")
  const positive = {}
  if (c.deploymentName) {
    if (cert.body.metadata.uid !== c.certificateUID || metadata.body.metadata.uid !== c.secretUID) {
      throw new Error("enrolled_objects_changed")
    }
    const target = `/apis/apps/v1/namespaces/${c.namespace}/deployments/${c.deploymentName}`
    const deploy = await request("GET", target)
    if (deploy.status !== 200 || deploy.body.metadata.uid !== c.deploymentUID || deploy.body.spec.replicas !== 0) {
      throw new Error("staged_deployment_changed")
    }
    // Effective PATCH authorization/admission, not a rollout: this is a
    // resourceVersion-bound metadata-only server dry run on the exact target.
    const dry = await request("PATCH", target + "?dryRun=All",
      { metadata: { resourceVersion: deploy.body.metadata.resourceVersion } })
    if (dry.status !== 200 || dry.body.metadata.uid !== c.deploymentUID || dry.body.spec.replicas !== 0) {
      throw new Error("staged_patch_dry_run_failed")
    }
    const revision = cert.body.status?.revision
    if (!Number.isSafeInteger(revision) || revision < 1) throw new Error("public_request_unknown")
    const issued = await request("GET",
      `/apis/cert-manager.io/v1/namespaces/${c.namespace}/certificaterequests/${certificateName}-${revision}`)
    if (issued.status !== 200 || !issued.body.metadata.ownerReferences?.some(o => o.uid === c.certificateUID)) {
      throw new Error("public_request_binding_failed")
    }
    positive.exactDeploymentGET = true
    positive.exactDeploymentPATCHServerDryRun = true
    positive.currentPublicRequestGET = true
  }
  const cases = [
    ["list-secrets", "GET", `/api/v1/namespaces/${c.namespace}/secrets`],
    ["read-ca-key-secret", "GET", c.caSecretPath ?? `/api/v1/namespaces/${c.namespace}/secrets/synthetic-ca`],
    ["list-pods", "GET", `/api/v1/namespaces/${c.namespace}/pods`],
    ["list-requests", "GET", `/apis/cert-manager.io/v1/namespaces/${c.namespace}/certificaterequests`],
    ["patch-other-deployment", "PATCH", `/apis/apps/v1/namespaces/${c.namespace}/deployments/not-enrolled`, {}],
    ["mint-token", "POST", `/api/v1/namespaces/${c.namespace}/serviceaccounts/${c.account}/token`,
      { apiVersion: "authentication.k8s.io/v1", kind: "TokenRequest", spec: {
        audiences: ["https://kubernetes.default.svc.cluster.local"], expirationSeconds: 600 } }],
    ["list-csrs", "GET", "/apis/certificates.k8s.io/v1/certificatesigningrequests"],
    ["other-namespace", "GET", "/api/v1/namespaces/bortus-ntfy-denied-qualify/secrets"],
  ]
  const denied = []
  for (const [label, method, path, body] of cases) {
    const reply = await request(method, path, body)
    if (reply.status !== 403) throw new Error("unexpected_allow")
    denied.push({ operation: label, status: reply.status })
  }
  console.log(JSON.stringify({ passed: true, subject: info.username, uid: info.uid,
    authenticatedProjectedToken: true, certificateAndSecretMetadataGET: true,
    positive, denied, tokenOrPrivateKeyPersisted: false }))
}
main().catch(() => {
  console.log(JSON.stringify({ passed: false, reason: "identity_or_scope_check_failed" }))
  process.exitCode = 1
})
