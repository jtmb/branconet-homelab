"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Container, Loader2, Server, Network, Gauge, Layers } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import ViewportWrapper from "../../../viewport-wrapper";
import ResourceActionsMenu from "../../../resource-actions-menu";

function formatAge(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 365) return `${d}d`;
  return `${Math.floor(d / 365)}y`;
}

export default function PodDetailPage() {
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const [pod, setPod] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const fetchPod = useCallback(async () => {
    try {
      const res = await fetch(`/api/cluster/pods/${namespace}/${name}`);
      if (res.status === 404) { setNotFound(true); setLoading(false); return; }
      const data = await res.json();
      setPod(data.pod);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [namespace, name]);

  useEffect(() => { fetchPod(); }, [fetchPod]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (notFound || !pod) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <Container className="w-12 h-12 text-zinc-600" />
        <h2 className="text-lg font-semibold text-zinc-300">Pod Not Found</h2>
        <p className="text-sm text-zinc-500">{namespace}/{name}</p>
        <Link href="/pods" className="text-indigo-400 hover:underline text-sm">← Back to Pods</Link>
      </div>
    );
  }

  const created = pod.metadata?.creationTimestamp;
  const ageMs = created ? Date.now() - new Date(created).getTime() : 0;
  const phase = pod.status?.phase || "Unknown";
  const ns = pod.metadata?.namespace || namespace;
  const nodeName = pod.spec?.nodeName || "-";
  const podIP = pod.status?.podIP || "-";
  const qosClass = pod.status?.qosClass || "-";

  // Owner references (e.g., ReplicaSet → Deployment chain)
  const owners = (pod.metadata?.ownerReferences || []).map((ref: any) => ({
    kind: ref.kind,
    name: ref.name,
  }));

  // Containers + statuses
  const containers = (pod.spec?.containers || []).map((c: any) => {
    const cs = (pod.status?.containerStatuses || []).find(
      (s: any) => s.name === c.name
    );
    return {
      name: c.name,
      image: c.image,
      state: cs?.state
        ? (Object.keys(cs.state)[0] || "-")
        : "-",
      ready: cs?.ready ? "Yes" : "No",
      restartCount: cs?.restartCount ?? 0,
      ports: (c.ports || []).map((p: any) => `${p.containerPort}/${p.protocol || "TCP"}`).join(", ") || "-",
    };
  });

  // Conditions
  const conditions = (pod.status?.conditions || []).map((c: any) => ({
    type: c.type,
    status: c.status,
    reason: c.reason || "-",
    message: c.message || "-",
  }));

  // Labels
  const labels = pod.metadata?.labels || {};

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        <div className="flex items-center gap-3 mb-6">
          <Container className="page-header-icon text-cyan-400" />
          <h1 className="page-header-title">{pod.metadata?.name}</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            phase === "Running" ? "badge-success" : phase === "Pending" ? "badge-warning" : "badge-error"
          }`}>{phase}</span>
          <span className="text-xs text-zinc-500 bg-zinc-800/60 px-2 py-0.5 rounded-full">{ns}</span>
          <span className="text-xs text-zinc-500 ml-auto">{ageMs > 0 ? formatAge(ageMs) : "…"}</span>
          <ResourceActionsMenu resourceType="pod" resource={pod} />
        </div>

        {/* Containers */}
        <section className="glass-card rounded-xl overflow-hidden mb-6">
        <div className="px-4 py-3 border-b border-zinc-700/40">
          <h2 className="text-sm font-semibold text-zinc-200">
            Containers {containers.length > 0 && `(${containers.length})`}
          </h2>
        </div>
        {containers.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-zinc-500">No containers found</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-700/40">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Name</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Image</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">State</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Ready</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Restarts</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Ports</th>
              </tr>
            </thead>
            <tbody>
              {containers.map((c: any) => (
                <tr key={c.name} className="border-b border-zinc-800/40">
                  <td className="px-4 py-2.5 text-sm text-zinc-200 font-mono">{c.name}</td>
                  <td className="px-4 py-2.5 text-sm text-zinc-400 font-mono text-xs">{c.image}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      c.state === "running" ? "badge-success" :
                      c.state === "waiting" ? "badge-warning" :
                      "text-xs text-zinc-500"
                    }`}>{c.state}</span>
                  </td>
                  <td className="px-4 py-2.5 text-sm text-zinc-400">{c.ready}</td>
                  <td className="px-4 py-2.5 text-sm text-zinc-400">{c.restartCount}</td>
                  <td className="px-4 py-2.5 text-sm text-zinc-500 font-mono text-xs">{c.ports}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

        {/* Conditions */}
        <section className="glass-card rounded-xl overflow-hidden mb-6">
        <div className="px-4 py-3 border-b border-zinc-700/40">
          <h2 className="text-sm font-semibold text-zinc-200">
            Conditions {conditions.length > 0 && `(${conditions.length})`}
          </h2>
        </div>
        {conditions.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-zinc-500">No conditions</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-700/40">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Type</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Status</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Reason</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Message</th>
              </tr>
            </thead>
            <tbody>
              {conditions.map((c: any) => (
                <tr key={c.type} className="border-b border-zinc-800/40">
                  <td className="px-4 py-2.5 text-sm text-zinc-200">{c.type}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      c.status === "True" ? "badge-success" : "badge-warning"
                    }`}>{c.status}</span>
                  </td>
                  <td className="px-4 py-2.5 text-sm text-zinc-400">{c.reason}</td>
                  <td className="px-4 py-2.5 text-sm text-zinc-500 max-w-xs truncate">{c.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

        {/* Details */}
        <section className="glass-card rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-zinc-300 mb-4">Details</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard icon={Server} label="Node" value={nodeName} />
            <StatCard icon={Network} label="Pod IP" value={podIP} mono />
            <StatCard icon={Gauge} label="QoS Class" value={qosClass} />
            {owners.length > 0 && (
              <StatCard
                icon={Layers}
                label="Owner"
                value={owners.map((o: any) => `${o.kind}/${o.name}`).join(", ")}
              />
            )}
          </div>
          {Object.keys(labels).length > 0 && (
            <div className="mt-4 pt-4 border-t border-zinc-700/40">
              <p className="text-xs text-zinc-500 mb-2.5 font-medium uppercase tracking-wider">Labels</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(labels).map(([k, v]) => (
                  <span key={k} className="text-xs px-2 py-0.5 rounded-md bg-zinc-800/80 text-zinc-300 font-mono ring-1 ring-zinc-700/40">
                    {k}={v as string}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>
      </main>
      </ViewportWrapper>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, mono }: { icon: any; label: string; value: string; mono?: boolean }) {
  return (
    <div className="bg-zinc-800/40 rounded-lg p-3 border border-zinc-700/30 hover:border-zinc-600/50 transition-colors">
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon className="w-3.5 h-3.5 text-zinc-500" />
        <p className="text-xs text-zinc-500">{label}</p>
      </div>
      <p className={`text-sm text-zinc-100 font-medium truncate ${mono ? "font-mono" : ""}`}>{value}</p>
    </div>
  );
}
