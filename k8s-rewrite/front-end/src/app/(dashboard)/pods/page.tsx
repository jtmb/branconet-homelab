"use client";

import { Container, Loader2, Search, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ViewportWrapper from "../viewport-wrapper";
import { SortHeader, useSort } from "@/components/ui/sortable-header";
import { useState, useEffect, useCallback, useMemo } from "react";

interface PodData {
  id: string;
  name: string;
  namespace: string;
  status: string;
  ready: string;
  restarts: number;
  image: string;
  ip: string;
  node: string;
  created: string | null;
}

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

export default function PodsPage() {
  const router = useRouter();
  const [pods, setPods] = useState<PodData[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPods = useCallback(async () => {
    try {
      const res = await fetch("/api/cluster/pods");
      const data = await res.json();
      setPods(data.pods || []);
    } catch {
      setPods([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const [search, setSearch] = useState("");

  const { sortKey, sortDir, toggle: toggleSort } = useSort("name");

  const filteredPods = useMemo(() => {
    let result = pods;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = pods.filter(
        (p) => p.name.toLowerCase().includes(q) || p.namespace.toLowerCase().includes(q)
      );
    }
    return [...result].sort((a, b) => {
      const va = String((a as any)[sortKey] ?? "").toLowerCase();
      const vb = String((b as any)[sortKey] ?? "").toLowerCase();
      return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }, [pods, search, sortKey, sortDir]);

  useEffect(() => { fetchPods(); }, [fetchPods]);

  useEffect(() => {
    const interval = setInterval(fetchPods, 10000);
    return () => clearInterval(interval);
  }, [fetchPods]);

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-4 text-xs text-zinc-500">
          <span className="text-zinc-300">Pods</span>
        </div>
        <div className="flex items-center gap-3 mb-6">
          <Container className="page-header-icon text-cyan-400" />
          <h1 className="page-header-title">Pods</h1>
          <span className="text-sm text-zinc-500 ml-auto">{pods.length} pods</span>
        </div>
        <div className="flex items-center gap-3 mb-6">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              placeholder="Search…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: '100%',
                background: 'rgb(39,39,42)',
                border: 'none',
                outline: 'none',
                boxShadow: 'none',
                padding: '0.5rem 0.75rem 0.5rem 2.25rem',
                fontSize: '0.875rem',
                lineHeight: '1.25rem',
                color: '#e4e4e7',
                borderRadius: '0.5rem',
                WebkitAppearance: 'none',
                MozAppearance: 'none',
                appearance: 'none',
              }}
            />
          </div>
        </div>
        {loading && pods.length === 0 ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-12rem)]">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : pods.length === 0 ? (
          <div className="glass-card p-8 rounded-xl text-center">
            <Container className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Pods Found</h3>
            <p className="text-sm text-zinc-500">
              Deploy a cluster first using the <a href="/deploy" className="text-indigo-400 hover:underline">Deploy</a> tab.
            </p>
          </div>
        ) : (
          <div className="glass-card rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-3 py-2.5"><SortHeader label="Status" active={sortKey==="status"} dir={sortDir} onClick={()=>toggleSort("status")} /></th>
                  <th className="text-left px-3 py-2.5"><SortHeader label="Name" active={sortKey==="name"} dir={sortDir} onClick={()=>toggleSort("name")} /></th>
                  <th className="text-left px-3 py-2.5"><SortHeader label="Namespace" active={sortKey==="namespace"} dir={sortDir} onClick={()=>toggleSort("namespace")} /></th>
                  <th className="text-left px-3 py-2.5"><SortHeader label="Image" active={sortKey==="image"} dir={sortDir} onClick={()=>toggleSort("image")} /></th>
                  <th className="text-left px-3 py-2.5"><SortHeader label="Ready" active={sortKey==="ready"} dir={sortDir} onClick={()=>toggleSort("ready")} /></th>
                  <th className="text-left px-3 py-2.5"><SortHeader label="Restarts" active={sortKey==="restarts"} dir={sortDir} onClick={()=>toggleSort("restarts")} /></th>
                  <th className="text-left px-3 py-2.5"><SortHeader label="IP" active={sortKey==="ip"} dir={sortDir} onClick={()=>toggleSort("ip")} /></th>
                  <th className="text-left px-3 py-2.5"><SortHeader label="Node" active={sortKey==="node"} dir={sortDir} onClick={()=>toggleSort("node")} /></th>
                  <th className="text-left px-3 py-2.5 text-xs font-medium text-zinc-400">Age</th>
                </tr>
              </thead>
              <tbody>
                {filteredPods.map((pod) => {
                  const ageMs = pod.created ? Date.now() - new Date(pod.created).getTime() : 0;
                  return (
                  <tr key={pod.id} className="border-b border-zinc-800/40 hover:bg-zinc-800/30 cursor-pointer" onClick={() => router.push(`/pods/${encodeURIComponent(pod.namespace)}/${encodeURIComponent(pod.name)}`)}>
                    <td className="px-3 py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        pod.status === "Running" ? "badge-success" : pod.status === "Pending" ? "badge-warning" : "badge-error"
                      }`}>{pod.status}</span>
                    </td>
                    <td className="px-3 py-2.5 text-sm text-zinc-200 font-mono max-w-[200px] truncate" title={pod.name}>{pod.name}</td>
                    <td className="px-3 py-2.5 text-sm text-zinc-400">{pod.namespace}</td>
                    <td className="px-3 py-2.5 text-sm text-zinc-500 font-mono max-w-[180px] truncate" title={pod.image}>{pod.image}</td>
                    <td className="px-3 py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        pod.ready.split("/")[0] === pod.ready.split("/")[1] ? "badge-success" : "badge-warning"
                      }`}>{pod.ready}</span>
                    </td>
                    <td className="px-3 py-2.5 text-sm text-zinc-400">{pod.restarts}</td>
                    <td className="px-3 py-2.5 text-sm text-zinc-500 font-mono">{pod.ip}</td>
                    <td className="px-3 py-2.5 text-sm text-zinc-500">{pod.node}</td>
                    <td className="px-3 py-2.5 text-sm text-zinc-500">{ageMs > 0 ? formatAge(ageMs) : "…"}</td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
      </ViewportWrapper>
    </div>
  );
}
