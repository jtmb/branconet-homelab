"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Layers,
  Loader2,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
  GitBranch,
  Rocket,
  Ship,
  Box,
  Globe,
  Network,
  Database,
  Shield,
  FileText,
} from "lucide-react";
import { useState, useEffect, useCallback, useMemo } from "react";
import ViewportWrapper from "../../../viewport-wrapper";
import type { KustomizationDetail } from "@/lib/flux";

function fmtTime(ts: string | null): string {
  if (!ts) return "—";
  try { return new Date(ts).toLocaleString(); } catch { return ts; }
}

function kindIcon(kind: string) {
  switch (kind) {
    case "Deployment": return <Rocket className="w-3.5 h-3.5 text-sky-400" />;
    case "Service": return <Network className="w-3.5 h-3.5 text-emerald-400" />;
    case "Ingress": return <Globe className="w-3.5 h-3.5 text-amber-400" />;
    case "ConfigMap": return <FileText className="w-3.5 h-3.5 text-zinc-400" />;
    case "Secret": return <Shield className="w-3.5 h-3.5 text-purple-400" />;
    case "PersistentVolumeClaim": return <Database className="w-3.5 h-3.5 text-cyan-400" />;
    case "Namespace": return <Box className="w-3.5 h-3.5 text-cyan-400" />;
    case "HelmRelease": return <Ship className="w-3.5 h-3.5 text-amber-400" />;
    default: return <Layers className="w-3.5 h-3.5 text-zinc-400" />;
  }
}

function resourceLink(kind: string, name: string, namespace: string, router: ReturnType<typeof useRouter>): string | null {
  switch (kind) {
    case "Deployment": return `/deployments/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`;
    case "Service": return `/services/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`;
    case "Ingress": return `/ingresses/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`;
    case "PersistentVolumeClaim": return `/storage/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`;
    default: return null;
  }
}

export default function BundleDetailPage() {
  const router = useRouter();
  const params = useParams<{ repoName: string; bundleName: string }>();
  const repoName = decodeURIComponent(params.repoName);
  const bundleName = decodeURIComponent(params.bundleName);

  const [detail, setDetail] = useState<KustomizationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const fetchDetail = useCallback(async () => {
    try {
      const res = await fetch(`/api/flux/kustomizations/${encodeURIComponent(bundleName)}`);
      if (res.status === 404) { setNotFound(true); setLoading(false); return; }
      const data = await res.json();
      setDetail(data);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [bundleName]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  // Group resources by kind
  const resourcesByKind = useMemo(() => {
    if (!detail) return [];
    const groups = new Map<string, { kind: string; name: string; namespace: string; apiGroup: string }[]>();
    for (const r of detail.resources) {
      const group = groups.get(r.kind) || [];
      group.push(r);
      groups.set(r.kind, group);
    }
    return Array.from(groups.entries())
      .sort(([a], [b]) => a.localeCompare(b));
  }, [detail]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (notFound || !detail) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <Layers className="w-12 h-12 text-zinc-600" />
        <h2 className="text-lg font-semibold text-zinc-300">Kustomization Not Found</h2>
        <p className="text-sm text-zinc-500">{bundleName}</p>
        <Link href={`/flux/${encodeURIComponent(repoName)}`} className="text-indigo-400 hover:underline text-sm">
          ← Back to {repoName}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-0">
      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-4 text-xs text-zinc-500">
          <Link href="/flux" className="hover:text-zinc-300 transition-colors">Flux</Link>
          <ChevronRight className="w-3 h-3" />
          <Link href={`/flux/${encodeURIComponent(repoName)}`} className="hover:text-zinc-300 transition-colors">{repoName}</Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-zinc-300">{bundleName}</span>
        </div>

        {/* Header */}
        <div className="flex items-center gap-3 mb-2 flex-wrap">
          <Layers className="page-header-icon text-indigo-400" />
          <h1 className="page-header-title">{bundleName}</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            detail.ready ? "badge-success" : "badge-warning"
          }`}>{detail.ready ? "Ready" : "Not Ready"}</span>
          {detail.suspended && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-500/10 text-zinc-400 border border-zinc-500/20">Suspended</span>
          )}
        </div>

        {/* Meta line */}
        <div className="flex items-center gap-4 text-xs text-zinc-500 mb-6 flex-wrap">
          <span>Source: <span className="text-zinc-300 font-mono">{detail.sourceRef.kind}/{detail.sourceRef.name}</span></span>
          <span>Path: <span className="text-zinc-300 font-mono">{detail.path}</span></span>
          <span>Age: <span className="text-zinc-300">{detail.age || "—"}</span></span>
          <span>Last Sync: <span className="text-zinc-300">{fmtTime(detail.lastSync)}</span></span>
        </div>

        {/* Resources grouped by kind */}
        {resourcesByKind.map(([kind, resources]) => (
          <section key={kind} className="glass-card rounded-xl overflow-hidden mb-6">
            <div className="px-4 py-3 border-b border-zinc-700/40 flex items-center gap-2">
              {kindIcon(kind)}
              <h2 className="text-sm font-semibold text-zinc-200">{kind}</h2>
              <span className="text-xs text-zinc-500">({resources.length})</span>
            </div>
            <table className="w-full table-fixed">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Name</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 w-56">Namespace</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 hidden sm:table-cell w-44">API Group</th>
                </tr>
              </thead>
              <tbody>
                {resources.map((r) => {
                  const link = resourceLink(kind, r.name, r.namespace, router);
                  return (
                    <tr
                      key={`${r.namespace}/${r.name}`}
                      onClick={link ? () => router.push(link) : undefined}
                      className={`border-b border-zinc-800/40 ${link ? "hover:bg-zinc-800/30 cursor-pointer" : ""} transition-colors`}
                    >
                      <td className="px-4 py-2.5 truncate">
                        <span className={`text-sm ${link ? "text-indigo-400 hover:text-indigo-300" : "text-zinc-200"} font-mono transition-colors`}>
                          {r.name}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-sm text-zinc-400 font-mono truncate">{r.namespace}</td>
                      <td className="px-4 py-2.5 text-sm text-zinc-500 font-mono hidden sm:table-cell truncate">{r.apiGroup || "core"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        ))}

        {resourcesByKind.length === 0 && (
          <div className="glass-card rounded-xl p-8 text-center text-sm text-zinc-500 mb-6">
            No managed resources found in inventory
          </div>
        )}

        {/* Conditions */}
        <section className="glass-card rounded-xl overflow-hidden mb-6">
          <div className="px-4 py-3 border-b border-zinc-700/40">
            <h2 className="text-sm font-semibold text-zinc-200">
              Conditions {detail.conditions.length > 0 && `(${detail.conditions.length})`}
            </h2>
          </div>
          {detail.conditions.length === 0 ? (
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
                {detail.conditions.map((c) => (
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
      </main>
      </ViewportWrapper>
    </div>
  );
}
