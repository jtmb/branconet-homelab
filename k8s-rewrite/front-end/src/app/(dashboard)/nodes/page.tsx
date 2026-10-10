"use client";
import { useState } from "react";
import { useQuery, useSession, requestJson, refetchCluster } from "@/lib/use-query";
import { QueryStatus } from "@/components/ui/query-status";
import { ResourceTable } from "@/components/cluster/resource-list";
import ViewportWrapper from "../viewport-wrapper";
import ConfirmDialog from "../confirm-dialog";
type NodeRow = Record<string, unknown> & { id: string; name: string; hostname: string; ipAddress: string; role: string };
const blank = { name: "", hostname: "", ipAddress: "", role: "worker" };
export default function NodesPage() {
  const live = useQuery<{ nodes: NodeRow[]; availability?: { state?: string } }>("/api/cluster/nodes");
  const inventory = useQuery<NodeRow[]>("/api/nodes");
  const session = useSession();
  const [form, setForm] = useState(blank);
  const [editing, setEditing] = useState<string>();
  const [opened, setOpened] = useState(false);
  const [deleting, setDeleting] = useState<NodeRow>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const filter = (rows: NodeRow[]) => rows.filter(row => [row.name, row.hostname, row.ipAddress].some(value => value?.toLowerCase().includes(search.toLowerCase())));
  const liveRows = filter(live.data?.nodes ?? []).map(row => ({ ...row, metadata: { name: row.hostname } }));
  const save = async () => {
    if (!session.canWrite || saving || !form.hostname || !form.ipAddress) return;
    setSaving(true); setError("");
    try {
      await requestJson(editing ? "/api/nodes/" + encodeURIComponent(editing) : "/api/nodes", { method: editing ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      inventory.refetch(); refetchCluster(); setForm(blank); setEditing(undefined); setOpened(false);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Inventory save failed"); }
    finally { setSaving(false); }
  };
  return <ViewportWrapper><main className="px-3 py-6 sm:px-4 lg:px-6">
    <h1 className="mb-4 text-2xl font-semibold">Nodes</h1>
    <label className="mb-4 block text-sm">Search nodes<input value={search} onChange={e => setSearch(e.target.value)} className="mt-1 block rounded border border-zinc-700 bg-zinc-900 p-2" /></label>
    <h2 className="mb-3 text-lg">Live cluster</h2><QueryStatus query={live} />
    {live.loading ? <p role="status">Loading live nodes…</p> : !live.data ? <p>Live cluster data is unavailable.</p>
      : <ResourceTable rows={liveRows} resetKey={search} type="node" detail={row => "/nodes/" + encodeURIComponent(String(row.hostname))}
        columns={[{ key: "hostname", label: "Hostname" }, { key: "status", label: "Status" }, { key: "ipAddress", label: "IP" }, { key: "role", label: "Role" }, { key: "cpu", label: "CPU", sort: "number" }, { key: "memory", label: "Memory (GiB)", sort: "number" }, { key: "pods", label: "Pods", sort: "number" }, { key: "age", label: "Age", sort: "age" }, { key: "k8sVersion", label: "Version" }]} />}
    <h2 className="mb-3 mt-8 text-lg">Inventory</h2>
    <p className="mb-4 text-sm text-zinc-400">Inventory records do not provision or join nodes, and do not establish live health.</p>
    {error && <p role="alert" className="mb-3 text-red-300">{error}</p>}
    {inventory.error && <p role="status" className="mb-3 text-amber-300">{inventory.error}<button onClick={inventory.refetch} className="ml-3 underline">Retry inventory</button></p>}
    {session.canWrite && <button onClick={() => { setForm(blank); setEditing(undefined); setOpened(true); }} className="mb-4 rounded bg-indigo-600 px-3 py-2">Add inventory node</button>}
    {opened && session.canWrite && <form className="mb-6 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void save(); }}>
      {(["name", "hostname", "ipAddress"] as const).map(field => <label key={field} className="text-sm">{field === "ipAddress" ? "IP address" : field === "name" ? "Display name" : "Hostname"}
        <input required={field !== "name"} value={form[field]} disabled={saving} onChange={e => setForm({ ...form, [field]: e.target.value })}
          className="mt-1 block rounded border border-zinc-700 bg-zinc-900 p-2" /></label>)}
      <label className="text-sm">Role<select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} disabled={saving} className="mt-1 block rounded border border-zinc-700 bg-zinc-900 p-2">{["worker", "master", "control-plane"].map(role => <option key={role}>{role}</option>)}</select></label>
      <button disabled={saving || !form.hostname || !form.ipAddress} className="rounded bg-indigo-600 px-3 py-2 disabled:opacity-40">{saving ? "Saving…" : "Save inventory"}</button>
      <button type="button" disabled={saving} onClick={() => setOpened(false)} className="rounded bg-zinc-800 px-3 py-2">Cancel</button>
    </form>}
    {inventory.loading ? <p role="status">Loading inventory…</p> : inventory.data && <ResourceTable rows={filter(inventory.data)} resetKey={search}
      columns={[{ key: "name", label: "Display name" }, { key: "hostname", label: "Hostname" }, { key: "ipAddress", label: "IP" }, { key: "role", label: "Role" }, { key: "status", label: "Recorded status" }]}
      renderActions={session.canWrite ? row => <div className="flex gap-3">
        <button aria-label={"Edit inventory " + row.hostname} disabled={saving} onClick={() => {
          const node = row as NodeRow; setEditing(node.id); setForm({ name: node.name, hostname: node.hostname, ipAddress: node.ipAddress, role: node.role }); setOpened(true);
        }} className="text-indigo-300 underline">Edit</button>
        <button aria-label={"Delete inventory " + row.hostname} disabled={saving} onClick={() => setDeleting(row as NodeRow)} className="text-red-300 underline">Delete</button>
      </div> : undefined} />}
    {deleting && session.canWrite && <ConfirmDialog open title="Delete inventory record" message="This removes only the SQLite inventory record. The live Kubernetes node remains."
      confirmName={deleting.hostname} error={error} danger confirmLabel="Delete inventory" loading={saving} onClose={() => { if (!saving) setDeleting(undefined); }}
      onConfirm={async () => {
        setSaving(true); setError("");
        try { await requestJson("/api/nodes/" + encodeURIComponent(deleting.id), { method: "DELETE" }); inventory.refetch(); setDeleting(undefined); }
        catch (failure) { setError(failure instanceof Error ? failure.message : "Inventory delete failed"); }
        finally { setSaving(false); }
      }} />}
  </main></ViewportWrapper>;
}
