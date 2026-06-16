/**
 * Cluster Secrets Sync — pushes secret_* variables from Botrus DB
 * to real Kubernetes Secret objects on the cluster.
 *
 * Convention: secret_<namespace>_<secretName>_<key>
 *   secret_plex_smb-creds_username → Secret "smb-creds" in ns "plex", key "username"
 *
 * Sync happens automatically on every CRUD operation to /api/vars.
 * A one-time bootstrap sync fires on module init to catch up pre-existing secrets.
 */

import { execFile } from "child_process";
import { promisify } from "util";
import { hasLocalKubectl, KUBECONFIG_PATH } from "./k8s";

const execFileAsync = promisify(execFile);

// =============================================================================
// Parsing
// =============================================================================

interface ParsedSecret {
  namespace: string;
  name: string;       // K8s Secret name (e.g. "smb-creds")
  key: string;        // field inside the secret (e.g. "username")
}

/**
 * Parse a secret variable key into its K8s Secret components.
 * Convention: secret_<namespace>_<secretName>_<key>
 *
 * Uses maxsplit=3 so secret names with hyphens (smb-creds) work correctly.
 * Returns null if the key doesn't match the secret_* convention.
 */
export function parseSecretKey(key: string): ParsedSecret | null {
  const parts = key.split("_"); // ["secret", "namespace", "name", "maybe", "more", "key"]
  if (parts.length < 4 || parts[0] !== "secret") return null;

  const namespace = parts[1];
  // The remainder contains name + key, joined by underscores.
  // Find the last underscore to split name from key.
  const rest = parts.slice(2).join("_"); // e.g. "smb-creds_username" or "my-secret_token"
  const lastUnderscore = rest.lastIndexOf("_");
  if (lastUnderscore === -1) return null; // No key separator

  const name = rest.slice(0, lastUnderscore);
  const fieldKey = rest.slice(lastUnderscore + 1);

  if (!namespace || !name || !fieldKey) return null;
  return { namespace, name, key: fieldKey };
}

// =============================================================================
// Shell helpers
// =============================================================================

/**
 * Run a kubectl command (no stdin) and return stdout, or null on failure.
 */
async function runKubectl(args: string[], timeoutMs = 15000): Promise<string | null> {
  const fullArgs = ["--kubeconfig", KUBECONFIG_PATH, ...args];
  try {
    const { stdout } = await execFileAsync("kubectl", fullArgs, {
      timeout: timeoutMs,
      maxBuffer: 512 * 1024,
    });
    return stdout.trim() || null;
  } catch (err: any) {
    const stderr = err?.stderr ? String(err.stderr).slice(0, 200) : "";
    if (stderr && !stderr.includes("NotFound") && !stderr.includes("not found")) {
      console.error("[cluster-secrets] kubectl error:", stderr);
    }
    return null;
  }
}

/**
 * Apply YAML to cluster via kubectl apply -f - using a bash pipe.
 * execFile input option doesn't reliably pipe to kubectl, so we use bash -c.
 */
async function kubectlApply(yaml: string): Promise<boolean> {
  // Use printf for reliable byte-for-byte stdin piping through bash
  const kubeconfig = KUBECONFIG_PATH;
  const escaped = yaml
    .replace(/\\/g, "\\\\")
    .replace(/'/g, `'\\''`);
  const cmd = `printf '%s' '${escaped}' | kubectl --kubeconfig '${kubeconfig}' apply -f -`;
  try {
    const { stdout, stderr } = await execFileAsync("bash", ["-c", cmd], {
      timeout: 15000,
      maxBuffer: 512 * 1024,
    });
    console.log("[cluster-secrets] kubectlApply:", stdout?.trim() || stderr?.trim() || "ok");
    return true;
  } catch (err: any) {
    const msg = err?.stderr ? String(err.stderr).slice(0, 300) : err?.message?.slice(0, 300) ?? "";
    console.error("[cluster-secrets] kubectlApply ERROR:", msg);
    return false;
  }
}

// =============================================================================
// K8s Secret operations
// =============================================================================

/**
 * Build and apply a K8s Secret from ALL secret_<ns>_<name>_* variables in the DB.
 * Ensures the namespace exists, creates/updates the Secret, and annotates
 * for FluxCD prune protection.
 */
export async function syncSecretToCluster(
  ns: string,
  name: string
): Promise<{ synced: boolean; keys: string[]; error?: string }> {
  console.log(`[cluster-secrets] syncSecretToCluster called: ns=${ns} name=${name}`);

  if (!hasLocalKubectl()) {
    console.log("[cluster-secrets] No kubeconfig, skipping sync");
    return { synced: false, keys: [], error: "No local kubeconfig found" };
  }

  let prisma;
  try {
    prisma = (await import("./db")).default;
  } catch(err) {
    console.error("[cluster-secrets] DB import failed:", err);
    return { synced: false, keys: [], error: "DB not available" };
  }

  // Fetch all variables matching secret_<ns>_<name>_*
  const prefix = `secret_${ns}_${name}_`;
  console.log(`[cluster-secrets] Querying DB for prefix: ${prefix}`);
  const vars = await prisma.variable.findMany({
    where: { key: { startsWith: prefix }, category: "secret" },
    orderBy: { key: "asc" },
  });

  const keys: string[] = [];

  for (const v of vars) {
    const parsed = parseSecretKey(v.key);
    if (parsed) keys.push(parsed.key);
  }

  if (keys.length === 0) {
    // No keys → delete the K8s Secret if it exists
    await runKubectl(["delete", "secret", name, "-n", ns, "--ignore-not-found"]);
    return { synced: true, keys: [] };
  }

  // Ensure namespace exists
  const nsYaml = await runKubectl([
    "create", "namespace", ns, "--dry-run=client", "-o", "yaml",
  ]);
  if (nsYaml) {
    await kubectlApply(nsYaml);
  }

  // Build --from-literal args as separate array elements
  const args = [
    "create", "secret", "generic", name, "-n", ns,
    "--dry-run=client", "-o", "yaml",
  ];
  for (const v of vars) {
    const parsed = parseSecretKey(v.key);
    if (!parsed) continue;
    args.push(`--from-literal=${parsed.key}=${v.value}`);
  }

  // Step 1: Generate YAML
  const yaml = await runKubectl(args);
  if (!yaml) {
    console.error(`[cluster-secrets] Failed to generate Secret YAML for ${ns}/${name}`);
    return { synced: false, keys, error: "Failed to generate YAML" };
  }

  // Step 2: Apply YAML
  const applied = await kubectlApply(yaml);
  if (!applied) {
    console.error(`[cluster-secrets] Failed to apply Secret ${ns}/${name}`);
    return { synced: false, keys, error: "kubectl apply failed" };
  }

  // Annotate for FluxCD prune protection
  await runKubectl([
    "annotate", "secret", name, "-n", ns,
    "kustomize.toolkit.fluxcd.io/prune=disabled", "--overwrite",
  ]);

  console.log(`[cluster-secrets] Synced Secret ${ns}/${name} with keys: ${keys.join(", ")}`);
  return { synced: true, keys };
}

/**
 * Remove a single key from a K8s Secret. If no keys remain after removal,
 * the entire Secret is deleted.
 */
export async function removeSecretKeyFromCluster(
  ns: string,
  name: string,
  keyToRemove: string
): Promise<{ synced: boolean; remainingKeys: string[]; error?: string }> {
  if (!hasLocalKubectl()) {
    return { synced: false, remainingKeys: [], error: "No local kubeconfig found" };
  }

  let prisma;
  try {
    prisma = (await import("./db")).default;
  } catch {
    return { synced: false, remainingKeys: [], error: "DB not available" };
  }

  const prefix = `secret_${ns}_${name}_`;
  const vars = await prisma.variable.findMany({
    where: { key: { startsWith: prefix }, category: "secret" },
    orderBy: { key: "asc" },
  });

  const remainingKeys: string[] = [];

  for (const v of vars) {
    const parsed = parseSecretKey(v.key);
    if (parsed && parsed.key !== keyToRemove) {
      remainingKeys.push(parsed.key);
    }
  }

  if (remainingKeys.length === 0) {
    // Last key removed — delete the entire K8s Secret
    await runKubectl(["delete", "secret", name, "-n", ns, "--ignore-not-found"]);
    console.log(`[cluster-secrets] Deleted Secret ${ns}/${name} (no keys remaining)`);
    return { synced: true, remainingKeys: [] };
  }

  // Rebuild the Secret with remaining keys only
  const args = [
    "create", "secret", "generic", name, "-n", ns,
    "--dry-run=client", "-o", "yaml",
  ];
  for (const v of vars) {
    const parsed = parseSecretKey(v.key);
    if (!parsed || parsed.key === keyToRemove) continue;
    args.push(`--from-literal=${parsed.key}=${v.value}`);
  }

  const yaml = await runKubectl(args);
  if (!yaml) {
    return { synced: false, remainingKeys, error: "Failed to generate YAML" };
  }

  await kubectlApply(yaml);
  console.log(`[cluster-secrets] Removed key "${keyToRemove}" from Secret ${ns}/${name}, remaining: ${remainingKeys.join(", ")}`);
  return { synced: true, remainingKeys };
}

/**
 * One-time bootstrap: sync ALL secret_* variables from DB to K8s Secrets.
 * Idempotent — re-running just reapplies the same secrets.
 */
export async function syncAllSecretsToCluster(): Promise<{
  synced: number;
  errors: string[];
}> {
  const errors: string[] = [];

  if (!hasLocalKubectl()) {
    return { synced: 0, errors: ["No local kubeconfig found"] };
  }

  let prisma;
  try {
    prisma = (await import("./db")).default;
  } catch {
    return { synced: 0, errors: ["DB not available"] };
  }

  const vars = await prisma.variable.findMany({
    where: { category: "secret", key: { startsWith: "secret_" } },
    orderBy: { key: "asc" },
  });

  // Group by (namespace, name)
  const groups = new Map<string, typeof vars>();
  for (const v of vars) {
    const parsed = parseSecretKey(v.key);
    if (!parsed) continue;
    const gkey = `${parsed.namespace}/${parsed.name}`;
    if (!groups.has(gkey)) groups.set(gkey, []);
    groups.get(gkey)!.push(v);
  }

  let synced = 0;
  for (const [gkey] of groups) {
    const [ns, name] = gkey.split("/");
    const result = await syncSecretToCluster(ns, name);
    if (result.synced) {
      synced++;
    } else if (result.error) {
      errors.push(`${ns}/${name}: ${result.error}`);
    }
  }

  if (synced > 0 || errors.length > 0) {
    console.log(
      `[cluster-secrets] Bootstrap: synced ${synced} Secret(s)` +
      (errors.length > 0 ? `, ${errors.length} error(s): ${errors.join("; ")}` : "")
    );
  }

  return { synced, errors };
}

// =============================================================================
// Module-level bootstrap (runs once on first import)
// =============================================================================

const _global = globalThis as typeof globalThis & {
  __clusterSecretsBootstrapped?: boolean;
};

if (!_global.__clusterSecretsBootstrapped && hasLocalKubectl()) {
  _global.__clusterSecretsBootstrapped = true;
  // Fire bootstrap sync in the background — don't block module loading
  syncAllSecretsToCluster().catch((err) => {
    console.error("[cluster-secrets] Bootstrap sync failed:", err);
  });
}
