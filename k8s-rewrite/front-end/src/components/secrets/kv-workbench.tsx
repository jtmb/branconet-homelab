"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Modal } from "../ui/modal";
import { useQuery, useSession } from "../../lib/use-query";
import {
  ValueFence, WorkbenchFailure, captureRevision, convertEncoding, draftChange, draftsFor, parseTransfer, replacementDrafts, workbenchRequest,
  type EncodedField, type FieldDraft, type ImportOutcome, type ImportPreview, type ImportResult, type KvCapabilities,
  type KvPermission, type KvSelectedPath, type KvStatus, type KvValues, type RevisionCapture, type TransferBundle,
} from "./kv-workbench-model";

export type { KvCapabilities, KvSelectedPath } from "./kv-workbench-model";
export interface KvWorkbenchProps {
  /** Explicit registered mapping, never an inferred native target. */
  path: KvSelectedPath;
  /** Fresh parent capability ceiling; the workbench shares that endpoint's query lifecycle. */
  capabilities: KvCapabilities | null;
  onClose: () => void;
  /** Metadata invalidation only. No values are passed to the parent. */
  onMetadataRefresh: () => void;
  returnFocus?: () => void;
}
type History = { pathId: string; resourceVersion: string; head: number; items: { version: number; createdAt: string; tombstone: boolean }[] };
type Adoption = { pathId: string; resourceVersion: string; expectedHead: number; fields: { field: string; key: string }[]; legacyAliases: { alias: string; namespace: string; name: string; key: string }[]; guardedAdoption: boolean };
type Edit = { capture: RevisionCapture; original: EncodedField[]; drafts: FieldDraft[]; create: boolean; replacement: boolean };
type Confirmation = { kind: "delete" | "rollback" | "reconcile" | "export"; capture: RevisionCapture; version?: number };
type Transfer = { bundle: TransferBundle; preview: ImportPreview; overwrites: number[] };
const input = "w-full min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400";
const button = "rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-3 py-2 text-sm text-indigo-200 hover:bg-indigo-500/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 disabled:cursor-not-allowed disabled:opacity-40";
const PAGE = 20;

/** Unmount on explicit mapping changes so no prior document can appear under a new heading. */
export function KvWorkbench(props: KvWorkbenchProps) {
  return <Workbench key={JSON.stringify([props.path.id, props.path.namespace, props.path.name, props.path.fields])} {...props} />;
}
export default KvWorkbench;

function Workbench({ path, capabilities, onClose, onMetadataRefresh, returnFocus }: KvWorkbenchProps) {
  const session = useSession();
  const capabilityQuery = useQuery<KvCapabilities>(`/api/kv/paths/${encodeURIComponent(path.id)}/capabilities`);
  const { refetch: refetchCapabilities } = capabilityQuery;
  const { refetch: refetchSession } = session;
  const [blockedAt, setBlockedAt] = useState<number>();
  const capabilityStamp = useRef(capabilityQuery.updatedAt); capabilityStamp.current = capabilityQuery.updatedAt;
  const caps = capabilities?.pathId === path.id && !capabilityQuery.error && !capabilityQuery.stale && (blockedAt === undefined || capabilityQuery.updatedAt > blockedAt)
    ? capabilityQuery.data ?? null : null;
  const [status, setStatus] = useState<KvStatus>();
  const [nativeAbsent, setNativeAbsent] = useState(false);
  const [history, setHistory] = useState<History>(), [historyPage, setHistoryPage] = useState(0);
  const [view, setView] = useState<KvValues>();
  const [edit, setEdit] = useState<Edit>();
  const [adoption, setAdoption] = useState<{ preview: Adoption; capture: RevisionCapture }>();
  const [aliasPage, setAliasPage] = useState(0);
  const [confirmation, setConfirmation] = useState<Confirmation>();
  const [exact, setExact] = useState(""), [ack, setAck] = useState(false);
  const [importOpen, setImportOpen] = useState(false), [importText, setImportText] = useState("");
  const [transfer, setTransfer] = useState<Transfer>(), [outcomes, setOutcomes] = useState<ImportOutcome[]>([]);
  const [transferPage, setTransferPage] = useState(0);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const [operation, setOperation] = useState<{ id: string; outcome?: string }>();
  const fence = useRef(new ValueFence()), mounted = useRef(false), running = useRef(false);
  const nativeEpoch = useRef(0);
  const heading = useRef<HTMLHeadingElement>(null), refreshButton = useRef<HTMLButtonElement>(null);
  const capabilityFresh = !!caps && Date.now() - capabilityQuery.updatedAt < 15000 && caps.pathId === path.id && caps.revision === path.revision;
  const access = `${session.data?.username ?? ""}:${session.canKvWrite}:${capabilityFresh}:${JSON.stringify(caps?.permissions)}:${caps?.initializationAllowed}:${caps?.nativeMutationEnabled}`;
  const accessRef = useRef(access);
  if (accessRef.current !== access) { fence.current.invalidate(); accessRef.current = access; }
  const allowed = (permission: KvPermission, mutation = false) => session.canKvWrite && capabilityFresh && caps?.permissions[permission] === true && (!mutation || caps.nativeMutationEnabled);
  const refreshParent = useRef(onMetadataRefresh); refreshParent.current = onMetadataRefresh;
  const clearSensitive = useCallback(() => {
    fence.current.invalidate(); setView(undefined); setEdit(undefined); setAdoption(undefined); setConfirmation(undefined);
    setExact(""); setAck(false); setImportOpen(false); setImportText(""); setTransfer(undefined);
  }, []);
  useEffect(() => {
    mounted.current = true; const currentFence = fence.current;
    const ended = () => { clearSensitive(); setBlockedAt(capabilityStamp.current); };
    const hidden = () => { if (document.visibilityState === "hidden") clearSensitive(); };
    window.addEventListener("bortus-session-ended", ended);
    window.addEventListener("pagehide", clearSensitive);
    document.addEventListener("visibilitychange", hidden);
    return () => { mounted.current = false; currentFence.invalidate(); window.removeEventListener("bortus-session-ended", ended); window.removeEventListener("pagehide", clearSensitive); document.removeEventListener("visibilitychange", hidden); };
  }, [clearSensitive]);
  useEffect(() => { clearSensitive(); }, [access, clearSensitive]);
  // Shared timestamps gate access; an unchanged successful read never changes a frozen action capture.
  const request = useCallback(async <T,>(url: string, init: RequestInit, success: (result: T) => void) => {
    if (running.current) return;
    running.current = true; setBusy(true); setMessage("");
    const ticket = fence.current.begin();
    const timeout = setTimeout(() => {
      if (mounted.current && ticket.current()) {
        clearSensitive();
        if (init.method && init.method !== "GET") { setStatus(undefined); refreshParent.current(); }
        setMessage("Request timed out. Refresh metadata and inspect the operation before retrying.");
      }
      ticket.abort();
    }, 40000);
    try {
      const result = await workbenchRequest<T>(url, { ...init, signal: ticket.signal });
      if (mounted.current && ticket.current()) success(result);
    } catch (error) {
      if (!mounted.current || !ticket.current()) return;
      if (error instanceof WorkbenchFailure) {
        if (url === `/api/kv/paths/${encodeURIComponent(path.id)}/status`) { setStatus(undefined); setNativeAbsent(error.status === 404); }
        if (error.status === 401 || error.status === 403) { clearSensitive(); setBlockedAt(capabilityStamp.current); refetchCapabilities(); refetchSession(); }
        else if (init.method && init.method !== "GET") { clearSensitive(); setStatus(undefined); refreshParent.current(); }
        setMessage(error.message);
        if (error.operationId) setOperation({ id: error.operationId, outcome: error.outcome });
      } else setMessage("Request unavailable. Refresh metadata and inspect the result before retrying.");
    } finally {
      clearTimeout(timeout); ticket.finish(); running.current = false;
      if (mounted.current) setBusy(false);
    }
  }, [clearSensitive, path.id, refetchCapabilities, refetchSession]);
  const endpoint = `/api/kv/paths/${encodeURIComponent(path.id)}`;
  const refresh = useCallback(() => {
    if (running.current) return;
    nativeEpoch.current++;
    setStatus(undefined); setNativeAbsent(false);
    void request<KvStatus>(endpoint + "/status", {}, result => { setStatus(result); setNativeAbsent(false); refreshParent.current(); });
  }, [endpoint, request]);
  // Browsing reads only status/capability metadata. Never fetch adoption or values on mount.
  useEffect(() => {
    const controller = new AbortController(); let active = true;
    const epoch = nativeEpoch.current;
    const timeout = setTimeout(() => controller.abort(), 20000);
    void workbenchRequest<KvStatus>(endpoint + "/status", { signal: controller.signal }).then(result => { if (active && epoch === nativeEpoch.current) { setStatus(result); setNativeAbsent(false); } })
      .catch(error => { if (active && epoch === nativeEpoch.current) { setNativeAbsent(error instanceof WorkbenchFailure && error.status === 404); setMessage(error instanceof WorkbenchFailure ? error.message : "Native metadata unavailable. Refresh explicitly."); } })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; controller.abort(); clearTimeout(timeout); };
  }, [endpoint]);
  function rememberFocus() { /* The stable Refresh metadata control receives focus after an inline action closes. */ }
  function returnToMetadata() { requestAnimationFrame(() => refreshButton.current?.focus()); }
  function focusPanel() { requestAnimationFrame(() => heading.current?.focus()); }
  function cancel() {
    clearSensitive(); setMessage("Display and draft cleared." + (busy ? " A sent request may still commit; refresh and inspect its outcome." : ""));
    returnToMetadata();
  }
  function close() { clearSensitive(); onClose(); }
  function startConfirmation(kind: Confirmation["kind"], version?: number) {
    const permission = kind === "rollback" ? "rollback" : kind === "delete" ? "delete" : kind;
    if (!status || !allowed(permission, kind !== "export") || busy) return;
    rememberFocus(); clearSensitive(); setConfirmation({ kind, version, capture: captureRevision(path, status) }); focusPanel();
  }
  function mutate(url: string, method: string, body: object) {
    nativeEpoch.current++; setStatus(undefined); setNativeAbsent(false);
    setOperation(undefined);
    void request<{ operationId: string; outcome: string; head: number }>(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, result => {
      clearSensitive(); setOperation({ id: result.operationId, outcome: result.outcome }); setStatus(undefined); setNativeAbsent(false); setHistory(undefined);
      setMessage(`Operation ${result.outcome}. Refresh metadata to inspect the new head.`); refreshParent.current(); returnToMetadata();
    });
  }
  function openEdit(create = false, replacement = false) {
    if (!allowed(create ? "create" : "update", true) || !create && !replacement && !allowed("read") || create && (!caps?.initializationAllowed || !status && !nativeAbsent) || replacement && !status?.adopted || busy) return;
    rememberFocus(); clearSensitive();
    if (replacement && status) {
      setEdit({ capture: captureRevision(path, status), original: [], drafts: replacementDrafts(path), create: false, replacement: true }); focusPanel(); return;
    }
    if (create) {
      const native = status ?? { resourceVersion: "absent", head: 0 };
      setEdit({ capture: captureRevision(path, native), original: [], drafts: draftsFor(path, []), create: true, replacement: false }); focusPanel(); return;
    }
    void request<KvValues>(endpoint + "/data", {}, result => {
      setEdit({ capture: captureRevision(path, result), original: result.fields, drafts: draftsFor(path, result.fields), create: false, replacement: false }); focusPanel();
    });
  }
  function reveal(version?: number) {
    if (!allowed("read") || busy) return;
    clearSensitive(); void request<KvValues>(endpoint + (version === undefined ? "/data" : `/versions/${version}/data`), {}, result => setView(result));
  }
  function openAdoption() {
    if (!caps?.initializationAllowed || !allowed("create", true) || busy) return;
    rememberFocus(); clearSensitive();
    void request<Adoption>(endpoint + "/adopt", {}, preview => {
      setAdoption({ preview, capture: captureRevision(path, { resourceVersion: preview.resourceVersion, head: preview.expectedHead }) }); setAliasPage(0); focusPanel();
    });
  }
  function confirmAction() {
    if (!confirmation || !ack || exact !== path.path || busy) return;
    const { kind, capture, version } = confirmation;
    if (kind === "export") {
      if (!allowed("export")) return;
      void request<TransferBundle>("/api/kv/export", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selections: [{ pathId: path.id, ...(version ? { version } : {}) }], confirmCredentials: true }) }, bundle => {
        // Dedicated explicit export creates only an ephemeral Blob; its URL is revoked immediately.
        const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" }));
        const anchor = document.createElement("a"); anchor.href = url; anchor.download = "bortus-kv-export.json";
        document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 0);
        clearSensitive(); setMessage("Export requested. The downloaded file contains credential values; protect it.");
      });
      return;
    }
    if (!allowed(kind, true)) return;
    mutate(endpoint + (kind === "delete" ? "/data" : `/${kind}`), kind === "delete" ? "DELETE" : "POST",
      { ...capture, ...(kind === "delete" ? { confirmPath: path.path } : {}), ...(version ? { version } : {}) });
  }
  function previewImport() {
    if (busy || !session.canKvWrite || !capabilityFresh) return;
    let bundle: TransferBundle;
    try { bundle = parseTransfer(importText); } catch (error) { setMessage(error instanceof Error ? error.message : "Invalid bundle."); return; }
    void request<ImportPreview>("/api/kv/import/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ bundle }) }, preview => {
      setTransfer({ bundle, preview, overwrites: [] }); setImportText(""); setTransferPage(0); setAck(false); focusPanel();
    });
  }
  function commitImport() {
    if (!transfer || !ack || busy || !session.canKvWrite || !capabilityFresh || !transfer.preview.guardedAdoption ||
      transfer.preview.plans.some(plan => plan.outcome !== "ready" || plan.requiresOverwrite && !transfer.overwrites.includes(plan.documentIndex))) return;
    const plans = transfer.preview.plans.map(plan => ({ documentIndex: plan.documentIndex, pathId: plan.pathId, revision: plan.revision,
      resourceVersion: plan.resourceVersion, expectedHead: plan.expectedHead, overwrite: transfer.overwrites.includes(plan.documentIndex) }));
    setOperation(undefined);
    nativeEpoch.current++; setStatus(undefined); setNativeAbsent(false);
    void request<ImportResult>("/api/kv/import", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bundle: transfer.bundle, plans, confirmCredentials: true }) }, result => {
      clearSensitive(); setOutcomes(result.outcomes); setTransferPage(0); setStatus(undefined); setHistory(undefined);
      setMessage(result.success ? "All documents committed. Refresh metadata." : "Batch partially committed or refused. Inspect every outcome before preparing a fresh preview."); refreshParent.current();
    });
  }
  const changed = edit ? draftChange(edit.drafts, edit.original) : undefined;
  const replacementIntent = !!edit?.replacement && (changed?.changed || edit.drafts.every(draft => !draft.present));
  const panel = edit || adoption || confirmation || importOpen;
  const capture = edit?.capture ?? adoption?.capture ?? confirmation?.capture;
  const capturedMetadataChanged = !!capture && capture.pathRevision !== path.revision;
  return <Modal open onClose={close} returnFocus={returnFocus} title={`KV · ${path.path}`} description={`${path.namespace}/${path.name} · ${path.fields.length} explicitly mapped fields`}>
    <div className="space-y-4 text-zinc-100">
      <div className="flex flex-wrap gap-2">
        <button ref={refreshButton} className={button} disabled={busy} onClick={refresh}>Refresh metadata</button>
        <button className={button} onClick={cancel}>Clear display and draft</button>
      </div>
      <div role="status" aria-live="polite" className="break-words text-sm text-zinc-300">{busy ? "Request in progress…" : message}</div>
      {operation && <p className="break-all text-sm text-zinc-400">Operation {operation.id}: {operation.outcome ?? "inspect outcome"}. <button className={button} disabled={busy} onClick={() => {
        void request<{ id: string; outcome: string }>(`/api/kv/operations/${encodeURIComponent(operation.id)}`, {}, result => setOperation({ id: result.id, outcome: result.outcome }));
      }}>Inspect operation</button></p>}
      {!capabilityFresh && <p className="text-sm text-amber-300">Checking fresh permissions. Value controls are paused.</p>}
      {!session.canKvWrite && <p className="text-sm text-zinc-400">Metadata only. Fresh write access and path policy are required for values.</p>}
      {status && <p className="break-words text-sm text-zinc-400">{status.adopted ? `Head ${status.head} · ${status.tombstone ? "soft-deleted" : "active"}` : "Registered; explicit adoption or initialization required"} · native revision {status.resourceVersion}</p>}
      {!status && <p className="text-sm text-amber-300">{nativeAbsent ? "Native target absent in the latest metadata request. Explicit initialization requires fresh create permission." : "Native status unavailable. Refresh metadata before opening a new native action."}</p>}
      {capture && <p className="break-all rounded-lg border border-zinc-700 p-3 text-sm">Captured head {capture.expectedHead}, native revision {capture.resourceVersion}, path revision {capture.pathRevision}. {capturedMetadataChanged && "Metadata changed. Cancel and reopen the action."}</p>}
      {!panel && <>
        <div className="flex flex-wrap gap-2">
          {allowed("read") && status?.adopted && <button className={button} disabled={busy} onClick={() => reveal()}>Reveal current fields</button>}
          {allowed("update", true) && allowed("read") && status?.adopted && <button className={button} disabled={busy} onClick={() => openEdit()}>Edit grouped fields</button>}
          {allowed("update", true) && !allowed("read") && status?.adopted && <button className={button} disabled={busy} onClick={() => openEdit(false, true)}>Replace complete document without reveal</button>}
          {allowed("create", true) && caps?.initializationAllowed && !status?.adopted && (status || nativeAbsent) && <>
            {status && <button className={button} disabled={busy} onClick={openAdoption}>Preview explicit adoption</button>}
            <button className={button} disabled={busy} onClick={() => openEdit(true)}>Initialize new native document</button>
          </>}
          {allowed("delete", true) && status?.adopted && !status.tombstone && <button className={button} disabled={busy} onClick={() => startConfirmation("delete")}>Soft-delete document</button>}
          {allowed("reconcile", true) && status?.adopted && <button className={button} disabled={busy} onClick={() => startConfirmation("reconcile")}>Capture external drift</button>}
          {allowed("export") && status?.adopted && <button className={button} disabled={busy} onClick={() => startConfirmation("export")}>Export current document</button>}
          {session.canKvWrite && capabilityFresh && (allowed("update", true) || caps?.initializationAllowed) && <button className={button} disabled={busy} onClick={() => {
            rememberFocus(); clearSensitive(); setOutcomes([]); setImportOpen(true); focusPanel();
          }}>Import bundle</button>}
        </div>
        {view && allowed("read") && <section aria-label={`Revealed version ${view.version}`} className="space-y-3 rounded-lg border border-amber-500/30 p-3">
          <p className="text-sm text-amber-200">Version {view.version}{view.tombstone ? " · tombstone" : ""} · values in this display only</p>
          {view.fields.map((field, index) => <label key={field.field} className="block text-sm">{field.field} · {field.encoding}{field.value === "" ? " · empty bytes" : ""}
            <textarea id={`kv-revealed-${index}`} aria-label={`${field.field} · ${field.encoding}`} className={`${input} mt-1 font-mono`} readOnly rows={3} value={field.value} autoComplete="off" spellCheck={false} />
          </label>)}
          {!view.fields.length && <p className="text-sm">No managed fields in this version.</p>}
        </section>}
        <section aria-label="Immutable version history" className="space-y-3">
          <button className={button} disabled={busy || !caps?.permissions.list || !capabilityFresh} onClick={() => {
            void request<History>(endpoint + "/versions", {}, result => { setHistory(result); setHistoryPage(0); });
          }}>Browse immutable history metadata</button>
          {history && <>
            <div className="max-w-full overflow-x-auto rounded-lg border border-zinc-800"><table className="w-full text-left text-sm"><caption className="p-2 text-left">Committed versions · rollback and restore create a new version</caption>
              <thead><tr><th className="p-2">Version</th><th className="p-2">Created</th><th className="p-2">State</th><th className="p-2">Actions</th></tr></thead>
              <tbody>{[...history.items].reverse().slice(historyPage * PAGE, (historyPage + 1) * PAGE).map(item => <tr key={item.version} className="border-t border-zinc-800">
                <td className="p-2">{item.version}{item.version === history.head ? " (head)" : ""}</td><td className="p-2">{item.createdAt}</td><td className="p-2">{item.tombstone ? "Tombstone" : "Values"}</td>
                <td className="flex flex-wrap gap-2 p-2">
                  {allowed("read") && <button className={button} disabled={busy} onClick={() => reveal(item.version)}>Reveal version {item.version}</button>}
                  {allowed("rollback", true) && status?.adopted && <button className={button} disabled={busy} onClick={() => startConfirmation("rollback", item.version)}>{status.tombstone && !item.tombstone ? "Restore" : "Rollback"} version {item.version}</button>}
                  {allowed("export") && <button className={button} disabled={busy} onClick={() => startConfirmation("export", item.version)}>Export version {item.version}</button>}
                </td></tr>)}</tbody></table></div>
            <Pager page={historyPage} total={history.items.length} setPage={setHistoryPage} />
          </>}
        </section>
      </>}
      {edit && allowed(edit.create ? "create" : "update", true) && <section className="space-y-3" aria-label="Grouped field editor">
        <h2 ref={heading} tabIndex={-1} className="text-base font-semibold">{edit.create ? "Initialize document" : edit.replacement ? "Replace complete mapped document without reading values" : "Edit grouped fields"}</h2>
        <p className="text-sm text-zinc-400">{edit.replacement ? "Current values have not been read. Enter the complete replacement for every included field. Unchecking a field explicitly removes it; existing mapped values are not retained. Unrelated native keys, type and metadata stay intact." : "Unchecked fields are removed from this document. Other native keys stay intact."} Empty values require explicit confirmation.</p>
        {edit.drafts.map((draft, index) => <div key={draft.field} className="space-y-2 rounded-lg border border-zinc-700 p-3">
          <label className="flex items-start gap-2 break-all text-sm"><input type="checkbox" checked={draft.present} onChange={event => setEdit({ ...edit, drafts: edit.drafts.map((row, i) => i === index ? { ...row, present: event.target.checked } : row) })} />Include {draft.field} → {path.fields[index].key}</label>
          {draft.present && <>
            <label className="block text-sm">Encoding for {draft.field}<select aria-label={`Encoding for ${draft.field}`} className={`${input} mt-1`} value={draft.encoding} onChange={event => {
              try { const encoding = event.target.value as EncodedField["encoding"]; const value = convertEncoding(draft, encoding);
                setEdit({ ...edit, drafts: edit.drafts.map((row, i) => i === index ? { ...row, encoding, value } : row) });
              } catch { setMessage("This field cannot be converted to the selected encoding. Keep binary bytes in base64."); }
            }}><option value="utf8">UTF-8 text</option><option value="base64">Base64 bytes</option></select></label>
            <label className="block text-sm">Value for {draft.field}<textarea aria-label={`Value for ${draft.field}`} className={`${input} mt-1 font-mono`} value={draft.value} rows={3} autoComplete="off" spellCheck={false} onChange={event => {
              setEdit({ ...edit, drafts: edit.drafts.map((row, i) => i === index ? { ...row, value: event.target.value, emptyConfirmed: false } : row) });
            }} /></label>
            {draft.value === "" && <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={draft.emptyConfirmed} onChange={event => setEdit({ ...edit, drafts: edit.drafts.map((row, i) => i === index ? { ...row, emptyConfirmed: event.target.checked } : row) })} />Intentionally store empty bytes for {draft.field}</label>}
          </>}
        </div>)}
        <p role="status" className="text-sm text-amber-300">{changed?.error}</p>
        {edit.create && <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={ack} onChange={event => setAck(event.target.checked)} />Create a new native document at this exact mapping; existing imported objects require adoption.</label>}
        {edit.replacement && <ExactConfirmation path={path.path} exact={exact} setExact={setExact} ack={ack} setAck={setAck} text="Replace the entire mapped document with only these entered fields. Unchecked mapped fields are removed; current values have not been read." />}
        <div className="flex flex-wrap gap-2"><button className={button} disabled={busy || capturedMetadataChanged || !(changed?.changed || replacementIntent) || !!changed?.error || edit.create && !ack || edit.replacement && (!ack || exact !== path.path)} onClick={() => {
          if (changed && (changed.changed || replacementIntent) && !changed.error && allowed(edit.create ? "create" : "update", true)) mutate(endpoint + "/data", edit.create ? "POST" : "PUT", { ...edit.capture, fields: changed.fields });
        }}>Save as new version</button><button className={button} onClick={cancel}>Cancel edit</button></div>
      </section>}
      {adoption && allowed("create", true) && caps?.initializationAllowed && <section className="space-y-3" aria-label="Adoption preview">
        <h2 ref={heading} tabIndex={-1} className="font-semibold">Preserve originals and adopt as version 1</h2>
        <p className="text-sm text-zinc-400">Snapshots the selected original bytes without replacing them. Unrelated keys and metadata stay intact. Existing exact aliases receive compatibility grants.</p>
        <ul className="space-y-1 break-all text-sm">{adoption.preview.fields.map(field => <li key={field.field}>{field.field} → {path.namespace}/{path.name}/{field.key}</li>)}</ul>
        <p className="text-sm">{adoption.preview.legacyAliases.length} exact legacy aliases affected</p>
        <ul className="space-y-1 break-all text-sm">{adoption.preview.legacyAliases.slice(aliasPage * PAGE, (aliasPage + 1) * PAGE).map(alias => <li key={alias.alias}>{alias.alias} → {alias.namespace}/{alias.name}/{alias.key}</li>)}</ul>
        <Pager page={aliasPage} total={adoption.preview.legacyAliases.length} setPage={setAliasPage} />
        <ExactConfirmation path={path.path} exact={exact} setExact={setExact} ack={ack} setAck={setAck} text="I reviewed the mapped fields and all affected aliases; preserve the originals and create immutable version 1." />
        <div className="flex flex-wrap gap-2"><button className={button} disabled={busy || capturedMetadataChanged || !adoption.preview.guardedAdoption || exact !== path.path || !ack} onClick={() => mutate(endpoint + "/adopt", "POST", { ...adoption.capture, legacyAliases: adoption.preview.legacyAliases.map(alias => alias.alias) })}>Confirm adoption</button><button className={button} onClick={cancel}>Cancel adoption</button></div>
      </section>}
      {confirmation && <section className="space-y-3" aria-label="Confirm native action">
        <h2 ref={heading} tabIndex={-1} className="font-semibold">{confirmation.kind === "delete" ? "Soft-delete current managed fields" : confirmation.kind === "rollback" ? `Create a new version from version ${confirmation.version}` : confirmation.kind === "reconcile" ? "Capture external selected bytes as a new version" : `Export ${confirmation.version ? `version ${confirmation.version}` : "current document"} to a credential-bearing file`}</h2>
        <p className="text-sm text-zinc-400">{confirmation.kind === "delete" ? "Retain immutable history and the original native object. Restore later from a retained value version." : confirmation.kind === "rollback" ? "The selected immutable version stays unchanged. This action creates a new head." : confirmation.kind === "reconcile" ? "Explicitly accept externally changed managed values into immutable history. No automatic reconciliation occurs." : "Only selected managed fields are exported. The download contains credential bytes and needs protected storage."}</p>
        <ExactConfirmation path={path.path} exact={exact} setExact={setExact} ack={ack} setAck={setAck} text="I understand and explicitly authorize this action for the exact path and selected version." />
        <div className="flex flex-wrap gap-2"><button className={button} disabled={busy || capturedMetadataChanged || exact !== path.path || !ack} onClick={confirmAction}>Confirm {confirmation.kind}</button><button className={button} onClick={cancel}>Cancel action</button></div>
      </section>}
      {importOpen && session.canKvWrite && capabilityFresh && <section className="space-y-3" aria-label="Protected import">
        <h2 ref={heading} tabIndex={-1} className="font-semibold">Import native KV bundle</h2>
        <p className="text-sm text-zinc-400">One MiB / 100 documents maximum. Preview displays metadata only; the bundle remains in this temporary form. Every target and mapping is explicit. Existing unadopted targets must be adopted separately.</p>
        {!transfer && <>
          <label className="block text-sm">BORTUS v1 JSON bundle<textarea className={`${input} mt-1 font-mono`} rows={6} value={importText} autoComplete="off" spellCheck={false} onChange={event => { setImportText(event.target.value); setAck(false); }} /></label>
          <label className="block text-sm">Or choose a JSON bundle<input className="mt-1 block max-w-full text-sm" type="file" accept="application/json,.json" onChange={async event => {
            const file = event.target.files?.[0]; event.target.value = "";
            if (!file) return;
            if (file.size > 1024 * 1024) { setMessage("Transfer exceeds one MiB."); return; }
            const ticket = fence.current.begin();
            try { const text = await file.text(); if (mounted.current && ticket.current()) setImportText(text); }
            catch { if (ticket.current()) setMessage("Unable to read the selected bundle."); } finally { ticket.finish(); }
          }} /></label>
          <button className={button} disabled={busy || !importText} onClick={previewImport}>Preview target metadata</button>
        </>}
        {transfer && <>
          <p className="text-sm text-amber-200">{transfer.preview.plans.length} documents · independent commits · partial success possible. Source versions are informational; each commit creates a new version.</p>
          {transfer.preview.plans.slice(transferPage * PAGE, (transferPage + 1) * PAGE).map(plan => <div className="space-y-2 rounded-lg border border-zinc-700 p-3 text-sm" key={plan.documentIndex}>
            <p className="break-all">Document {plan.documentIndex + 1}: {transfer.bundle.documents[plan.documentIndex].path} → {transfer.bundle.documents[plan.documentIndex].namespace}/{transfer.bundle.documents[plan.documentIndex].name}</p>
            <p>{plan.outcome} · HTTP {plan.status}{plan.outcome === "ready" ? ` · head ${plan.expectedHead} · path revision ${plan.revision ?? "new"} · native revision ${plan.resourceVersion}` : " · review permissions, mapping and separate adoption requirements"}</p>
            <ul className="break-all">{transfer.bundle.documents[plan.documentIndex].mappings.map(mapping => <li key={mapping.field}>{mapping.field} → {mapping.key}</li>)}</ul>
            {plan.requiresOverwrite && <label className="flex items-start gap-2"><input type="checkbox" checked={transfer.overwrites.includes(plan.documentIndex)} onChange={event => setTransfer({ ...transfer, overwrites: event.target.checked ? [...transfer.overwrites, plan.documentIndex] : transfer.overwrites.filter(index => index !== plan.documentIndex) })} />Overwrite this existing document at the captured head/revision by creating a new version.</label>}
          </div>)}
          <Pager page={transferPage} total={transfer.preview.plans.length} setPage={setTransferPage} />
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={ack} onChange={event => setAck(event.target.checked)} />I reviewed every explicit target/mapping and authorize credential transfer with independent commits and new version creation.</label>
          <button className={button} disabled={busy || !ack || !transfer.preview.guardedAdoption || transfer.preview.plans.some(plan => plan.outcome !== "ready" || plan.requiresOverwrite && !transfer.overwrites.includes(plan.documentIndex))} onClick={commitImport}>Commit reviewed import</button>
        </>}
        <button className={button} onClick={cancel}>Cancel and discard bundle</button>
      </section>}
      {!!outcomes.length && <section aria-label="Import batch outcomes" className="space-y-2 text-sm">
        <h2 className="font-semibold">Per-document outcomes</h2>
        {outcomes.slice(transferPage * PAGE, (transferPage + 1) * PAGE).map(outcome => <p key={outcome.documentIndex} className="break-all">Document {outcome.documentIndex + 1}: {outcome.outcome} · HTTP {outcome.status}{outcome.head ? ` · new head ${outcome.head}` : ""}{outcome.operationId ? ` · operation ${outcome.operationId}` : ""}</p>)}
        <Pager page={transferPage} total={outcomes.length} setPage={setTransferPage} />
      </section>}
    </div>
  </Modal>;
}
function ExactConfirmation({ path, exact, setExact, ack, setAck, text }: { path: string; exact: string; setExact: (value: string) => void; ack: boolean; setAck: (value: boolean) => void; text: string }) {
  return <><label className="block break-all text-sm">Type exact logical path: {path}<input className={`${input} mt-1`} value={exact} onChange={event => setExact(event.target.value)} autoComplete="off" spellCheck={false} /></label>
    <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={ack} onChange={event => setAck(event.target.checked)} />{text}</label></>;
}
function Pager({ page, total, setPage }: { page: number; total: number; setPage: (page: number) => void }) {
  return <div className="flex flex-wrap items-center gap-2 text-sm"><button className={button} disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
    <span>Page {page + 1} of {Math.max(1, Math.ceil(total / PAGE))}</span><button className={button} disabled={(page + 1) * PAGE >= total} onClick={() => setPage(page + 1)}>Next</button></div>;
}
