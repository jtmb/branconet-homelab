export const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"] as const;
export type Severity = typeof SEVERITIES[number];
export type ScanState = "unscanned" | "queued" | "scanning" | "complete" | "unsupported" | "error" | "cancelled";
export interface Consumer {
  cluster: string; namespace: string; pod: string; container: string;
  kind: "container" | "init" | "ephemeral"; workload: string; services: string[] | null;
}
export interface Finding {
  id: string; severity: Severity; package: string; installed: string; fixed: string;
  target: string; title: string; url: string | null;
}
export interface ScanResult {
  state: ScanState; message?: string; scannedAt?: string;
  dbUpdatedAt?: string; dbNextUpdate?: string; scannerVersion?: string;
  packageCount?: number; findings: Finding[]; endOfLife?: boolean;
}
export interface ImageReport extends ScanResult {
  key: string; digest: string | null; reference: string | null; aliases: string[]; consumers: Consumer[];
}
export interface Inventory {
  images: ImageReport[]; sampledAt: string | null; warnings: string[];
  available: boolean; stale: boolean; runningContainers: number;
}
export interface SystemReport extends Inventory {
  job: { id: string; state: "running" | "complete" | "cancelled" | "error"; startedAt: string; finishedAt?: string } | null;
  scanner: { configured: boolean; message: string };
}
export function safeAdvisoryURL(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 2048) return null;
  try { const url = new URL(value); return url.protocol === "https:" && !url.username && !url.password ? url.href : null; }
  catch { return null; }
}
export function resultStale(result: ScanResult, now = Date.now()): boolean {
  if (result.state !== "complete") return false;
  const scan = Date.parse(result.scannedAt ?? ""), update = Date.parse(result.dbUpdatedAt ?? ""), next = Date.parse(result.dbNextUpdate ?? "");
  return ![scan, update, next].every(Number.isFinite) || scan > now + 300000 || update > now + 300000 ||
    now - scan > 24 * 3600000 || now - update > 48 * 3600000 || now >= next;
}
