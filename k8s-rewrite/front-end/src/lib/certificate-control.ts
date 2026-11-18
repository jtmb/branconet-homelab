/** Fixed metadata-only control channel for the independent certificate runner. */
export const CERTIFICATE_CONTROL_NAMESPACE = "bortus";
export const CERTIFICATE_POLICY_NAME = "bortus-certificate-policy";
export const CERTIFICATE_OBSERVATIONS_NAME = "bortus-certificate-observations";
const resources = ["certificates.cert-manager.io", "certificatesigningrequests.certificates.k8s.io"];
export interface MonitoringPolicy {
  version: 1; mode: "paused" | "monitor"; scanIntervalSeconds: number; expiryWarningDays: number;
}
export interface PolicyAudit {
  actor: string; at: string; previousRevision: string; policy: MonitoringPolicy;
}
export interface PolicyView {
  uid: string; revision: string; desired: MonitoringPolicy; audit: PolicyAudit[];
}
const DELIVERY_STATES = ["not-configured", "no-delivery-yet", "pending-delivery", "delivered"] as const;

export interface MonitorObservation {
  uid: string; name: string; namespace: string; resource: string; state: string; observedAt: string;
  notAfter?: string | null; renewalTime?: string | null; requester?: string; signer?: string;
}
export interface MonitorView {
  heartbeatAt: string; policyUid: string; policyRevision: string; mode: "paused" | "monitor";
  sources: { resource: string; checkedAt: string; available: boolean; stale: boolean }[];
  observations: MonitorObservation[];
  lastRun: { id: string; startedAt: string; finishedAt: string | null; state: string } | null;
  notificationsPending: number;
  notificationDelivery: "not-configured" | "no-delivery-yet" | "pending-delivery" | "delivered";
}
export interface CertificateControls {
  policy: PolicyView | null; monitor: MonitorView | null;
  state: "unavailable" | "offline" | "pending" | "paused" | "monitoring" | "degraded";
  message: string;
}
type Json = Record<string, unknown>;
type Read = (args: readonly string[]) => Promise<unknown>;
type Patch = (args: readonly string[]) => Promise<unknown>;
const headers = { "Cache-Control": "private, no-store" };
export class CertificateControlError extends Error {
  readonly status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}
function record(value: unknown, status = 503): Json {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new CertificateControlError(status, "Invalid certificate control metadata");
  return value as Json;
}
function string(value: unknown, status = 503): string {
  if (typeof value !== "string" || !value.length || value.length > 512) throw new CertificateControlError(status, "Invalid certificate control field");
  return value;
}
function time(value: unknown): string {
  const text = string(value);
  if (!Number.isFinite(Date.parse(text))) throw new CertificateControlError(503, "Invalid certificate observation time");
  return new Date(text).toISOString();
}
function json(value: unknown): unknown {
  if (typeof value !== "string" || value.length > 512 * 1024) throw new CertificateControlError(503, "Certificate control data unavailable");
  try { return JSON.parse(value); } catch { throw new CertificateControlError(503, "Invalid certificate control data"); }
}
function configMap(value: unknown, name: string) {
  const object = record(value), metadata = record(object.metadata);
  if (object.kind !== "ConfigMap" || metadata.name !== name || metadata.namespace !== CERTIFICATE_CONTROL_NAMESPACE)
    throw new CertificateControlError(503, "Certificate control identity mismatch");
  return { uid: string(metadata.uid), revision: string(metadata.resourceVersion), data: record(object.data) };
}
export function monitoringPolicy(value: unknown): MonitoringPolicy {
  const input = record(value, 400);
  if (Object.keys(input).sort().join(",") !== "expiryWarningDays,mode,scanIntervalSeconds,version" ||
      input.version !== 1 || (input.mode !== "paused" && input.mode !== "monitor") ||
      !Number.isInteger(input.scanIntervalSeconds) || Number(input.scanIntervalSeconds) < 60 || Number(input.scanIntervalSeconds) > 900 ||
      !Number.isInteger(input.expiryWarningDays) || Number(input.expiryWarningDays) < 1 || Number(input.expiryWarningDays) > 30)
    throw new CertificateControlError(400, "Use paused/monitor, a 60–900 second interval and a 1–30 day expiry warning");
  return { version: 1, mode: input.mode as MonitoringPolicy["mode"],
    scanIntervalSeconds: input.scanIntervalSeconds as number, expiryWarningDays: input.expiryWarningDays as number };
}
export function policyView(value: unknown): PolicyView {
  const map = configMap(value, CERTIFICATE_POLICY_NAME);
  const desired = monitoringPolicy(json(map.data["policy.json"]));
  const audit = json(map.data["audit.json"] ?? "[]");
  if (!Array.isArray(audit) || audit.length > 50) throw new CertificateControlError(503, "Invalid certificate policy history");
  return { uid: map.uid, revision: map.revision, desired, audit: audit.map(value => {
    const entry = record(value);
    return { actor: string(entry.actor), at: time(entry.at), previousRevision: string(entry.previousRevision), policy: monitoringPolicy(entry.policy) };
  }) };
}
export function monitorView(value: unknown, now = Date.now()): MonitorView {
  const map = configMap(value, CERTIFICATE_OBSERVATIONS_NAME);
  const data = record(json(map.data["snapshot.json"]));
  const policy = record(data.policy);
  if (data.version !== 1 || (data.mode !== "paused" && data.mode !== "monitor") ||
      !Array.isArray(data.sources) || data.sources.length > 2 ||
      !Array.isArray(data.observations) || data.observations.length > 2000 ||
      !Number.isSafeInteger(data.notificationsPending) || Number(data.notificationsPending) < 0 ||
      // Delivery state is optional so an older monitor snapshot still renders;
      // an unrecognised value is still rejected rather than guessed at.
      (data.notificationDelivery !== undefined &&
       !DELIVERY_STATES.includes(data.notificationDelivery as never)))
    throw new CertificateControlError(503, "Invalid certificate monitor snapshot");
  const seen = new Set<string>();
  const sources = data.sources.map(value => {
    const source = record(value), resource = string(source.resource), checkedAt = time(source.checkedAt);
    if (!resources.includes(resource) || seen.has(resource) || typeof source.available !== "boolean")
      throw new CertificateControlError(503, "Invalid certificate monitor source");
    seen.add(resource);
    const age = now - Date.parse(checkedAt);
    return { resource, checkedAt, available: source.available, stale: age < 0 || age > 15 * 60000 };
  });
  const observations = data.observations.map(value => {
    const entry = record(value), resource = string(entry.resource), state = string(entry.state);
    if (resource === "tls-endpoint") {
      const name = string(entry.name), uid = string(entry.uid);
      if (name !== uid || !/^node0[1-3]:(apiserver|kubelet)$/.test(name) ||
          !["expired", "warning", "healthy"].includes(state) ||
          (entry.namespace !== undefined && entry.namespace !== ""))
        throw new CertificateControlError(503, "Invalid TLS endpoint observation");
      return { uid, name, namespace: "", resource, state,
        observedAt: time(entry.observedAt), notAfter: time(entry.notAfter) };
    }
    if (!resources.includes(resource) || !["expired", "renewing", "unknown", "warning", "healthy", "denied", "failed", "issued", "approved", "pending"].includes(state))
      throw new CertificateControlError(503, "Invalid certificate observation");
    const projected: MonitorObservation = {
      uid: string(entry.uid), name: string(entry.name), namespace: entry.namespace === "" ? "" : string(entry.namespace),
      resource, state, observedAt: time(entry.observedAt),
    };
    for (const key of ["notAfter", "renewalTime"] as const) if (entry[key] !== undefined)
      projected[key] = entry[key] === null ? null : time(entry[key]);
    for (const key of ["requester", "signer"] as const) if (entry[key] !== undefined) projected[key] = string(entry[key]);
    return projected;
  });
  let lastRun: MonitorView["lastRun"] = null;
  if (data.lastRun !== null) {
    const run = record(data.lastRun);
    if (typeof run.state !== "string" || !["running", "interrupted", "complete", "partial"].includes(run.state))
      throw new CertificateControlError(503, "Invalid certificate run state");
    lastRun = { id: string(run.id), startedAt: time(run.startedAt),
      finishedAt: run.finishedAt === null ? null : time(run.finishedAt), state: run.state as string };
  }
  return { heartbeatAt: time(data.heartbeatAt), policyUid: string(policy.uid), policyRevision: string(policy.revision),
    mode: data.mode as MonitorView["mode"], sources, observations, lastRun,
    notificationsPending: data.notificationsPending as number,
    notificationDelivery: (data.notificationDelivery ?? "not-configured") as MonitorView["notificationDelivery"] };
}
export async function certificateControls(read: Read, now = Date.now()): Promise<CertificateControls> {
  const get = (name: string) => read(["get", "configmap", name, "-n", CERTIFICATE_CONTROL_NAMESPACE]);
  const [policyResult, monitorResult] = await Promise.allSettled([
    get(CERTIFICATE_POLICY_NAME).then(policyView),
    get(CERTIFICATE_OBSERVATIONS_NAME).then(value => monitorView(value, now)),
  ]);
  const policy = policyResult.status === "fulfilled" ? policyResult.value : null;
  const monitor = monitorResult.status === "fulfilled" ? monitorResult.value : null;
  const result = { policy, monitor };
  if (!policy) return { ...result, state: "unavailable", message: "Policy unavailable. Bootstrap the fixed control resources and verify scoped access; no default policy is applied." };
  const age = monitor ? now - Date.parse(monitor.heartbeatAt) : Infinity;
  if (!monitor || age < 0 || age > 180000) return { ...result, state: "offline", message: "Runner heartbeat is missing or stale. A saved policy is not proof of active monitoring." };
  if (monitor.policyUid !== policy.uid || monitor.policyRevision !== policy.revision || monitor.mode !== policy.desired.mode)
    return { ...result, state: "pending", message: "Policy saved; the runner has not acknowledged this revision." };
  if (monitor.mode === "paused") return { ...result, state: "paused", message: "Runner acknowledged the pause. Previous observations are historical." };
  if (monitor.sources.length !== 2 || monitor.sources.some(source => !source.available || source.stale) || monitor.lastRun?.state !== "complete")
    return { ...result, state: "degraded", message: "Runner is reachable, but monitoring has incomplete or stale coverage." };
  return { ...result, state: "monitoring", message: "Runner acknowledged the current monitoring policy. Host, mesh and served-endpoint verification remain separate." };
}
export async function updateCertificatePolicy(read: Read, patch: Patch, input: unknown, actor: string, now = Date.now()): Promise<PolicyView> {
  const body = record(input, 400);
  if (Object.keys(body).sort().join(",") !== "policy,revision,uid") throw new CertificateControlError(400, "Expected policy, revision and uid only");
  const desired = monitoringPolicy(body.policy), uid = string(body.uid, 400), revision = string(body.revision, 400);
  const args = ["get", "configmap", CERTIFICATE_POLICY_NAME, "-n", CERTIFICATE_CONTROL_NAMESPACE];
  const current = policyView(await read(args));
  if (current.uid !== uid || current.revision !== revision) throw new CertificateControlError(409, "Policy changed. Refresh before saving again.");
  const audit = [...current.audit, { actor: string(actor), at: new Date(now).toISOString(), previousRevision: revision, policy: desired }].slice(-50);
  const operations = [
    { op: "test", path: "/metadata/uid", value: uid }, { op: "test", path: "/metadata/resourceVersion", value: revision },
    { op: "add", path: "/data/policy.json", value: JSON.stringify(desired) },
    { op: "add", path: "/data/audit.json", value: JSON.stringify(audit) },
  ];
  const updated = await patch(["patch", "configmap", CERTIFICATE_POLICY_NAME, "-n", CERTIFICATE_CONTROL_NAMESPACE, "--type=json", "-p", JSON.stringify(operations)]);
  return policyView(updated);
}

/** Authorization precedes body consumption; bounded, same-origin browser mutation. */
export async function certificatePolicyResponse(request: Request, dependencies: {
  authorize: () => Promise<{ id: string } | Response>;
  read: Read; patch: Patch;
}): Promise<Response> {
  const actor = await dependencies.authorize();
  if (actor instanceof Response) return actor;
  if (request.headers.get("origin") !== new URL(request.url).origin)
    return Response.json({ error: "Same-origin request required" }, { status: 403, headers });
  try {
    const reader = request.body?.getReader();
    if (!reader) throw new CertificateControlError(400, "Policy body required");
    let size = 0, content = "";
    const decoder = new TextDecoder("utf-8", { fatal: true });
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.length;
        if (size > 4096) { await reader.cancel(); throw new CertificateControlError(413, "Policy request exceeds size limit"); }
        content += decoder.decode(value, { stream: true });
      }
      content += decoder.decode();
    } finally { reader.releaseLock(); }
    let input: unknown;
    try { input = JSON.parse(content); } catch { throw new CertificateControlError(400, "Invalid policy JSON"); }
    const policy = await updateCertificatePolicy(dependencies.read, dependencies.patch, input, actor.id);
    return Response.json({ policy }, { headers });
  } catch (error) {
    const known = error instanceof CertificateControlError;
    // Process failures may contain private API output. Expose only fixed guidance.
    const conflict = !known && (error as { status?: number })?.status === 409;
    return Response.json({ error: known ? error.message : conflict ? "Policy changed. Refresh before saving again." : "Policy save could not be verified. Refresh before retrying." },
      { status: known ? error.status : conflict ? 409 : 503, headers });
  }
}
