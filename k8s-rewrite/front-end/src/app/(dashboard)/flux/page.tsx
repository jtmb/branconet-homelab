"use client";

import { GitBranch, Loader2, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import ViewportWrapper from "../viewport-wrapper";
import ConfirmDialog from "../confirm-dialog";
import FluxTreeRow from "./tree-row";
import { Modal } from "@/components/ui/modal";
import { SortHeader, useSort } from "@/components/ui/sortable-header";
import { useQuery, useSession } from "@/lib/use-query";
import { useMutation } from "@/lib/use-mutation";
import { compareValues } from "@/lib/table-sort";
import type { QuerySnapshot } from "@/lib/query-store";
import type { DeleteProgress, FluxTreeNode } from "@/lib/flux";

const inputClass = "mt-1 block w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2";
const buttonClass = "rounded-lg bg-zinc-800 px-3 py-2 text-sm disabled:opacity-50";
interface RemovalMonitor { id: string; startedAt: number; name: string; accepted: boolean }
interface FluxScreenProps {
  canWrite: boolean; monitor: RemovalMonitor | null; setMonitor: (monitor: RemovalMonitor | null) => void;
  completed: DeleteProgress | null; setCompleted: (progress: DeleteProgress | null) => void;
}

function filterTree(nodes: FluxTreeNode[], query: string): FluxTreeNode[] {
  const lower = query.toLowerCase();
  return nodes.flatMap(node => {
    const children = filterTree(node.children, query);
    return node.name.toLowerCase().includes(lower) || children.length
      ? [{ ...node, children: children.length ? children : node.children }] : [];
  });
}

/** Dispose private forms and mutation owners on permission, account or visibility loss. */
export default function FluxPage() {
  const session = useSession();
  const [visible, setVisible] = useState(true);
  const [ended, setEnded] = useState(false);
  const [monitor, setMonitor] = useState<RemovalMonitor | null>(null);
  const [completed, setCompleted] = useState<DeleteProgress | null>(null);
  useEffect(() => {
    const visibility = () => setVisible(document.visibilityState !== "hidden");
    const end = () => setEnded(true);
    visibility();
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("bortus-session-ended", end);
    return () => { document.removeEventListener("visibilitychange", visibility); window.removeEventListener("bortus-session-ended", end); };
  }, []);
  if (ended) return <p role="alert" className="p-6">Session ended. Sign in again to manage Flux.</p>;
  if (!visible) return null;
  return <FluxHierarchy privateKey={`${session.data?.username ?? "anonymous"}:${session.canWrite}`} canWrite={session.canWrite}
    monitor={monitor} setMonitor={setMonitor} completed={completed} setCompleted={setCompleted} />;
}

/** Public read ownership persists while only the private mutation/form owner changes. */
function FluxHierarchy({ privateKey, ...props }: FluxScreenProps & { privateKey: string }) {
  const hierarchy = useQuery<{ trees: FluxTreeNode[] }>("/api/flux/hierarchy");
  return <FluxScreen key={privateKey} {...props} hierarchy={hierarchy} />;
}

function FluxScreen({ canWrite, monitor, setMonitor, completed, setCompleted, hierarchy }: FluxScreenProps & {
  hierarchy: QuerySnapshot<{ trees: FluxTreeNode[] }> & { refetch: () => void };
}) {
  const mutation = useMutation();
  const [adding, setAdding] = useState(false);
  const [confirmation, setConfirmation] = useState<FluxTreeNode | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const { sortKey, sortDir, toggle } = useSort<"name" | "revision" | "lastSync">("name");
  const searchRef = useRef<HTMLInputElement>(null);
  const removalOwner = useRef<symbol | null>(null);
  const trees = useMemo(() => hierarchy.data?.trees ?? [], [hierarchy.data]);
  const filtered = useMemo(() => {
    const result = search.trim() ? filterTree(trees, search.trim()) : trees;
    return [...result].sort((left, right) => {
      const sortValue = (node: FluxTreeNode) => sortKey === "lastSync" ? node.lastSync : sortKey === "revision" ? node.revision : node.name;
      const compare = compareValues(sortValue(left), sortValue(right), sortKey === "lastSync" ? "date" : "text", sortDir);
      return compare || compareValues(left.name, right.name) || compareValues(left.id, right.id);
    });
  }, [trees, search, sortKey, sortDir]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / 100));
  const currentPage = Math.min(page, pageCount - 1);
  const busy = mutation.busy || monitor !== null;
  const refetch = hierarchy.refetch;
  const finish = useCallback((progress: DeleteProgress) => {
    removalOwner.current = null;
    setMonitor(null); setCompleted(progress); refetch();
  }, [refetch, setMonitor, setCompleted]);
  function dismissProgress() {
    removalOwner.current = null;
    if (monitor) setNotice("Progress monitoring dismissed. The server operation may still be running; refresh and check its result before retrying.");
    setMonitor(null); setCompleted(null);
  }
  function sync(node: FluxTreeNode) {
    if (!canWrite || busy) return;
    setSyncing(node.id); setNotice("");
    const parameters = new URLSearchParams({ name: node.name, namespace: node.namespace });
    void mutation.mutate(`/api/flux/repos/${encodeURIComponent(node.id)}/sync?${parameters}`, { method: "POST" }, () => {
      setNotice(`Reconciliation requested for ${node.name}. Controller readiness is shown separately.`); refetch();
    });
  }
  function remove() {
    if (!canWrite || busy || !confirmation) return;
    const node = confirmation;
    const parameters = new URLSearchParams({ name: node.name, namespace: node.namespace });
    setNotice("");
    setConfirmation(null);
    // Public operation references survive hidden pages/permission loss; never retain a request body.
    const startedAt = Date.now();
    const owner = Symbol("removal");
    removalOwner.current = owner;
    setMonitor({ id: node.id.startsWith("gr-") ? `gr-${node.name}` : node.id, name: node.name, startedAt, accepted: false });
    void mutation.mutate<{ deleteId?: string }>(`/api/flux/repos/${encodeURIComponent(node.id)}?${parameters}`, { method: "DELETE" }, result => {
      if (removalOwner.current !== owner) return;
      if (!result.deleteId) throw new Error("Deletion response is incomplete. Refresh to check the result before retrying.");
      setMonitor({ id: result.deleteId, name: node.name, startedAt, accepted: true });
    });
  }
  return <ViewportWrapper><main className="px-3 py-6 sm:px-4 lg:px-6">
    <div className="mb-6 flex flex-wrap items-center gap-3">
      <GitBranch className="page-header-icon text-emerald-400" /><h1 className="page-header-title">Flux</h1>
      <span className="text-sm text-zinc-400">{hierarchy.data ? `${trees.length} repositories` : "Repository count unavailable"}</span>
      <button onClick={refetch} disabled={hierarchy.refreshing} className={`${buttonClass} ml-auto`} aria-label="Refresh Flux hierarchy"><RefreshCw className="h-4 w-4" /></button>
      {canWrite && <button disabled={busy} onClick={() => setAdding(true)} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm disabled:opacity-50"><Plus className="h-4 w-4" />Add Repository</button>}
    </div>
    <label className="mb-4 block max-w-md text-sm">Search repositories and descendants
      <input ref={searchRef} value={search} onChange={event => { setSearch(event.target.value); setPage(0); }} className={inputClass} type="search" />
    </label>
    {(hierarchy.error || hierarchy.stale) && <p role="alert" className="mb-4 rounded border border-amber-800 p-3 text-amber-200">
      {hierarchy.error ?? "Flux metadata is stale."} {hierarchy.data ? "Showing the last successful snapshot." : "Flux hierarchy unavailable."}
      <button onClick={refetch} className={`${buttonClass} ml-2`}>Retry</button>
    </p>}
    {mutation.error && !confirmation && <p role="alert" className="mb-4 text-red-300">{mutation.error}</p>}
    {notice && <p role="status" className="mb-4 text-sm text-zinc-300">{notice}</p>}
    {hierarchy.loading && !hierarchy.data ? <p role="status" className="flex items-center gap-2"><Loader2 className="h-5 w-5 animate-spin" />Loading Flux hierarchy</p>
      : hierarchy.data && trees.length === 0 ? <p className="rounded-xl border border-zinc-800 p-6">No Git repositories in the current successful snapshot.</p>
      : hierarchy.data && <div className="rounded-xl border border-zinc-800">
        <div className="flex flex-wrap gap-4 border-b border-zinc-800 p-3">
          <SortHeader label="Name" active={sortKey === "name"} dir={sortDir} onClick={() => { toggle("name"); setPage(0); }} />
          <SortHeader label="Revision" active={sortKey === "revision"} dir={sortDir} onClick={() => { toggle("revision"); setPage(0); }} />
          <SortHeader label="Last Sync" active={sortKey === "lastSync"} dir={sortDir} onClick={() => { toggle("lastSync"); setPage(0); }} />
        </div>
        {filtered.slice(currentPage * 100, (currentPage + 1) * 100).map(node => <FluxTreeRow key={node.id} node={node}
          onSync={canWrite ? () => sync(node) : undefined} onDelete={canWrite ? () => { mutation.clear(); setConfirmation(node); } : undefined}
          syncingId={mutation.busy ? syncing : null} deletingId={monitor?.id} disabled={busy} />)}
        {!filtered.length && <p className="p-4">No matching repositories.</p>}
        <nav aria-label="Repository pages" className="flex flex-wrap items-center gap-3 border-t border-zinc-800 p-3">
          <button className={buttonClass} disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Previous</button>
          <span className="text-sm">Page {currentPage + 1} of {pageCount}; {filtered.length} matches</span>
          <button className={buttonClass} disabled={currentPage + 1 >= pageCount} onClick={() => setPage(currentPage + 1)}>Next</button>
        </nav>
      </div>}
    {adding && canWrite && <AddRepository onClose={() => setAdding(false)} onAdded={() => { setAdding(false); refetch(); }} returnFocus={() => searchRef.current?.focus()} />}
    {confirmation && canWrite && <ConfirmDialog open onClose={() => setConfirmation(null)} onConfirm={remove} title={`Remove ${confirmation.name}`} confirmName={confirmation.name} confirmLabel="Remove repository" danger loading={mutation.busy} error={mutation.error}
      message={`Remove this repository and its discovered children. For supported application namespaces, cascade removal also deletes the namespace and cleans up bound volumes after confirmed absence. Protected namespaces are retained. Native repository credentials remain for explicit cleanup. Selected namespace: ${confirmation.namespace}.`} returnFocus={() => searchRef.current?.focus()} />}
    {monitor && <DeleteMonitor id={monitor.id} name={monitor.name} startedAt={monitor.startedAt} accepted={monitor.accepted} mutationError={mutation.error} onComplete={finish} onClose={dismissProgress} returnFocus={() => searchRef.current?.focus()} />}
    {completed && <DeleteDialog progress={completed} onClose={dismissProgress} returnFocus={() => searchRef.current?.focus()} />}
  </main></ViewportWrapper>;
}

function AddRepository({ onClose, onAdded, returnFocus }: { onClose: () => void; onAdded: () => void; returnFocus: () => void }) {
  const mutation = useMutation();
  const authenticationId = useId();
  const [form, setForm] = useState({ name: "", url: "", branch: "main", path: "./", authMethod: "none", authData: "" });
  function add(event: React.FormEvent) {
    event.preventDefault();
    if (mutation.busy || !form.name || !form.url) return;
    void mutation.mutate("/api/flux/repos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, authData: form.authData || undefined }) }, onAdded);
  }
  return <Modal open onClose={onClose} title="Add Git Repository" description="Flux will reconcile the selected repository path. Private authentication goes directly to a native Kubernetes Secret." returnFocus={returnFocus}>
    <form onSubmit={add} className="space-y-4">
      {mutation.error && <p role="alert" className="text-red-300">{mutation.error}</p>}
      <fieldset disabled={mutation.busy} className="space-y-4 disabled:opacity-60">
        {([['name', 'Name'], ['url', 'Git URL'], ['branch', 'Branch'], ['path', 'Kustomize Path']] as const).map(([key, label]) => <label key={key} className="block text-sm">{label}<input autoComplete="off" required value={form[key]} onChange={event => setForm(current => ({ ...current, [key]: event.target.value }))} className={inputClass} /></label>)}
        <div className="text-sm"><label htmlFor={authenticationId}>Authentication</label><select id={authenticationId} value={form.authMethod} onChange={event => setForm(current => ({ ...current, authMethod: event.target.value, authData: "" }))} className={inputClass}><option value="none">Public</option><option value="ssh">SSH deploy key</option><option value="https">HTTPS token</option></select></div>
        {form.authMethod !== "none" && <label className="block text-sm">{form.authMethod === "ssh" ? "SSH Deploy Key" : "Personal Access Token"}
          {form.authMethod === "ssh" ? <textarea required autoComplete="off" spellCheck={false} rows={5} value={form.authData} onChange={event => setForm(current => ({ ...current, authData: event.target.value }))} className={inputClass} />
            : <input required type="password" autoComplete="new-password" value={form.authData} onChange={event => setForm(current => ({ ...current, authData: event.target.value }))} className={inputClass} />}
        </label>}
      </fieldset>
      <p className="text-xs text-zinc-400">Closing this form aborts the client request and clears the draft. An already accepted server operation can continue; refresh to check the result before retrying.</p>
      <div className="flex justify-end gap-3"><button type="button" onClick={onClose} className={buttonClass}>Cancel</button><button disabled={mutation.busy || !form.name || !form.url} className="rounded-lg bg-indigo-600 px-4 py-2 disabled:opacity-50">{mutation.busy ? "Adding repository" : "Add Repository"}</button></div>
    </form>
  </Modal>;
}

function DeleteMonitor({ id, name, startedAt, accepted, mutationError, onComplete, onClose, returnFocus }: { id: string; name: string; startedAt: number; accepted: boolean; mutationError?: string; onComplete: (progress: DeleteProgress) => void; onClose: () => void; returnFocus: () => void }) {
  const query = useQuery<DeleteProgress>(`/api/flux/repos/${encodeURIComponent(id)}/delete-progress`, 1500);
  const progress = query.updatedAt > startedAt ? query.data : undefined;
  useEffect(() => { if (progress?.done && !query.error) onComplete(progress); }, [progress, query.error, onComplete]);
  return <DeleteDialog progress={progress} name={name} onClose={onClose} returnFocus={returnFocus} error={query.error ?? mutationError} stale={query.stale} retry={query.refetch}
    recovery={!accepted && !progress ? "Request acceptance is unconfirmed. Checking the public operation reference; do not submit again until its result is established. Completed progress expires during cleanup and server restart loses progress; missing progress does not establish that removal failed." : undefined} />;
}

function DeleteDialog({ progress, name, onClose, returnFocus, error, stale, retry, recovery }: { progress?: DeleteProgress; name?: string; onClose: () => void; returnFocus: () => void; error?: string; stale?: boolean; retry?: () => void; recovery?: string }) {
  return <Modal open onClose={onClose} returnFocus={returnFocus} title={`Repository removal: ${progress?.repoName ?? name ?? "progress"}`} description="Dismiss closes monitoring; it does not cancel the server operation.">
    <div aria-live="polite" className="space-y-3">
      {!progress && <p>Waiting for deletion progress.</p>}
      {recovery && <p className="text-amber-200">{recovery}</p>}
      {(error || stale) && <p role="alert" className="text-amber-200">{error ?? "Progress is stale."} {progress && "Showing the last successful progress snapshot."} {retry && <button className={buttonClass} onClick={retry}>Retry progress</button>}</p>}
      {progress?.steps.map(step => <p key={step.step} className={step.status === "error" ? "text-amber-200" : "text-zinc-300"}><span className="font-medium">{step.status}: </span>{step.detail}</p>)}
      {progress?.error && <p role="alert" className="text-red-300">{progress.error} Inspect the retained resources and inventory before retrying.</p>}
      {progress?.done && !progress.error && <p>Server removal completed. Review the hierarchy and retained native credentials.</p>}
    </div>
    <div className="mt-4 flex justify-end"><button onClick={onClose} className={buttonClass}>{progress?.done ? "Close" : "Dismiss monitoring"}</button></div>
  </Modal>;
}
