"use client";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useQuery, useSession } from "@/lib/use-query";
import { useMutation } from "@/lib/use-mutation";
import { configurationRemoved, configurationSaved, type ConfigurationVariable as Variable } from "@/lib/configuration-response";
import { QueryStatus } from "@/components/ui/query-status";
import { ResourceTable } from "@/components/cluster/resource-list";
import ViewportWrapper from "../viewport-wrapper";
const Modal = dynamic(() => import("@/components/ui/modal").then(module => module.Modal), { ssr: false });
const ConfirmDialog = dynamic(() => import("../confirm-dialog"), { ssr: false });
const blank = { key: "", value: "", category: "general" };
export default function ConfigurationPage() {
  const query = useQuery<Variable[]>("/api/vars");
  const session = useSession();
  const mutation = useMutation();
  const [search, setSearch] = useState("");
  const [form, setForm] = useState(blank);
  const [editor, setEditor] = useState<"new" | Variable>();
  const [deleting, setDeleting] = useState<Variable>();
  const [message, setMessage] = useState("");
  const editing = editor && editor !== "new" ? editor : undefined;
  const valid = /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(form.key) && form.category.trim() !== ""
    && (!editing || form.value !== editing.value || form.category !== editing.category);
  useEffect(() => { if (!session.canWrite) { setEditor(undefined); setDeleting(undefined); setForm(blank); } }, [session.canWrite]);
  function open(row?: Variable) {
    mutation.clear(); setMessage(""); setEditor(row ?? "new"); setForm(row ? { key: row.key, value: row.value, category: row.category } : blank);
  }
  function close() { if (!mutation.busy) { setEditor(undefined); setForm(blank); mutation.clear(); } }
  return <ViewportWrapper><main className="min-w-0 space-y-4 px-3 py-6 sm:px-4 lg:px-6">
    <h1 className="text-2xl font-semibold">Nonsecret configuration</h1>
    <p className="text-sm text-zinc-400">Versions, network and inventory settings. Manage credentials under Secrets.</p>
    {message && <p role="status" className="text-emerald-300">{message}</p>}
    <div className="flex flex-wrap items-end gap-3">
      <label className="text-sm">Search configuration<input value={search} onChange={e => setSearch(e.target.value)} className="mt-1 block w-full rounded border border-zinc-700 bg-zinc-900 p-2" /></label>
      {session.canWrite && <button onClick={() => open()} disabled={mutation.busy} className="rounded bg-indigo-600 px-3 py-2">Add configuration</button>}
    </div>
    <QueryStatus query={query} />
    {query.loading ? <p role="status">Loading configuration…</p> : query.data && <ResourceTable
      rows={query.data.filter(row => [row.key, row.category, row.value].some(value => value.toLowerCase().includes(search.toLowerCase())))} resetKey={search}
      columns={[{ key: "key", label: "Key" }, { key: "category", label: "Category" }, { key: "value", label: "Value" }]}
      renderActions={session.canWrite ? row => <div className="flex gap-3">
        <button aria-label={"Edit configuration " + row.key} disabled={mutation.busy} onClick={() => open(row as Variable)} className="text-indigo-300 underline">Edit</button>
        <button aria-label={"Delete configuration " + row.key} disabled={mutation.busy} onClick={() => { mutation.clear(); setMessage(""); setDeleting(row as Variable); }} className="text-red-300 underline">Delete</button>
      </div> : undefined} />}
    {editor && session.canWrite && <Modal open onClose={close} title={editing ? "Edit configuration " + editing.key : "Add nonsecret configuration"}
      description="Use valid Ansible identifiers for keys. Empty nonsecret values are allowed. Credentials belong in native Secrets.">
      <form className="space-y-4" onSubmit={e => {
        e.preventDefault(); if (!session.canWrite || !valid) return;
        void mutation.mutate("/api/vars", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, ...(editing ? { id: editing.id } : {}), encrypted: false }) },
          result => { configurationSaved(result, { ...form, ...(editing ? { id: editing.id } : {}) }); setEditor(undefined); setForm(blank); setMessage("Configuration saved."); query.refetch(); });
      }}>
        {(["key", "category", "value"] as const).map(field => <label className="block text-sm" key={field}>{field === "key" ? "Key" : field === "category" ? "Category" : "Nonsecret value"}
          <input required={field !== "value"} disabled={mutation.busy || field === "key" && !!editing} value={form[field]} onChange={e => setForm({ ...form, [field]: e.target.value })}
            className="mt-1 block w-full rounded border border-zinc-700 bg-zinc-950 p-2" /></label>)}
        {mutation.error && <p role="alert" className="text-red-300">{mutation.error}</p>}
        <div className="flex flex-wrap justify-end gap-3"><button type="button" onClick={close} disabled={mutation.busy} className="rounded bg-zinc-700 px-4 py-2">Cancel</button>
          <button disabled={!valid || mutation.busy} className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50">{mutation.busy ? "Saving…" : "Save configuration"}</button></div>
      </form>
    </Modal>}
    {deleting && session.canWrite && <ConfirmDialog key={deleting.id} open title="Delete configuration" message={"Remove only the nonsecret SQLite entry: " + deleting.key}
      confirmName={deleting.key} danger loading={mutation.busy} error={mutation.error} confirmLabel="Delete configuration"
      onClose={() => { if (!mutation.busy) setDeleting(undefined); }} onConfirm={() => {
        if (!session.canWrite) return;
        void mutation.mutate("/api/vars/" + encodeURIComponent(deleting.id), { method: "DELETE" }, result => { configurationRemoved(result); setDeleting(undefined); setMessage("Configuration removed."); query.refetch(); });
      }} />}
  </main></ViewportWrapper>;
}
