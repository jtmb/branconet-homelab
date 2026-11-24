import { KubernetesCommandError } from "./kubectl-client";

/** kubectl normally collects pages; an incomplete discovery cannot establish empty children. */
export function requireCompleteFluxList(value: any): void {
  if (!value || typeof value !== "object" || Array.isArray(value) || !Array.isArray(value.items) || value.items.length > 10000
    || value.items.some((item: unknown) => !item || typeof item !== "object" || Array.isArray(item))
    || (value.metadata !== undefined && (!value.metadata || typeof value.metadata !== "object" || Array.isArray(value.metadata)))
    || (value.metadata && ((value.metadata.continue !== undefined && value.metadata.continue !== "")
      || (value.metadata.remainingItemCount !== undefined && value.metadata.remainingItemCount !== 0))))
    throw new KubernetesCommandError(502, "Invalid or incomplete Flux resource list");
}

/** Repository locations are persisted/public metadata. Authentication belongs in a native Secret. */
export function repositoryUrl(value: unknown): string {
  const invalid = () => new KubernetesCommandError(400, "Use a credential-free HTTPS or SSH repository URL; provide authentication separately");
  if (typeof value !== "string" || !value || value.length > 2048 || /[\s\u0000-\u001f\u007f]/.test(value) || value.includes("\\")) throw invalid();
  // Git's SCP spelling carries only a nonsecret SSH login, never a password/query/fragment.
  if (/^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+:[a-zA-Z0-9._/~+-]+$/.test(value)) return value;
  let parsed: URL;
  try { parsed = new URL(value); } catch { throw invalid(); }
  if (!["https:", "ssh:"].includes(parsed.protocol) || !parsed.hostname || !parsed.pathname || parsed.pathname === "/"
      || parsed.password || parsed.search || parsed.hash || parsed.protocol === "https:" && parsed.username
      || parsed.protocol === "ssh:" && parsed.username && !/^[a-zA-Z0-9._-]+$/.test(parsed.username)) throw invalid();
  return value;
}

export function publicRepositoryUrl(value: unknown): string {
  try { return repositoryUrl(value); } catch { return ""; }
}
export function fluxReadiness(...conditions: unknown[]): string {
  const states = conditions.map(condition => condition && typeof condition === "object" ? (condition as Record<string, unknown>).status : undefined);
  if (states.some(status => status === "False")) return "Not Ready";
  return states.length && states.every(status => status === "True") ? "Ready" : "Unknown";
}
export function publicFluxConditions(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 32).map(condition => {
    const row = condition && typeof condition === "object" ? condition as Record<string, unknown> : {};
    const type = typeof row.type === "string" ? row.type : "";
    return { type: ["Ready", "Reconciling", "Stalled", "Released", "TestSuccess", "Remediated"].includes(type) ? type : "Other",
      status: row.status === "True" || row.status === "False" ? row.status : "Unknown",
      reason: fluxReadiness(row), message: "Controller output withheld" };
  });
}
