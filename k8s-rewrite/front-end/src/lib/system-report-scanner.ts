import { spawn } from "node:child_process";
import { readFile, stat, mkdtemp, rm } from "node:fs/promises";
import { isAbsolute, join } from "node:path";
import { tmpdir } from "node:os";
import { createHash } from "node:crypto";
import { runtimeImage } from "./system-report-inventory";
import { SEVERITIES, safeAdvisoryURL, type Finding, type ScanResult, type Severity } from "./system-report-types";

export const SCAN_TIMEOUT_MS = 90000;
export const SCAN_OUTPUT_BYTES = 8 * 1024 * 1024;
export interface Scanner {
  status(): Promise<{ configured: boolean; message: string; cacheKey: string }>;
  scan(reference: string, signal: AbortSignal): Promise<ScanResult>;
}
type ObjectValue = Record<string, unknown>;
function object(value: unknown): ObjectValue { return value && typeof value === "object" && !Array.isArray(value) ? value as ObjectValue : {}; }
function text(value: unknown, maximum = 512): string { return typeof value === "string" ? value.slice(0, maximum) : ""; }
function date(value: unknown): string | undefined {
  return typeof value === "string" && Number.isFinite(Date.parse(value)) ? new Date(value).toISOString() : undefined;
}

/** Project scanner JSON into finite UI fields, never forward raw scanner output/credentials. */
export function normalizeTrivy(value: unknown, reference: string, database: ObjectValue, now = Date.now()): ScanResult {
  const report = object(value), metadata = object(report.Metadata);
  const identity = runtimeImage(reference);
  if (report.SchemaVersion !== 2 || !identity || !Array.isArray(metadata.RepoDigests) ||
    !metadata.RepoDigests.some(digest => runtimeImage(text(digest))?.digest === identity.digest))
    throw Error("Scanner result does not establish the requested runtime digest");
  if (!Array.isArray(report.Results) || !report.Results.length || report.Results.length > 1000)
    return { state: "unsupported", message: "Scanner recognized no analyzable package targets. Coverage is unknown.", findings: [] };
  let packageCount = 0;
  const findings: Finding[] = [];
  const seen = new Set<string>();
  for (const rawResult of report.Results) {
    const result = object(rawResult), packages = result.Packages;
    if (!Array.isArray(packages) || packages.length > 50000) throw Error("Scanner package coverage missing or exceeds limits");
    packageCount += packages.length;
    if (packageCount > 100000) throw Error("Scanner package count exceeds limit");
    const vulnerabilities = result.Vulnerabilities ?? [];
    if (!Array.isArray(vulnerabilities) || vulnerabilities.length > 10000) throw Error("Scanner findings exceed limit");
    for (const raw of vulnerabilities) {
      const vulnerability = object(raw);
      const id = text(vulnerability.VulnerabilityID), name = text(vulnerability.PkgName), installed = text(vulnerability.InstalledVersion);
      if (!id || !name || !installed) throw Error("Scanner finding is incomplete");
      const target = text(result.Target);
      const key = JSON.stringify([id, name, installed, target]);
      if (seen.has(key)) continue;
      seen.add(key);
      if (seen.size > 10000) throw Error("Scanner findings exceed limit");
      const severity = SEVERITIES.includes(vulnerability.Severity as Severity) ? vulnerability.Severity as Severity : "UNKNOWN";
      const references = Array.isArray(vulnerability.References) ? vulnerability.References : [];
      findings.push({ id, package: name, installed, fixed: text(vulnerability.FixedVersion), target, severity,
        title: text(vulnerability.Title), url: safeAdvisoryURL(vulnerability.PrimaryURL) ?? references.map(safeAdvisoryURL).find(Boolean) ?? null });
    }
  }
  if (!packageCount) return { state: "unsupported", message: "No packages analyzed; zero matches cannot establish coverage.", findings: [] };
  findings.sort((a, b) => SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity) || a.id.localeCompare(b.id));
  return { state: "complete", findings, packageCount, scannedAt: new Date(now).toISOString(),
    dbUpdatedAt: date(database.UpdatedAt), dbNextUpdate: date(database.NextUpdate),
    scannerVersion: text(object(report.Trivy).Version, 100) || undefined, endOfLife: object(metadata.OS).EOSL === true };
}

/** No shell, inherited Trivy settings, cluster credentials, daemon socket, update service or telemetry. */
export function trivyArguments(reference: string, cache: string): string[] {
  if (!runtimeImage(reference)) throw Error("A registry-qualified runtime digest is required");
  const empty = process.platform === "win32" ? "NUL" : "/dev/null";
  return ["image", "--config", empty, "--ignorefile", empty, "--cache-dir", cache, "--cache-backend", "memory",
    "--image-src", "remote", "--scanners", "vuln", "--format", "json", "--list-all-pkgs",
    "--skip-db-update", "--skip-java-db-update", "--skip-check-update", "--offline-scan",
    "--skip-version-check", "--disable-telemetry", "--parallel", "1", "--max-image-size", "1GB",
    "--timeout", "90s", "--quiet", "--", reference];
}

export function executeScanner(binary: string, args: string[], cache: string, signal: AbortSignal, temporary = tmpdir(),
  limits = { timeoutMs: SCAN_TIMEOUT_MS, outputBytes: SCAN_OUTPUT_BYTES, errorBytes: 65536 }): Promise<string> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(Error("cancelled")); return; }
    const env: NodeJS.ProcessEnv = { NODE_ENV: "production", PATH: process.env.PATH, SystemRoot: process.env.SystemRoot,
      HOME: cache, USERPROFILE: cache, XDG_CONFIG_HOME: cache, DOCKER_CONFIG: join(cache, "registry-auth"),
      TMP: temporary, TEMP: temporary, TMPDIR: temporary, GOMAXPROCS: "1", GOMEMLIMIT: "256MiB" };
    const child = spawn(binary, args, { shell: false, windowsHide: true, cwd: cache, env, stdio: ["ignore", "pipe", "pipe"] });
    const buffers: Buffer[] = [];
    let size = 0, stderrSize = 0, failure: string | undefined;
    const stop = (message: string) => { failure ??= message; child.kill("SIGKILL"); };
    const abort = () => stop("cancelled");
    const timer = setTimeout(() => stop("timeout"), limits.timeoutMs);
    signal.addEventListener("abort", abort, { once: true });
    child.stdout.on("data", (chunk: Buffer) => {
      size += chunk.length;
      if (size > limits.outputBytes) stop("output limit");
      else buffers.push(chunk);
    });
    child.stderr.on("data", (chunk: Buffer) => { stderrSize += chunk.length; if (stderrSize > limits.errorBytes) stop("error output limit"); });
    child.on("error", () => { failure ??= "scanner unavailable"; });
    // Hold the single scanner slot until the actual process and pipes close.
    child.on("close", code => {
      clearTimeout(timer); signal.removeEventListener("abort", abort);
      if (failure || code !== 0) reject(Error(failure ?? "scanner failed"));
      else resolve(Buffer.concat(buffers).toString("utf8"));
    });
  });
}

export function localTrivyScanner(binary = process.env.BORTUS_TRIVY_PATH, cache = process.env.BORTUS_TRIVY_CACHE_DIR): Scanner {
  async function database(): Promise<{ bytes: string; fingerprint: string; metadata: ObjectValue }> {
    if (!binary || !cache || !isAbsolute(binary) || !isAbsolute(cache)) throw Error("Local scanner is not configured");
    const metadataPath = join(cache, "db", "metadata.json");
    const dbFile = await stat(join(cache, "db", "trivy.db")), executable = await stat(binary);
    if ((await stat(metadataPath)).size > 65536 || !executable.isFile() || !dbFile.isFile() || dbFile.size < 1 || dbFile.size > 3 * 1024 ** 3) throw Error("Scanner inputs unavailable");
    const bytes = await readFile(metadataPath, "utf8"), metadata = object(JSON.parse(bytes));
    if (!date(metadata.UpdatedAt) || !date(metadata.NextUpdate)) throw Error("Database freshness metadata unavailable");
    return { bytes, metadata, fingerprint: JSON.stringify([dbFile.size, dbFile.mtimeMs, executable.size, executable.mtimeMs]) };
  }
  return {
    async status() {
      try {
        const db = await database();
        return { configured: true, message: "Local Trivy • prepared advisory database • no uploads", cacheKey: createHash("sha256").update(binary!).update(db.bytes).update(db.fingerprint).digest("hex") };
      } catch { return { configured: false, message: "Local scanner unavailable. Configure BORTUS_TRIVY_PATH and BORTUS_TRIVY_CACHE_DIR with a prepared database in the BORTUS runtime.", cacheKey: "unavailable" }; }
    },
    async scan(reference, signal) {
      let temporary: string | undefined;
      try {
        const before = await database();
        temporary = await mkdtemp(join(tmpdir(), "bortus-cve-"));
        const output = await executeScanner(binary!, trivyArguments(reference, cache!), cache!, signal, temporary);
        const after = await database();
        if (before.bytes !== after.bytes || before.fingerprint !== after.fingerprint) throw Error("database changed");
        return normalizeTrivy(JSON.parse(output), reference, before.metadata);
      } catch {
        return { state: signal.aborted ? "cancelled" : "error", findings: [], message: signal.aborted ? "Scan cancelled; coverage incomplete." : "Local scan failed, timed out, exceeded a limit or could not establish package/digest coverage. Check runtime scanner/database and existing registry access; raw scanner errors are withheld." };
      } finally { if (temporary) await rm(temporary, { recursive: true, force: true }); }
    },
  };
}
