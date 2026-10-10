"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Server, Loader2, Cpu, MemoryStick, HardDrive, Monitor, Network, Container, Hash, ChevronRight } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import ViewportWrapper from "../../viewport-wrapper";
import ResourceActionsMenu from "../../resource-actions-menu";

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

export default function NodeDetailPage() {
  const router = useRouter();
  const { hostname } = useParams<{ hostname: string }>();
  const [node, setNode] = useState<any>(null);
  const [pods, setPods] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const fetchNode = useCallback(async () => {
    try {
      const res = await fetch(`/api/cluster/nodes/${encodeURIComponent(hostname)}`);
      if (res.status === 404) { setNotFound(true); setLoading(false); return; }
      if (!res.ok) throw new Error("Failed to fetch node");
      const data = await res.json();
      setNode(data.node);
      setPods(data.pods || []);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [hostname]);

  useEffect(() => { fetchNode(); }, [fetchNode]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (notFound || !node) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <Server className="w-12 h-12 text-zinc-600" />
        <h2 className="text-lg font-semibold text-zinc-300">Node Not Found</h2>
        <p className="text-sm text-zinc-500">{hostname}</p>
        <Link href="/nodes" className="text-indigo-400 hover:underline text-sm">← Back to Nodes</Link>
      </div>
    );
  }

  const created = node.metadata?.creationTimestamp;
  const ageMs = created ? Date.now() - new Date(created).getTime() : 0;

  // Conditions
  const conditions = (node.status?.conditions || []).map((c: any) => ({
    type: c.type,
    status: c.status,
    reason: c.reason || "-",
    message: c.message || "-",
  }));

  const isReady = conditions.find((c: any) => c.type === "Ready")?.status === "True";

  // Addressing
  const addresses = node.status?.addresses || [];
  const internalIp = addresses.find((a: any) => a.type === "InternalIP")?.address || "-";
  const externalIp = addresses.find((a: any) => a.type === "ExternalIP")?.address || null;
  const hostnameAddr = addresses.find((a: any) => a.type === "Hostname")?.address || null;

  // Roles from labels
  const labels = node.metadata?.labels || {};
  const roles: string[] = [];
  if ("node-role.kubernetes.io/control-plane" in labels) roles.push("control-plane");
  if ("node-role.kubernetes.io/master" in labels) roles.push("master");
  if (!roles.length) roles.push("worker");

  // Capacity & Allocatable
  const capacity = node.status?.capacity || {};
  const allocatable = node.status?.allocatable || {};
  const nodeInfo = node.status?.nodeInfo || {};

  // Labels display (filter out kubernetes.io and node-role prefixes for the labels chip area)
  const displayLabels = Object.entries(labels).filter(
    ([k]) => !k.startsWith("kubernetes.io/") && !k.startsWith("node-role.kubernetes.io/") && !k.startsWith("node.kubernetes.io/")
  );

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-4 text-xs text-zinc-500">
          <Link href="/nodes" className="hover:text-zinc-300 transition-colors">Nodes</Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-zinc-300">{node.metadata?.name}</span>
        </div>
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Server className="page-header-icon text-blue-400" />
          <h1 className="page-header-title">{node.metadata?.name}</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            isReady ? "badge-success" : "badge-warning"
          }`}>{isReady ? "Active" : "Not Ready"}</span>
          {roles.map((r) => (
            <span key={r} className={`text-[10px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded whitespace-nowrap ${
              r === "control-plane" || r === "master" ? "bg-amber-500/10 text-amber-400" : "bg-blue-500/10 text-blue-400"
            }`}>{r}</span>
          ))}
          <span className="text-xs text-zinc-500 ml-auto">{ageMs > 0 ? formatAge(ageMs) : "…"}</span>
          <ResourceActionsMenu resourceType="node" resource={node} />
        </div>

        {/* Details — Stat Cards */}
        <section className="glass-card rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-zinc-300 mb-4">Details</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard icon={Monitor} label="OS Image" value={nodeInfo.osImage || "-"} />
            <StatCard icon={Hash} label="Kernel" value={nodeInfo.kernelVersion || "-"} />
            <StatCard icon={Container} label="Runtime" value={nodeInfo.containerRuntimeVersion || "-"} />
            <StatCard icon={Network} label="Kubelet" value={nodeInfo.kubeletVersion || "-"} />
            <StatCard icon={Network} label="Internal IP" value={internalIp} mono />
            {externalIp && <StatCard icon={Network} label="External IP" value={externalIp} mono />}
            <StatCard icon={Cpu} label="CPU Capacity" value={capacity.cpu || "-"} />
            <StatCard icon={MemoryStick} label="Memory Capacity" value={capacity.memory || "-"} />
          </div>
          {/* Pods section */}
          <div className="mt-4 pt-4 border-t border-zinc-700/40">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">
                Pods {pods.length > 0 && `(${pods.length})`}
              </p>
            </div>
            {pods.length === 0 ? (
              <p className="text-sm text-zinc-500">No pods scheduled on this node</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {pods.map((p: any) => {
                  const ns = p.metadata?.namespace || "default";
                  const pname = p.metadata?.name || "unknown";
                  const phase = p.status?.phase || "Unknown";
                  return (
                    <button
                      key={`${ns}/${pname}`}
                      onClick={() => router.push(`/pods/${encodeURIComponent(ns)}/${encodeURIComponent(pname)}`)}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800/40 border border-zinc-700/30 hover:border-zinc-600/50 transition-colors text-left"
                    >
                      <Container className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
                      <span className="text-sm text-zinc-200 font-mono truncate">{pname}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ml-auto shrink-0 ${
                        phase === "Running" ? "badge-success" :
                        phase === "Pending" ? "badge-warning" : "badge-error"
                      }`}>{phase}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
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

        {/* Labels */}
        {displayLabels.length > 0 && (
          <section className="glass-card rounded-xl p-5 mb-6">
            <h2 className="text-sm font-semibold text-zinc-300 mb-3">Labels</h2>
            <div className="flex flex-wrap gap-1.5">
              {displayLabels.map(([k, v]) => (
                <span key={k} className="text-xs px-2 py-0.5 rounded-md bg-zinc-800/80 text-zinc-300 font-mono ring-1 ring-zinc-700/40">
                  {k}={v as string}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Taints */}
        {node.spec?.taints?.length > 0 && (
          <section className="glass-card rounded-xl p-5 mb-6">
            <h2 className="text-sm font-semibold text-zinc-300 mb-3">Taints</h2>
            <div className="flex flex-wrap gap-1.5">
              {node.spec.taints.map((t: any, i: number) => (
                <span key={i} className="text-xs px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-400 font-mono ring-1 ring-amber-500/20">
                  {t.key}={t.value}:{t.effect}
                </span>
              ))}
            </div>
          </section>
        )}
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
