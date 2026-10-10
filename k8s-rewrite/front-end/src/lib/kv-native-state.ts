import type { V1Secret } from "@kubernetes/client-node";
import type { RegisteredPath } from "./kv-registry";
import { KvError, KV_VALUE_BYTES, fieldMapping, logicalPath } from "./kv-contract";

export const STATE_ANNOTATION = "bortus.io/kv-state";
export const HISTORY_ANNOTATION = "bortus.io/kv-history";
export const CREATED_ANNOTATION = "bortus.io/kv-created";
export type VersionRef = { version: number; name: string; uid: string; operationId: string; createdAt: string; tombstone: boolean };
export type NativeOperation = { id: string; action: string; previousVersion: number; newVersion: number; historyUid?: string; historyName?: string; createdAt: string };
export type PathState = {
  id: string; mountId: string; path: string; sourceUid: string; fields: { field: string; key: string }[];
  head: number; sequence: number; tombstone: boolean; versions: VersionRef[]; operations: NativeOperation[];
};
export type NativeState = { format: 1; paths: PathState[] };
export type EncodedField = { field: string; encoding: "base64" | "utf8"; value: string };
const sameMappings = (a: { field: string; key: string }[], b: { field: string; key: string }[]) =>
  JSON.stringify([...a].sort((x,y) => x.field.localeCompare(y.field))) === JSON.stringify([...b].map(({field,key}) => ({field,key})).sort((x,y) => x.field.localeCompare(y.field)));
const integer = (n: unknown) => Number.isSafeInteger(n) && Number(n) >= 0;
export const nativeIdentity = (s: V1Secret) => {
  if (typeof s.metadata?.uid !== "string" || !s.metadata.uid || s.metadata.uid.length > 128 || typeof s.metadata.resourceVersion !== "string" || !s.metadata.resourceVersion || s.metadata.resourceVersion.length > 128) throw new KvError(503, "Native Secret identity unavailable");
  return { uid: s.metadata.uid, resourceVersion: s.metadata.resourceVersion };
};

export function base64(value: unknown): string {
  if (typeof value === "string" && value.length > Math.ceil(KV_VALUE_BYTES / 3) * 4) throw new KvError(413, "KV field exceeds 256 KiB");
  if (typeof value !== "string" || Buffer.from(value, "base64").toString("base64") !== value)
    throw new KvError(400, "Invalid canonical base64 field");
  return value;
}
export function boundedValues(data: Record<string, string>) {
  let bytes = 0;
  for (const value of Object.values(data)) { base64(value); bytes += Buffer.from(value, "base64").length; }
  if (bytes > KV_VALUE_BYTES) throw new KvError(413, "KV document exceeds 256 KiB");
  return data;
}
export function encodedValues(fields: unknown, path: Pick<RegisteredPath, "fields">): Record<string, string> {
  if (!Array.isArray(fields) || fields.length > path.fields.length) throw new KvError(400, "Invalid selected document fields");
  const seen = new Set<string>();
  const values = fields.map(item => {
    if (!item || typeof item !== "object" || typeof item.field !== "string" || typeof item.value !== "string" ||
      Object.keys(item).some(k => !["field", "encoding", "value"].includes(k)) || seen.has(item.field) || !path.fields.some(f => f.field === item.field))
      throw new KvError(400, "Invalid selected document fields");
    seen.add(item.field);
    if (item.encoding === "base64") return [item.field, base64(item.value)] as const;
    if (item.encoding !== "utf8" || Buffer.from(item.value).toString("utf8") !== item.value) throw new KvError(400, "Invalid field encoding");
    return [item.field, Buffer.from(item.value).toString("base64")] as const;
  });
  return boundedValues(Object.fromEntries(values));
}
export function selectedValues(secret: V1Secret, path: Pick<RegisteredPath, "fields">, required = false): Record<string, string> {
  const values: [string, string][] = [];
  for (const mapping of path.fields) {
    if (Object.hasOwn(secret.data || {}, mapping.key)) values.push([mapping.field, base64(secret.data![mapping.key])]);
    else if (required) throw new KvError(404, "Selected native Secret key not found");
  }
  return boundedValues(Object.fromEntries(values));
}
export const equalValues = (a: Record<string, string>, b: Record<string, string>) =>
  Object.keys(a).length === Object.keys(b).length && Object.entries(a).every(([key,value]) => Object.hasOwn(b,key) && b[key] === value);
export const exportFields = (data: Record<string, string>): EncodedField[] => Object.entries(data).sort(([a],[b]) => a.localeCompare(b)).map(([field,value]) => ({field,encoding:"base64",value}));

export function parseState(secret: V1Secret): NativeState {
  const raw = secret.metadata?.annotations?.[STATE_ANNOTATION];
  if (raw === undefined) return { format: 1, paths: [] };
  if (typeof raw !== "string" || Buffer.byteLength(raw) > 200 * 1024) throw new KvError(503, "Native KV ownership metadata unavailable");
  try {
    const state = JSON.parse(raw);
    const known = (value: object, keys: string[]) => Object.keys(value).every(key => keys.includes(key));
    if (!known(state, ["format", "paths"]) || state.format !== 1 || !Array.isArray(state.paths) || state.paths.length > 64) throw Error();
    const ids = new Set<string>(), keys = new Set<string>();
    for (const p of state.paths) {
      if (!known(p, ["id", "mountId", "path", "sourceUid", "fields", "head", "sequence", "tombstone", "versions", "operations"]) || typeof p.id !== "string" || ids.has(p.id) || typeof p.mountId !== "string" || typeof p.path !== "string" || typeof p.sourceUid !== "string" ||
        !integer(p.head) || !integer(p.sequence) || p.head > p.sequence || typeof p.tombstone !== "boolean" ||
        !Array.isArray(p.versions) || p.versions.length > 100 || !Array.isArray(p.operations) || p.operations.length > 100) throw Error();
      ids.add(p.id);
      logicalPath(p.path);
      for (const mapping of fieldMapping(p.fields, secret.metadata?.namespace || "", secret.metadata?.name || "")) {
        if (keys.has(mapping.key)) throw Error(); keys.add(mapping.key);
      }
      const versions = new Set<number>();
      for (const ref of p.versions) {
        if (!known(ref, ["version", "name", "uid", "operationId", "createdAt", "tombstone"]) || !integer(ref.version) || ref.version < 1 || ref.version > p.sequence || versions.has(ref.version) ||
          typeof ref.name !== "string" || typeof ref.uid !== "string" || !ref.uid || typeof ref.operationId !== "string" ||
          typeof ref.createdAt !== "string" || !Number.isFinite(Date.parse(ref.createdAt)) || typeof ref.tombstone !== "boolean") throw Error();
        versions.add(ref.version);
      }
      if (p.head && !versions.has(p.head) || !p.head && !p.tombstone || p.head && p.versions.find((v: VersionRef) => v.version === p.head).tombstone !== p.tombstone) throw Error();
      for (const op of p.operations) if (!known(op, ["id", "action", "previousVersion", "newVersion", "historyUid", "historyName", "createdAt"]) || typeof op.id !== "string" || typeof op.action !== "string" || !integer(op.previousVersion) || !integer(op.newVersion) || typeof op.createdAt !== "string") throw Error();
    }
    return state as NativeState;
  } catch { throw new KvError(503, "Native KV ownership metadata unavailable"); }
}
export function ownedPath(secret: V1Secret, path: RegisteredPath, state = parseState(secret)): PathState | undefined {
  const current = state.paths.find(p => p.id === path.id);
  if (current && (current.sourceUid !== nativeIdentity(secret).uid || current.mountId !== path.mountId || current.path !== path.path || !sameMappings(current.fields, path.fields)))
    throw new KvError(409, "Canonical Secret ownership changed; recovery required");
  if (state.paths.some(p => p.id !== path.id && p.fields.some(f => path.fields.some(own => own.key === f.key))))
    throw new KvError(409, "Selected native keys already have another owner");
  return current;
}
export function stateBody(secret: V1Secret, state: NativeState, path: RegisteredPath, values?: Record<string, string>): V1Secret {
  const annotation = JSON.stringify(state);
  if (Buffer.byteLength(annotation) > 200 * 1024) throw new KvError(413, "Native KV ownership metadata exceeds the size limit");
  const data = Object.fromEntries(Object.entries(secret.data || {}));
  if (values) for (const mapping of path.fields) {
    if (Object.hasOwn(values, mapping.field)) Object.defineProperty(data, mapping.key, { value: values[mapping.field], enumerable: true, configurable: true, writable: true });
    else delete data[mapping.key];
  }
  const body = { ...secret, metadata: { ...secret.metadata, annotations: { ...secret.metadata?.annotations, [STATE_ANNOTATION]: annotation } }, data };
  delete body.stringData;
  if (Buffer.byteLength(JSON.stringify(body)) > 900 * 1024) throw new KvError(413, "Canonical Secret exceeds the application size limit");
  return body;
}
export function historyBody(path: RegisteredPath, sourceUid: string, namespace: string, name: string, version: number, operationId: string, values: Record<string,string>, tombstone: boolean): V1Secret {
  return { apiVersion: "v1", kind: "Secret", type: "Opaque", immutable: true,
    metadata: { namespace, name, labels: { "bortus.io/kv-history": "v1" }, annotations: {
      [HISTORY_ANNOTATION]: JSON.stringify({ format: 1, pathId: path.id, mountId: path.mountId, path: path.path, namespace: path.namespace, name: path.name, sourceUid, version, operationId,
        fields: path.fields.map(({field,key}) => ({field,key})), tombstone }),
    } }, data: Object.fromEntries(Object.entries(boundedValues(values))) };
}
export function historyValues(secret: V1Secret, path: RegisteredPath, sourceUid: string, ref: VersionRef): Record<string,string> {
  let owned: any;
  try { owned = JSON.parse(secret.metadata?.annotations?.[HISTORY_ANNOTATION] || ""); } catch { throw new KvError(409, "Owned history identity changed; recovery required"); }
  if (secret.immutable !== true || secret.type !== "Opaque" || nativeIdentity(secret).uid !== ref.uid || secret.metadata?.name !== ref.name ||
    owned.format !== 1 || owned.pathId !== path.id || owned.mountId !== path.mountId || owned.path !== path.path || owned.namespace !== path.namespace || owned.name !== path.name ||
    owned.sourceUid !== sourceUid || owned.version !== ref.version || owned.operationId !== ref.operationId || owned.tombstone !== ref.tombstone || !Array.isArray(owned.fields) || !sameMappings(owned.fields, path.fields) ||
    Object.keys(secret.data || {}).some(field => !path.fields.some(f => f.field === field)) || ref.tombstone && Object.keys(secret.data || {}).length)
    throw new KvError(409, "Owned history identity changed; recovery required");
  return boundedValues(Object.fromEntries(Object.entries(secret.data || {})));
}
