"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Network, Loader2, ChevronRight } from "lucide-react";
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

export default function ServiceDetailPage() {
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const [service, setService] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const fetchService = useCallback(async () => {
    try {
      const res = await fetch(`/api/cluster/services/${namespace}/${name}`);
      if (res.status === 404) { setNotFound(true); setLoading(false); return; }
      const data = await res.json();
      setService(data.service);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [namespace, name]);

  useEffect(() => { fetchService(); }, [fetchService]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (notFound || !service) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <Network className="w-12 h-12 text-zinc-600" />
        <h2 className="text-lg font-semibold text-zinc-300">Service Not Found</h2>
        <p className="text-sm text-zinc-500">{namespace}/{name}</p>
        <Link href="/services" className="text-indigo-400 hover:underline text-sm">← Back to Services</Link>
      </div>
    );
  }

  const created = service.metadata?.creationTimestamp;
  const ageMs = created ? Date.now() - new Date(created).getTime() : 0;
  const ns = service.metadata?.namespace || namespace;
  const svcType = service.spec?.type || "ClusterIP";
  const clusterIP = service.spec?.clusterIP || "-";
  const externalIPs = service.spec?.externalIPs || [];
  const lbIngress = service.status?.loadBalancer?.ingress;
  const externalIP =
    (lbIngress && lbIngress.length > 0)
      ? lbIngress.map((i: any) => i.ip || i.hostname).join(", ")
      : externalIPs.join(", ") || "-";
  const sessionAffinity = service.spec?.sessionAffinity || "None";
  const ports = service.spec?.ports || [];
  const selector = service.spec?.selector || {};

  return (
    <div className="flex flex-col min-h-0">
      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-4 text-xs text-zinc-500">
          <Link href="/services" className="hover:text-zinc-300 transition-colors">Services</Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-zinc-300">{service.metadata?.name}</span>
        </div>

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Network className="page-header-icon text-emerald-400" />
          <h1 className="page-header-title">{service.metadata?.name}</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            svcType === "LoadBalancer"
              ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
              : svcType === "NodePort"
              ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
              : "bg-zinc-500/10 text-zinc-400 border border-zinc-500/20"
          }`}>{svcType}</span>
          <span className="text-xs text-zinc-500 bg-zinc-800/60 px-2 py-0.5 rounded-full">{ns}</span>
          <span className="text-xs text-zinc-500 ml-auto">{ageMs > 0 ? formatAge(ageMs) : "…"}</span>
          <ResourceActionsMenu resourceType="service" resource={service} onAction={fetchService} />
        </div>

        {/* Summary */}
        <section className="glass-card p-4 rounded-xl mb-6">
          <h2 className="text-sm font-semibold text-zinc-200 mb-3">Summary</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Type</p>
              <p className="text-sm font-medium text-zinc-200">{svcType}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Cluster IP</p>
              <p className="text-sm font-medium text-zinc-200 font-mono">{clusterIP}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">External IP</p>
              <p className="text-sm font-medium text-zinc-200">{externalIP}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Session Affinity</p>
              <p className="text-sm font-medium text-zinc-200">{sessionAffinity}</p>
            </div>
          </div>
        </section>

        {/* Ports */}
        {ports.length > 0 && (
          <section className="glass-card rounded-xl overflow-hidden mb-6">
            <div className="px-4 py-3 border-b border-zinc-700/40">
              <h2 className="text-sm font-semibold text-zinc-200">Ports</h2>
            </div>
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Name</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Port</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Protocol</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Target Port</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Node Port</th>
                </tr>
              </thead>
              <tbody>
                {ports.map((p: any, pi: number) => (
                  <tr key={pi} className="border-b border-zinc-800/40">
                    <td className="px-4 py-3 text-sm text-zinc-200 font-mono">{p.name || "—"}</td>
                    <td className="px-4 py-3 text-sm text-zinc-300 font-mono">{p.port}</td>
                    <td className="px-4 py-3 text-sm text-zinc-400">{p.protocol || "TCP"}</td>
                    <td className="px-4 py-3 text-sm text-zinc-300 font-mono">{typeof p.targetPort === "object" ? JSON.stringify(p.targetPort) : (p.targetPort ?? "—")}</td>
                    <td className="px-4 py-3 text-sm text-zinc-400 font-mono">{p.nodePort || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* Selector */}
        {Object.keys(selector).length > 0 && (
          <section className="glass-card p-4 rounded-xl mb-6">
            <h2 className="text-sm font-semibold text-zinc-200 mb-3">Selector</h2>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(selector).map(([k, v]) => (
                <span key={k} className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono">
                  {k}={v as string}
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
