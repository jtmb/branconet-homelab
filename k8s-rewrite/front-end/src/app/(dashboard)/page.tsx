"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useSession, requestJson, refetchCluster } from "@/lib/use-query";
import { QueryStatus } from "@/components/ui/query-status";
import ViewportWrapper from "./viewport-wrapper";
import ConfirmDialog from "./confirm-dialog";
interface Info { nodes: number | null; readyNodes: number | null; pods: number | null; runningPods: number | null; version: string | null;
  longhornVolumes: number | null; healthyVolumes: number | null; hasDbCluster: boolean; fluxRepos: number; availability?: { state?: string } }
export default function ClusterPage() {
  const query = useQuery<Info>("/api/cluster/info");
  const secrets = useQuery<{ secrets: unknown[] }>("/api/secrets", 30000);
  const configuration = useQuery<unknown[]>("/api/vars", 30000);
  const session = useSession();
  const [confirm, setConfirm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const info = query.data;
  const count = (value: unknown) => typeof value === "number" ? String(value) : "—";
  const cards = [
    { title: "Nodes ready", value: count(info?.readyNodes) + " / " + count(info?.nodes), href: "/nodes" },
    { title: "Pods running", value: count(info?.runningPods) + " / " + count(info?.pods), href: "/pods" },
    { title: "Longhorn healthy", value: count(info?.healthyVolumes) + " / " + count(info?.longhornVolumes), href: "/storage" },
    { title: "Native Secret objects", value: secrets.error ? "Unavailable" : count(secrets.data?.secrets.length), href: "/secrets" },
    { title: "Configuration records", value: configuration.error ? "Unavailable" : count(configuration.data?.length), href: "/configuration" },
    { title: "Repository inventory", value: count(info?.fluxRepos), href: "/flux" },
  ];
  return <ViewportWrapper><main className="px-3 py-6 sm:px-4 lg:px-6">
    <h1 className="mb-2 text-2xl font-semibold">Cluster overview</h1>
    <p className="mb-4 text-sm text-zinc-400">{query.loading ? "Loading cluster…" : !info ? "Cluster unavailable" : "Kubernetes " + (info.version || "version unavailable")}
      {info && " · " + info.availability?.state}</p>
    <QueryStatus query={query} />
    {error && <p role="alert" className="mb-4 text-red-300">{error}</p>}
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {cards.map(card => <Link key={card.title} href={card.href} className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 hover:border-indigo-500">
        <h2 className="text-sm text-zinc-400">{card.title}</h2><p className="mt-2 text-2xl">{card.value}</p></Link>)}
    </div>
    {(secrets.error || configuration.error) && <p role="status" className="mt-4 text-sm text-amber-300">Some independent metadata sources are unavailable; their counts are not reported as zero.</p>}
    <section className="mt-8 space-y-3 text-sm text-zinc-400">
      <h2 className="text-lg text-zinc-200">Operations</h2>
      <p>Flux owns Git desired state through the private branconet-charts repository. Inspect live sources and reconciliation status in <Link href="/flux" className="text-indigo-300 underline">Flux</Link>.</p>
      <p>Native Kubernetes Secrets hold credential values. Configuration and inventory are stored in SQLite. Cluster provisioning runs from an independent operator environment.</p>
      {session.canWrite && info?.hasDbCluster && <button onClick={() => { setError(""); setConfirm(true); }} className="rounded border border-red-800 px-3 py-2 text-red-300">Clear dashboard inventory</button>}
    </section>
    {confirm && session.canWrite && <ConfirmDialog open title="Clear dashboard inventory" message="Removes SQLite cluster state, node, pod, service, deployment and Git repository inventory records. Live cluster resources and native Secrets remain. Rebuilding inventory may require operator work."
      confirmName="inventory" confirmLabel="Clear inventory" danger loading={saving} onClose={() => { if (!saving) setConfirm(false); }} onConfirm={async () => {
        setSaving(true);
        try { await requestJson("/api/cluster/remove", { method: "DELETE" }); refetchCluster(); setConfirm(false); }
        catch (failure) { setError(failure instanceof Error ? failure.message : "Inventory removal failed"); }
        finally { setSaving(false); }
      }} />}
  </main></ViewportWrapper>;
}
