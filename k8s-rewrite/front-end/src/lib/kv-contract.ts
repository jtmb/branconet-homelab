import { SecretError, validateTarget } from "./cluster-secrets";

export class KvError extends SecretError {}
export class KvMutationError extends KvError {
  constructor(status: number, message: string, readonly operationId: string, readonly outcome: string) { super(status, message); }
}
export const KV_ACTIONS = ["list", "read", "create", "update", "delete", "rollback", "reconcile", "destroy", "export", "rotate"] as const;
export type KvAction = typeof KV_ACTIONS[number];
export type KvScope = { mountId: string; path: string };
export type KvRule = { mountId: string | null; prefix: string; effect: string; actions: string };
export type KvActor = { id: string; sessionVersion: number; identityId?: string };
export const KV_BODY_BYTES = 512 * 1024;
// Complete policy/legacy acknowledgements contain up to 10,000 exact 253-byte aliases.
// Only fresh human administrators on the named strict metadata commit routes use this limit.
export const KV_ADMIN_METADATA_BODY_BYTES = 3 * 1024 * 1024;
export const KV_VALUE_BYTES = 256 * 1024;

// Reject alternate spellings instead of silently normalizing policy inputs.
export function logicalPath(value: unknown, allowRoot = false): string {
  if (typeof value !== "string" || value.length > 512 || value.normalize("NFC") !== value ||
    /[%\\\x00-\x20\x7f]/.test(value) || Buffer.from(value).toString("utf8") !== value || (!allowRoot && !value)) throw new KvError(400, "Invalid logical path");
  if (allowRoot && value === "") return value;
  const segments = value.split("/");
  if (segments.length > 32 || segments.some(s => !s || s === "." || s === ".." || s.length > 128))
    throw new KvError(400, "Invalid logical path");
  return value;
}

export function prefixMatches(prefix: string, path: string): boolean {
  logicalPath(prefix, true); logicalPath(path);
  return prefix === "" || path === prefix || path.startsWith(prefix + "/");
}

export function policyAllows(rules: readonly KvRule[], scope: KvScope, action: KvAction): boolean {
  logicalPath(scope.path);
  let allowed = false;
  for (const rule of rules) {
    // Corrupt policy metadata fails closed, including a malformed deny rule.
    if (!["allow", "deny"].includes(rule.effect)) throw new KvError(503, "KV policy metadata unavailable");
    const actions = parseActions(rule.actions);
    logicalPath(rule.prefix, true);
    if ((rule.mountId === null || rule.mountId === scope.mountId) && prefixMatches(rule.prefix, scope.path) && actions.includes(action)) {
      if (rule.effect === "deny") return false;
      allowed = true;
    }
  }
  return allowed;
}

export function parseActions(raw: string): KvAction[] {
  let value: unknown;
  try { value = JSON.parse(raw); } catch { throw new KvError(503, "KV policy metadata unavailable"); }
  if (!Array.isArray(value) || !value.length || value.length > KV_ACTIONS.length ||
    value.some(a => !KV_ACTIONS.includes(a)) || new Set(value).size !== value.length)
    throw new KvError(503, "KV policy metadata unavailable");
  return value as KvAction[];
}

export type KvConfig = { historyNamespace: string; retention: number; maxRetention: number; guardedAdoption: boolean };
export function kvConfig(env: Readonly<Record<string, string | undefined>> = process.env): KvConfig {
  const historyNamespace = env.BORTUS_HISTORY_NAMESPACE || "bortus-history";
  validateTarget({ namespace: historyNamespace, name: "validation", key: "validation" });
  const number = (name: string, fallback: number) => {
    const raw = env[name] ?? String(fallback);
    if (!/^[1-9][0-9]*$/.test(raw) || Number(raw) > 100) throw new KvError(503, "Invalid KV retention configuration");
    return Number(raw);
  };
  const retention = number("BORTUS_KV_RETENTION", 20), maxRetention = number("BORTUS_KV_MAX_RETENTION", 100);
  if (retention > maxRetention) throw new KvError(503, "Invalid KV retention configuration");
  if (env.BORTUS_KV_GUARDED_ADOPTION !== undefined && !["true", "false"].includes(env.BORTUS_KV_GUARDED_ADOPTION))
    throw new KvError(503, "Invalid guarded adoption configuration");
  return { historyNamespace, retention, maxRetention, guardedAdoption: env.BORTUS_KV_GUARDED_ADOPTION === "true" };
}

export function requireGuarded(config: KvConfig) {
  if (!config.guardedAdoption) throw new KvError(403, "KV value changes require externally verified guarded adoption");
}

export function metadataRevision(value: unknown): number {
  if (value === undefined || value === null) throw new KvError(428, "Metadata revision required");
  if (!Number.isSafeInteger(value) || Number(value) < 1) throw new KvError(400, "Invalid metadata revision");
  return Number(value);
}

export function fieldMapping(value: unknown, namespace: string, name: string): { field: string; key: string }[] {
  if (!Array.isArray(value) || !value.length || value.length > 64) throw new KvError(400, "Map between one and 64 fields");
  const fields = new Set<string>(), keys = new Set<string>();
  return value.map(item => {
    if (!item || typeof item !== "object" || typeof item.field !== "string" || typeof item.key !== "string" ||
      !/^[A-Za-z0-9._-]{1,253}$/.test(item.field))
      throw new KvError(400, "Invalid field mapping");
    validateTarget({ namespace, name, key: item.key });
    if (fields.has(item.field) || keys.has(item.key)) throw new KvError(400, "Field mapping must be unique");
    fields.add(item.field); keys.add(item.key);
    return { field: item.field, key: item.key };
  });
}
