"use client";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useQuery, useSession } from "@/lib/use-query";
import { useMutation } from "@/lib/use-mutation";
import { ResourceTable } from "@/components/cluster/resource-list";
import { QueryStatus } from "@/components/ui/query-status";
import ViewportWrapper, { setViewMode, type ViewMode } from "../viewport-wrapper";
const ConfirmDialog = dynamic(() => import("../confirm-dialog"), { ssr: false });
type PV = Record<string, unknown> & { name: string; reclaimPolicy: string; status: string; storageClass: string; capacity: string; claimRef: string; age: string };
export default function SettingsPage() {
  const session = useSession();
  const settings = useQuery<Record<string, string>>("/api/settings");
  const volumes = useQuery<{ volumes: PV[] }>("/api/cluster/volumes/reclaim", 15000);
  const mutation = useMutation(session.canWrite);
  const [mode, setMode] = useState<ViewMode>("comfortable");
  const [selected, setSelected] = useState<PV>();
  const [policy, setPolicy] = useState("Retain");
  const [message, setMessage] = useState("");
  useEffect(() => {
    try { const saved = localStorage.getItem("k8s-view-mode"); if (saved === "full" || saved === "comfortable") setMode(saved); }
    catch { /* Browser preferences may be unavailable; the default still works. */ }
  }, []);
  useEffect(() => { if (!session.canWrite) setSelected(undefined); }, [session.canWrite]);
  const registrationKnown = !!session.data?.authenticated && !session.error;
  const registrationOpen = session.data?.registrationOpen === true;
  return <ViewportWrapper><main className="min-w-0 space-y-6 px-3 py-6 sm:px-4 lg:px-6">
    <h1 className="text-2xl font-semibold">Settings</h1>
    {message && <p role="status" className="text-emerald-300">{message}</p>}
    {mutation.error && !selected && <p role="alert" className="text-red-300">{mutation.error}</p>}
    <section className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <h2 className="text-lg">Viewport width</h2><p className="text-sm text-zinc-400">Choose the content width for this browser. Narrow screens use all available space.</p>
      <div className="flex flex-wrap gap-3">{(["comfortable", "full"] as const).map(value => <button key={value} aria-pressed={mode === value}
        onClick={() => { try { setViewMode(value); setMode(value); } catch { setMessage("Browser preferences are unavailable."); } }}
        className={"rounded border px-4 py-2 " + (mode === value ? "border-indigo-500 bg-indigo-500/10" : "border-zinc-700")}>{value === "full" ? "Full width" : "Comfortable"}</button>)}</div>
    </section>
    <section className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <h2 className="text-lg">User registration</h2><QueryStatus query={session} /><QueryStatus query={settings} />
      <p className="text-sm text-zinc-400">The application setting controls registration after bootstrap. ALLOW_REGISTRATION=true in the operator environment keeps registration open even when this setting is off.</p>
      <p>{registrationKnown ? registrationOpen ? "Registration open" : "Registration locked" : "Registration status unavailable"}</p>
      {session.canWrite && settings.data && !settings.error && <button role="switch" aria-label="Allow registration in application settings"
        aria-checked={settings.data.allow_registration === "true"} disabled={mutation.busy}
        onClick={() => {
          if (!session.canWrite) return;
          void mutation.mutate("/api/settings", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key: "allow_registration", value: String(settings.data!.allow_registration !== "true") }) },
            () => { setMessage("Registration setting saved."); settings.refetch(); session.refetch(); });
        }} className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50">{mutation.busy ? "Saving…" : settings.data.allow_registration === "true" ? "Application registration: on" : "Application registration: off"}</button>}
    </section>
    <section className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <h2 className="text-lg">Persistent volume reclaim policies</h2>
      <p className="text-sm text-zinc-400">New volume defaults come from the StorageClass. Review an existing volume before changing its policy. Delete can remove the underlying storage when a claim is released.</p>
      <QueryStatus query={volumes} />
      {volumes.loading ? <p role="status">Loading volume policies…</p> : volumes.data && <ResourceTable rows={volumes.data.volumes} resetKey=""
        columns={[{ key: "name", label: "Volume" }, { key: "reclaimPolicy", label: "Policy" }, { key: "status", label: "Status" }, { key: "storageClass", label: "Storage class" }, { key: "capacity", label: "Capacity", sort: "quantity" }, { key: "claimRef", label: "Claim" }, { key: "age", label: "Created", sort: "date" }]}
        renderActions={session.canWrite && !volumes.error ? row => <button aria-label={"Change reclaim policy " + row.name} disabled={mutation.busy}
          onClick={() => { mutation.clear(); const volume = row as PV; setSelected(volume); setPolicy(volume.reclaimPolicy); }} className="text-indigo-300 underline">Change policy</button> : undefined} />}
    </section>
    <p className="text-sm text-zinc-400">Flux repository deletion can remove namespaces, workloads and storage. Review its explicit confirmation and recovery state on the <Link prefetch={false} href="/flux" className="text-indigo-300 underline">Flux page</Link>.</p>
    {selected && session.canWrite && <ConfirmDialog key={selected.name} open title="Change volume reclaim policy" message={"Change " + selected.name + " from " + selected.reclaimPolicy + " to " + policy + ". Delete may remove the underlying storage after claim release."}
        confirmName={selected.name} danger={policy === "Delete"} loading={mutation.busy} error={mutation.error} confirmLabel="Apply policy"
        disabled={policy === selected.reclaimPolicy}
        onClose={() => { if (!mutation.busy) setSelected(undefined); }} onConfirm={() => {
          if (!session.canWrite || policy === selected.reclaimPolicy) return;
          void mutation.mutate<{ success: boolean; results: { success: boolean; error?: string }[] }>("/api/cluster/volumes/reclaim", {
            method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ volumes: [{ name: selected.name, policy }] }),
          }, result => {
            volumes.refetch();
            if (!result.success) throw new Error(result.results.find(item => !item.success)?.error ?? "Volume update failed.");
            setSelected(undefined); setMessage("Volume reclaim policy updated.");
          });
        }}>
      <label className="mb-4 block text-sm">Policy for {selected.name}<select value={policy} disabled={mutation.busy} onChange={e => setPolicy(e.target.value)} className="ml-3 rounded bg-zinc-950 p-2">
        {!["Retain", "Delete"].includes(selected.reclaimPolicy) && <option disabled>{selected.reclaimPolicy}</option>}<option>Retain</option><option>Delete</option>
      </select></label>
    </ConfirmDialog>}
  </main></ViewportWrapper>;
}
