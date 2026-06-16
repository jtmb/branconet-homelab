"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { FolderTree, Loader2 } from "lucide-react";
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

export default function NamespaceDetailPage() {
  const router = useRouter();
  const { name } = useParams<{ name: string }>();
  const [ns, setNs] = useState<any>(null);
  const [pods, setPods] = useState<any[]>([]);
  const [deployments, setDeployments] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const fetchNs = useCallback(async () => {
    try {
      const res = await fetch(`/api/cluster/namespaces/${name}`);
      if (res.status === 404) { setNotFound(true); setLoading(false); return; }
      const data = await res.json();
      setNs(data.namespace);
      setPods(data.pods || []);
      setDeployments(data.deployments || []);
      setServices(data.services || []);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [name]);

  useEffect(() => { fetchNs(); }, [fetchNs]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (notFound || !ns) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <FolderTree className="w-12 h-12 text-zinc-600" />
        <h2 className="text-lg font-semibold text-zinc-300">Namespace Not Found</h2>
        <p className="text-sm text-zinc-500">{name}</p>
        <Link href="/name-spaces" className="text-indigo-400 hover:underline text-sm">← Back to Namespaces</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        <div className="flex items-center gap-3 mb-6">
          <FolderTree className="page-header-icon text-violet-400" />
          <h1 className="page-header-title">{ns.name}</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            ns.status === "Active" ? "badge-success" : "badge-warning"
          }`}>{ns.status}</span>
          <span className="text-xs text-zinc-500 ml-auto">{ns.age}</span>
          <ResourceActionsMenu resourceType="namespace" resource={ns} />
        </div>

        {/* Deployments */}
        <section className="glass-card rounded-xl overflow-hidden mb-6">
        <div className="px-4 py-3 border-b border-zinc-700/40 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-200">
            Deployments {deployments.length > 0 && `(${deployments.length})`}
          </h2>
        </div>
        {deployments.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-zinc-500">No deployments</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-700/40">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Name</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Ready</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Age</th>
              </tr>
            </thead>
            <tbody>
              {deployments.map((d: any) => (
                <tr key={d.name} className="border-b border-zinc-800/40 hover:bg-zinc-800/30 cursor-pointer" onClick={() => router.push(`/deployments/${encodeURIComponent(ns.name)}/${encodeURIComponent(d.name)}`)}>
                  <td className="px-4 py-2.5 text-sm text-zinc-200 font-mono">{d.name}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      d.ready === d.ready.split("/")[1] ? "badge-success" : "badge-warning"
                    }`}>{d.ready}</span>
                  </td>
                  <td className="px-4 py-2.5 text-sm text-zinc-500">{d.age}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

        {/* Pods */}
        <section className="glass-card rounded-xl overflow-hidden mb-6">
        <div className="px-4 py-3 border-b border-zinc-700/40 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-200">
            Pods {pods.length > 0 && `(${pods.length})`}
          </h2>
        </div>
        {pods.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-zinc-500">No pods</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-700/40">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Name</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Status</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Node</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Age</th>
              </tr>
            </thead>
            <tbody>
              {pods.map((p: any) => {
                const pCreated = p.metadata?.creationTimestamp;
                const pAgeMs = pCreated ? Date.now() - new Date(pCreated).getTime() : 0;
                return (
                  <tr key={p.metadata?.uid || p.metadata?.name} className="border-b border-zinc-800/40 hover:bg-zinc-800/30 cursor-pointer" onClick={() => router.push(`/pods/${encodeURIComponent(ns.name)}/${encodeURIComponent(p.metadata?.name)}`)}>
                    <td className="px-4 py-2.5 text-sm text-zinc-200 font-mono">{p.metadata?.name}</td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        p.status?.phase === "Running" ? "badge-success" : p.status?.phase === "Pending" ? "badge-warning" : "badge-error"
                      }`}>{p.status?.phase || "Unknown"}</span>
                    </td>
                    <td className="px-4 py-2.5 text-sm text-zinc-500">{p.spec?.nodeName || "-"}</td>
                    <td className="px-4 py-2.5 text-sm text-zinc-500">{pAgeMs > 0 ? formatAge(pAgeMs) : "…"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

        {/* Services */}
        <section className="glass-card rounded-xl overflow-hidden mb-6">
        <div className="px-4 py-3 border-b border-zinc-700/40 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-200">
            Services {services.length > 0 && `(${services.length})`}
          </h2>
        </div>
        {services.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-zinc-500">No services</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-700/40">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Name</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Type</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Cluster IP</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Ports</th>
              </tr>
            </thead>
            <tbody>
              {services.map((s: any) => (
                <tr key={s.name} className="border-b border-zinc-800/40 hover:bg-zinc-800/30">
                  <td className="px-4 py-2.5 text-sm text-zinc-200 font-mono">{s.name}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      s.type === "LoadBalancer" ? "bg-purple-500/10 text-purple-400 border border-purple-500/20" :
                      s.type === "NodePort" ? "bg-amber-500/10 text-amber-400 border border-amber-500/20" :
                      "bg-zinc-500/10 text-zinc-400 border border-zinc-500/20"
                    }`}>{s.type}</span>
                  </td>
                  <td className="px-4 py-2.5 text-sm text-zinc-400 font-mono">{s.clusterIP}</td>
                  <td className="px-4 py-2.5 text-sm text-zinc-500 font-mono text-xs">{s.ports}</td>
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
