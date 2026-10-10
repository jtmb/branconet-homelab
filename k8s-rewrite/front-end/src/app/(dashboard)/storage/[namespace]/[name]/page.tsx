"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Database, Loader2, ChevronRight } from "lucide-react";
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

export default function PvcDetailPage() {
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const [pvc, setPvc] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const fetchPvc = useCallback(async () => {
    try {
      const res = await fetch(`/api/cluster/volumes/${namespace}/${name}`);
      if (res.status === 404) { setNotFound(true); setLoading(false); return; }
      const data = await res.json();
      setPvc(data.pvc);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [namespace, name]);

  useEffect(() => { fetchPvc(); }, [fetchPvc]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (notFound || !pvc) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <Database className="w-12 h-12 text-zinc-600" />
        <h2 className="text-lg font-semibold text-zinc-300">PVC Not Found</h2>
        <p className="text-sm text-zinc-500">{namespace}/{name}</p>
        <Link href="/storage" className="text-indigo-400 hover:underline text-sm">← Back to Storage</Link>
      </div>
    );
  }

  const created = pvc.metadata?.creationTimestamp;
  const ageMs = created ? Date.now() - new Date(created).getTime() : 0;
  const ns = pvc.metadata?.namespace || namespace;
  const pvcStatus = pvc.status?.phase || "Pending";
  const capacity = pvc.spec?.resources?.requests?.storage || pvc.status?.capacity?.storage || "—";
  const storageClass = pvc.spec?.storageClassName || "—";
  const accessModes = (pvc.spec?.accessModes || []).join(", ") || "—";
  const volumeName = pvc.spec?.volumeName || "—";
  const volumeMode = pvc.spec?.volumeMode || "Filesystem";

  return (
    <div className="flex flex-col min-h-0">
      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-4 text-xs text-zinc-500">
          <Link href="/storage" className="hover:text-zinc-300 transition-colors">Storage</Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-zinc-300">{pvc.metadata?.name}</span>
        </div>

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Database className="page-header-icon text-cyan-400" />
          <h1 className="page-header-title">{pvc.metadata?.name}</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            pvcStatus === "Bound" ? "badge-success" : "badge-warning"
          }`}>{pvcStatus}</span>
          <span className="text-xs text-zinc-500 bg-zinc-800/60 px-2 py-0.5 rounded-full">{ns}</span>
          <span className="text-xs text-zinc-500 ml-auto">{ageMs > 0 ? formatAge(ageMs) : "…"}</span>
          <ResourceActionsMenu resourceType="pvc" resource={pvc} onAction={fetchPvc} />
        </div>

        {/* Summary */}
        <section className="glass-card p-4 rounded-xl mb-6">
          <h2 className="text-sm font-semibold text-zinc-200 mb-3">Summary</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Status</p>
              <p className="text-sm font-medium text-zinc-200">{pvcStatus}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Capacity</p>
              <p className="text-sm font-medium text-zinc-200">{capacity}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Storage Class</p>
              <p className="text-sm font-medium text-zinc-200">{storageClass}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Access Modes</p>
              <p className="text-sm font-medium text-zinc-200">{accessModes}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 pt-3 mt-3 border-t border-zinc-700/40">
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Volume</p>
              <p className="text-sm font-medium text-zinc-200 font-mono">{volumeName}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Volume Mode</p>
              <p className="text-sm font-medium text-zinc-200">{volumeMode}</p>
            </div>
          </div>
        </section>
      </main>
      </ViewportWrapper>
    </div>
  );
}
