/**
 * Fail-closed serving-leaf rollout decisions. No network, keys or mutations.
 * The executor must supply authenticated current facts, verify the issued
 * public leaf and recheck facts immediately before transmitting a CAS patch.
 */
export const REQUESTED = "bortus.jtmb.cc/requested-serving-fingerprint"
const digest = /^[0-9a-f]{64}$/
const attention = reason => ({ state: "attention", reason, patch: null })
const wait = reason => ({ state: "waiting", reason, patch: null })

export function decide(enrollment, facts, nowSeconds) {
  if (!enrollment || !["observe", "auto"].includes(enrollment.mode)
      || !enrollment.certificateUID || !enrollment.secretUID || !enrollment.deploymentUID
      || !Number.isSafeInteger(nowSeconds)) return attention("invalid_enrollment")
  const { certificate: cert, secret, deployment: deploy, issued, projected, served } = facts ?? {}
  if (!cert || !secret || !deploy) return attention("coverage_unknown")
  if (cert.uid !== enrollment.certificateUID) return attention("certificate_recreated")
  if (secret.uid !== enrollment.secretUID) return attention("secret_recreated")
  if (deploy.uid !== enrollment.deploymentUID) return attention("deployment_recreated")
  if (!cert.ready || cert.observedGeneration !== cert.generation
      || !Number.isSafeInteger(cert.revision) || cert.revision < 1) return wait("issuance_not_current")
  if (!issued || issued.ownerUID !== cert.uid || issued.revision !== cert.revision
      || !issued.ready || !issued.cryptographicallyVerified
      || !digest.test(issued.fingerprint)) return attention("issued_leaf_not_verified")
  if (!Number.isSafeInteger(issued.notBefore) || !Number.isSafeInteger(issued.notAfter)
      || issued.notBefore > nowSeconds + 5 || issued.notAfter < nowSeconds + 300) {
    return attention("issued_leaf_time_invalid")
  }
  if (!projected || projected.fingerprint !== issued.fingerprint) return wait("projection_pending")
  if (!served || !served.trusted || !digest.test(served.fingerprint)) return attention("endpoint_trust_unknown")
  if (!deploy.resourceVersion || !secret.resourceVersion || !cert.resourceVersion) {
    return attention("revision_unknown")
  }
  // A successful observation, not an annotation or rollout request, proves
  // that the desired leaf is actually being served.
  if (served.fingerprint === issued.fingerprint) {
    return { state: "verified", reason: "expected_leaf_served", fingerprint: issued.fingerprint, patch: null }
  }
  if (deploy.paused || deploy.replicas !== 1 || deploy.strategy !== "Recreate") {
    return attention("unsupported_or_paused_workload")
  }
  const annotations = deploy.templateAnnotations ?? {}
  if (annotations[REQUESTED] === issued.fingerprint) return wait("requested_rollout_not_yet_verified")
  if (enrollment.mode === "observe") {
    return { state: "observing", reason: "would_request_rollout", fingerprint: issued.fingerprint, patch: null }
  }
  return {
    state: "request_rollout", reason: "new_verified_projected_leaf",
    fingerprint: issued.fingerprint,
    // Re-fetch and compare this binding before dispatch; another certificate
    // revision/Secret replacement means reconcile, never blind retry.
    binding: { certificateUID: cert.uid, certificateRV: cert.resourceVersion,
      revision: cert.revision, secretUID: secret.uid, secretRV: secret.resourceVersion },
    patch: [
      { op: "test", path: "/metadata/uid", value: deploy.uid },
      { op: "test", path: "/metadata/resourceVersion", value: deploy.resourceVersion },
      { op: "add", path: "/spec/template/metadata/annotations",
        value: { ...annotations, [REQUESTED]: issued.fingerprint } },
    ],
  }
}
