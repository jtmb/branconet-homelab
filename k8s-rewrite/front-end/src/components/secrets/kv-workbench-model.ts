/** Browser-only contracts. Never import the native engine or registry into this module. */
export type KvPermission = "list" | "read" | "create" | "update" | "delete" | "rollback" | "reconcile" | "export";
export type KvCapabilities = {
  pathId: string; revision: number; permissions: Partial<Record<KvPermission, boolean>>;
  nativeMutationEnabled: boolean; initializationAllowed: boolean;
};
export type KvSelectedPath = {
  id: string; mountId: string; path: string; namespace: string; name: string; revision: number;
  fields: readonly { field: string; key: string }[];
};
export type KvStatus = { pathId: string; resourceVersion: string; adopted: boolean; head: number; tombstone: boolean; guardedAdoption: boolean };
export type EncodedField = { field: string; encoding: "utf8" | "base64"; value: string };
export type KvValues = { pathId: string; resourceVersion: string; head: number; version: number; tombstone: boolean; fields: EncodedField[] };
export type RevisionCapture = { resourceVersion: string; expectedHead: number; pathRevision: number };
export type FieldDraft = EncodedField & { present: boolean; emptyConfirmed: boolean };
export type TransferDocument = { mountId: string; path: string; namespace: string; name: string; mappings: { field: string; key: string }[]; fields: EncodedField[]; sourceVersion?: number };
export type TransferBundle = { format: "bortus-kv"; version: 1; documents: TransferDocument[] };
export type ImportPlan = {
  documentIndex: number; outcome: "ready" | "refused"; status: number; pathId?: string | null; revision?: number | null;
  resourceVersion?: string; expectedHead?: number; requiresOverwrite?: boolean; path?: string; namespace?: string; name?: string;
};
export type ImportPreview = { format: "bortus-kv-import-preview"; version: 1; guardedAdoption: boolean; plans: ImportPlan[] };
export type ImportOutcome = { documentIndex: number; pathId: string | null; status: number; outcome: string; operationId?: string; head?: number };
export type ImportResult = { success: boolean; atomic: false; outcomes: ImportOutcome[] };
export function captureRevision(path: KvSelectedPath, native: { resourceVersion: string; head: number }): RevisionCapture {
  return Object.freeze({ resourceVersion: native.resourceVersion, expectedHead: native.head, pathRevision: path.revision });
}
/** Metadata refresh may pause an action, but never upgrade its frozen capture. */
export function captureMatchesMetadata(capture: RevisionCapture, path: KvSelectedPath, status: KvStatus | undefined, nativeAbsent: boolean): boolean {
  return capture.pathRevision === path.revision && (status
    ? status.pathId === path.id && capture.resourceVersion === status.resourceVersion && capture.expectedHead === status.head
    : nativeAbsent && capture.resourceVersion === "absent" && capture.expectedHead === 0);
}
export function canonicalBase64(field: EncodedField): string {
  if (field.encoding === "base64") {
    if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(field.value)) throw new Error("Use canonical base64.");
    const decoded = atob(field.value);
    if (btoa(decoded) !== field.value) throw new Error("Use canonical base64.");
    return field.value;
  }
  const bytes = new TextEncoder().encode(field.value);
  if (new TextDecoder("utf-8", { fatal: true }).decode(bytes) !== field.value) throw new Error("Use valid UTF-8.");
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}
export function convertEncoding(field: EncodedField, encoding: EncodedField["encoding"]): string {
  const base64 = canonicalBase64(field);
  return encoding === "base64" ? base64 : new TextDecoder("utf-8", { fatal: true }).decode(Uint8Array.from(atob(base64), c => c.charCodeAt(0)));
}
export function draftsFor(path: KvSelectedPath, values: EncodedField[]): FieldDraft[] {
  const byName = new Map(values.map(value => [value.field, value]));
  return path.fields.map(({ field }) => ({ ...(byName.get(field) ?? { field, encoding: "utf8" as const, value: "" }), present: byName.has(field), emptyConfirmed: false }));
}
/** Write-without-read replacement starts from metadata and blank input, never presumed current bytes. */
export function replacementDrafts(path: KvSelectedPath): FieldDraft[] {
  return draftsFor(path, []).map(draft => ({ ...draft, present: true }));
}
export function draftChange(drafts: FieldDraft[], original: EncodedField[]): { fields: EncodedField[]; changed: boolean; error: string } {
  const before = new Map(original.map(field => [field.field, canonicalBase64(field)]));
  const fields: EncodedField[] = []; let bytes = 0;
  try {
    for (const draft of drafts) {
      if (!draft.present) continue;
      const encoded = canonicalBase64(draft);
      if (!encoded && before.get(draft.field) !== "" && !draft.emptyConfirmed) return { fields: [], changed: false, error: "Confirm each intentional empty value." };
      bytes += atob(encoded).length;
      if (bytes > 256 * 1024) return { fields: [], changed: false, error: "Document exceeds 256 KiB." };
      fields.push({ field: draft.field, encoding: draft.encoding, value: draft.value });
    }
    const after = new Map(fields.map(field => [field.field, canonicalBase64(field)]));
    return { fields, changed: before.size !== after.size || [...after].some(([name, value]) => before.get(name) !== value), error: "" };
  } catch { return { fields: [], changed: false, error: "A field needs valid UTF-8 or canonical base64." }; }
}
/** One-MiB bounded in-memory parsing. Errors deliberately omit input. Server validates ownership/policies. */
export function parseTransfer(text: string): TransferBundle {
  if (new TextEncoder().encode(text).length > 1024 * 1024) throw new Error("Transfer exceeds one MiB.");
  let bundle: TransferBundle;
  try { bundle = JSON.parse(text); } catch { throw new Error("Use a valid BORTUS v1 JSON bundle."); }
  if (!bundle || bundle.format !== "bortus-kv" || bundle.version !== 1 || !Array.isArray(bundle.documents) || !bundle.documents.length || bundle.documents.length > 100)
    throw new Error("Use a BORTUS v1 bundle with one to 100 documents.");
  for (const doc of bundle.documents) {
    if (!doc || [doc.mountId, doc.path, doc.namespace, doc.name].some(value => typeof value !== "string") || !Array.isArray(doc.mappings) || !doc.mappings.length || doc.mappings.length > 64 ||
      doc.mappings.some(mapping => !mapping || typeof mapping.field !== "string" || typeof mapping.key !== "string") || !Array.isArray(doc.fields) || doc.fields.length > 64 ||
      doc.fields.some(field => !field || typeof field.field !== "string" || typeof field.value !== "string" || !["utf8", "base64"].includes(field.encoding))) throw new Error("Invalid transfer document metadata or fields.");
    const changed = draftChange(doc.fields.map(field => ({ ...field, present: true, emptyConfirmed: true })), []);
    if (changed.error) throw new Error(changed.error);
  }
  return bundle;
}
/** Each invalidation aborts and fences late responses, even when a transport ignores abort. */
export class ValueFence {
  private epoch = 0;
  private requests = new Set<AbortController>();
  invalidate() { this.epoch++; for (const controller of this.requests) controller.abort(); }
  begin() {
    const epoch = this.epoch, controller = new AbortController(); this.requests.add(controller);
    return { signal: controller.signal, current: () => epoch === this.epoch && !controller.signal.aborted,
      finish: () => this.requests.delete(controller), abort: () => controller.abort() };
  }
}
export class WorkbenchFailure extends Error {
  constructor(readonly status: number, readonly operationId?: string, readonly outcome?: string) {
    super(status === 409 ? "Conflict or external drift. Clear drafts, refresh metadata, and inspect before opening a new action."
      : status === 401 || status === 403 ? "Access changed. Values and drafts have been cleared."
      : status === 428 ? "A captured revision or acknowledgement is missing."
      : "Request failed. Inspect metadata and operation outcome before retrying.");
  }
}
export async function workbenchRequest<T>(url: string, init: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store", credentials: "same-origin" });
  // Never reflect arbitrary response error text: it may contain native data or input.
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const operationId = typeof body.operationId === "string" && /^[0-9a-f-]{36}$/.test(body.operationId) ? body.operationId : undefined;
    const outcome = ["pending", "committed", "conflict", "ambiguous", "recovery-required"].includes(body.outcome) ? body.outcome : undefined;
    throw new WorkbenchFailure(response.status, operationId, outcome);
  }
  return response.json() as Promise<T>;
}
