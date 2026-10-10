"use client";

import { useParams, useRouter } from "next/navigation";
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

export default function IngressDetailPage() {
  const router = useRouter();
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const [ingress, setIngress] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const fetchIngress = useCallback(async () => {
    try {
      const res = await fetch(`/api/cluster/ingresses/${namespace}/${name}`);
      if (res.status === 404) { setNotFound(true); setLoading(false); return; }
      const data = await res.json();
      setIngress(data.ingress);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [namespace, name]);

  useEffect(() => { fetchIngress(); }, [fetchIngress]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (notFound || !ingress) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <Network className="w-12 h-12 text-zinc-600" />
        <h2 className="text-lg font-semibold text-zinc-300">Ingress Not Found</h2>
        <p className="text-sm text-zinc-500">{namespace}/{name}</p>
        <Link href="/ingresses" className="text-indigo-400 hover:underline text-sm">← Back to Ingresses</Link>
      </div>
    );
  }

  const created = ingress.metadata?.creationTimestamp;
  const ageMs = created ? Date.now() - new Date(created).getTime() : 0;
  const ns = ingress.metadata?.namespace || namespace;
  const className = ingress.spec?.ingressClassName || "-";
  const tls = ingress.spec?.tls || [];
  const rules = ingress.spec?.rules || [];
  const lbIngress = ingress.status?.loadBalancer?.ingress;
  const lbStatus = lbIngress && lbIngress.length > 0
    ? lbIngress.map((i: any) => i.ip || i.hostname).join(", ")
    : "Pending";

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-4 text-xs text-zinc-500">
          <Link href="/ingresses" className="hover:text-zinc-300 transition-colors">Ingresses</Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-zinc-300">{ingress.metadata?.name}</span>
        </div>
        <div className="flex items-center gap-3 mb-6">
          <Network className="page-header-icon text-sky-400" />
          <h1 className="page-header-title">{ingress.metadata?.name}</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full ${lbIngress && lbIngress.length > 0 ? "badge-success" : "badge-warning"}`}>
            {lbIngress && lbIngress.length > 0 ? "Ready" : "Pending"}
          </span>
          <span className="text-xs text-zinc-500 bg-zinc-800/60 px-2 py-0.5 rounded-full">{ns}</span>
          <span className="text-xs text-zinc-500 ml-auto">{ageMs > 0 ? formatAge(ageMs) : "…"}</span>
          <ResourceActionsMenu resourceType="ingress" resource={ingress} onAction={fetchIngress} />
        </div>

        {/* Summary */}
        <section className="glass-card p-4 rounded-xl mb-6">
          <h2 className="text-sm font-semibold text-zinc-200 mb-3">Summary</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Ingress Class</p>
              <p className="text-sm font-medium text-zinc-200">{className}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Load Balancer</p>
              <p className="text-sm font-medium text-zinc-200">{lbStatus}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">TLS</p>
              <p className="text-sm font-medium text-zinc-200">{tls.length > 0 ? `${tls.length} host(s)` : "None"}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Rules</p>
              <p className="text-sm font-medium text-zinc-200">{rules.length} rule(s)</p>
            </div>
          </div>
        </section>

        {/* Rules */}
        {rules.length > 0 && (
          <section className="glass-card rounded-xl overflow-hidden mb-6">
            <div className="px-4 py-3 border-b border-zinc-700/40">
              <h2 className="text-sm font-semibold text-zinc-200">Rules</h2>
            </div>
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Host</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Path</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Backend</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule: any, ri: number) => {
                  const host = rule.host || "*";
                  const paths = rule.http?.paths || [];
                  if (paths.length === 0) {
                    return (
                      <tr key={ri} className="border-b border-zinc-800/40">
                        <td className="px-4 py-3 text-sm text-zinc-200 font-mono">{host}</td>
                        <td className="px-4 py-3 text-sm text-zinc-500">—</td>
                        <td className="px-4 py-3 text-sm text-zinc-500">—</td>
                      </tr>
                    );
                  }
                  return paths.map((p: any, pi: number) => {
                    const backend = p.backend?.service;
                    const backendStr = backend
                      ? `${backend.name}:${backend.port?.number || backend.port?.name || ""}`
                      : p.backend?.resource?.name || "—";
                    return (
                      <tr key={`${ri}-${pi}`} className="border-b border-zinc-800/40">
                        <td className="px-4 py-3 text-sm text-zinc-200 font-mono">{host}</td>
                        <td className="px-4 py-3 text-sm text-zinc-400 font-mono">
                          {p.path || "/"}{p.pathType ? ` (${p.pathType})` : ""}
                        </td>
                        <td className="px-4 py-3 text-sm text-indigo-400 font-mono">{backendStr}</td>
                      </tr>
                    );
                  });
                })}
              </tbody>
            </table>
          </section>
        )}

        {/* TLS */}
        {tls.length > 0 && (
          <section className="glass-card rounded-xl overflow-hidden mb-6">
            <div className="px-4 py-3 border-b border-zinc-700/40">
              <h2 className="text-sm font-semibold text-zinc-200">TLS</h2>
            </div>
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Hosts</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Secret Name</th>
                </tr>
              </thead>
              <tbody>
                {tls.map((t: any, ti: number) => (
                  <tr key={ti} className="border-b border-zinc-800/40">
                    <td className="px-4 py-3 text-sm text-zinc-300 font-mono">
                      {(t.hosts || []).join(", ") || "—"}
                    </td>
                    <td className="px-4 py-3 text-sm text-zinc-400 font-mono">{t.secretName || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </main>
      </ViewportWrapper>
    </div>
  );
}
