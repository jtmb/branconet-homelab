/** Public certificate metadata only. Never fetch TLS Secrets for inventory. */
export type CertificateHealth = "healthy" | "renewing" | "warning" | "expired" | "unknown";
export interface CertificateRow {
  id: string;
  name: string;
  namespace: string;
  names: string[];
  issuer: string;
  renewalOwner: string;
  notAfter: string | null;
  renewalTime: string | null;
  health: CertificateHealth;
  message: string;
}
export interface CertificateRequestRow {
  id: string;
  name: string;
  requester: string;
  signer: string;
  createdAt: string | null;
  state: "pending" | "denied" | "failed" | "approved" | "issued";
  message: string;
}
export interface CertificateInventory {
  sampledAt: string;
  certificates: CertificateRow[];
  requests: CertificateRequestRow[];
  warnings: string[];
  sources: { resource: string; available: boolean; message: string }[];
  automation: { mode: "unavailable"; message: string };
}
type Json = Record<string, unknown>;
export type CertificateReader = (args: readonly string[]) => Promise<unknown>;
const object = (value: unknown): Json => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Json : {};
const text = (value: unknown, fallback = "Unknown"): string => typeof value === "string" && value.length <= 512 ? value : fallback;
const date = (value: unknown): string | null => typeof value === "string" && Number.isFinite(Date.parse(value)) ? new Date(value).toISOString() : null;
const items = (value: unknown): Json[] => {
  const list = object(value);
  const metadata = object(list.metadata);
  // Kubernetes may encode a valid empty typed list as items:null.
  const rows = list.items === null && ["CertificateList", "CertificateSigningRequestList"].includes(text(list.kind)) ? [] : list.items;
  if (!Array.isArray(rows) || rows.length > 1000 ||
      rows.some(item => item === null || typeof item !== "object" || Array.isArray(item)) ||
      metadata.continue || (metadata.remainingItemCount !== undefined && metadata.remainingItemCount !== 0))
    throw Error("Incomplete or malformed inventory");
  return rows as Json[];
};
const condition = (status: Json, type: string) => Array.isArray(status.conditions) &&
  status.conditions.some(value => object(value).type === type && object(value).status === "True");

export function certificateRow(value: unknown, now: number): CertificateRow {
  const resource = object(value), meta = object(resource.metadata), spec = object(resource.spec), status = object(resource.status);
  if (typeof meta.uid !== "string" || typeof meta.name !== "string" || typeof meta.namespace !== "string")
    throw Error("Certificate identity unavailable");
  const notAfter = date(status.notAfter), renewalTime = date(status.renewalTime);
  const ready = condition(status, "Ready"), renewing = condition(status, "Issuing");
  const expiry = notAfter ? Date.parse(notAfter) : NaN;
  const renewalDue = renewalTime !== null && Date.parse(renewalTime) <= now;
  const issuer = object(spec.issuerRef);
  // cert-manager owns its renewal schedule; annual node thresholds do not apply.
  const health: CertificateHealth = expiry <= now ? "expired" : renewing ? "renewing" :
    !notAfter ? "unknown" : !ready || renewalDue || expiry - now <= 7 * 86400000 ? "warning" : "healthy";
  return {
    id: text(meta.uid), name: text(meta.name), namespace: text(meta.namespace),
    names: Array.isArray(spec.dnsNames) ? spec.dnsNames.slice(0, 100).map(name => text(name)) : [],
    issuer: `${text(issuer.kind, "Issuer")}/${text(issuer.name)}`,
    renewalOwner: "cert-manager", notAfter, renewalTime, health,
    message: health === "expired" ? "Certificate has expired." :
      health === "renewing" ? "Issuance is in progress; the served certificate is not yet verified." :
      health === "unknown" ? "Certificate expiry is unavailable." :
      health === "warning" ? "Readiness, renewal schedule or expiry requires attention." :
      "Ready according to cert-manager. The served endpoint has not been verified by this inventory.",
  };
}

export function certificateRequestRow(value: unknown): CertificateRequestRow {
  const resource = object(value), meta = object(resource.metadata), spec = object(resource.spec), status = object(resource.status);
  if (typeof meta.uid !== "string" || typeof meta.name !== "string") throw Error("CSR identity unavailable");
  // Denial/failure wins even if an inconsistent object also contains a certificate.
  const state: CertificateRequestRow["state"] = condition(status, "Denied") ? "denied" :
    condition(status, "Failed") ? "failed" : typeof status.certificate === "string" && status.certificate.length > 0 ? "issued" :
      condition(status, "Approved") ? "approved" : "pending";
  return {
    id: text(meta.uid), name: text(meta.name), requester: text(spec.username), signer: text(spec.signerName),
    createdAt: date(meta.creationTimestamp), state,
    message: state === "issued" ? "Issued by the signer; installation and endpoint verification are not established." :
      state === "approved" ? "Approved only; waiting for the signer. This is not a completed renewal." :
      state === "pending" ? "No approval recorded. Identity validation is required before any approval." :
      "The request was denied or failed. Inspect it through the operator workflow.",
  };
}

/** No shared last-good cache: a denied source must not appear healthy or empty. */
export async function certificateInventory(read: CertificateReader, now = Date.now()): Promise<CertificateInventory> {
  const report: CertificateInventory = {
    sampledAt: new Date(now).toISOString(), certificates: [], requests: [], warnings: [],
    sources: [], automation: {
      mode: "unavailable",
      message: "Scheduled monitoring and unattended approval are not enabled. This page performs read-only inventory checks.",
    },
  };
  const sources = [
    { resource: "certificates.cert-manager.io", args: ["get", "certificates.cert-manager.io", "-A"], kind: "certificates" },
    { resource: "certificatesigningrequests.certificates.k8s.io", args: ["get", "certificatesigningrequests.certificates.k8s.io"], kind: "requests" },
  ] as const;
  const results = await Promise.allSettled(sources.map(async source => {
    const rows = items(await read(source.args));
    return source.kind === "certificates" ? rows.map(row => certificateRow(row, now)) : rows.map(certificateRequestRow);
  }));
  results.forEach((result, index) => {
    const source = sources[index], available = result.status === "fulfilled";
    report.sources.push({
      resource: source.resource, available,
      message: available ? "Complete visible inventory read." : "Unavailable: check resource availability, permissions and API connectivity.",
    });
    if (result.status === "fulfilled") {
      if (source.kind === "certificates") report.certificates = result.value as CertificateRow[];
      else report.requests = result.value as CertificateRequestRow[];
    } else report.warnings.push(`${source.resource} inventory is unavailable. Coverage is unknown, not empty.`);
  });
  report.certificates.sort((a, b) => (a.notAfter ?? "9999").localeCompare(b.notAfter ?? "9999") || a.name.localeCompare(b.name));
  report.requests.sort((a, b) => (b.createdAt ?? "").localeCompare(a.createdAt ?? ""));
  report.warnings.push("Host kubeadm/kubelet, mesh CA and served-endpoint checks are not connected to this inventory. Their trust and expiry are unknown here.");
  report.warnings.push("Consumers have not been mapped. No certificate is classified as unused or safe to retire.");
  return report;
}
