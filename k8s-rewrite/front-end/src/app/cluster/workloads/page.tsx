"use client";

import Link from "next/link";
import { Box, Loader2 } from "lucide-react";
import { useState, useEffect, useCallback } from "react";

type FilterType = "all" | "system" | "app";

interface PodData {
  id: string;
  name: string;
  namespace: string;
  status: string;
  node: string;
  appType: string | null;
}

export default function WorkloadsPage() {
  const [pods, setPods] = useState<PodData[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterType>("all");

  const fetchPods = useCallback(async (type: FilterType) => {
    try {
      const url = type === "all" ? "/api/cluster/pods" : `/api/cluster/pods?type=${type}`;
      const res = await fetch(url);
      const data = await res.json();
      setPods(data.pods || []);
    } catch {
      setPods([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchPods(filter);
  }, [filter, fetchPods]);

  useEffect(() => {
    const interval = setInterval(() => fetchPods(filter), 10000);
    return () => clearInterval(interval);
  }, [filter, fetchPods]);

  return (
    <div className="min-h-screen bg-zinc-950">
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center gap-3">
          <Link href="/cluster" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors mr-2">
            Cluster
          </Link>
          <span className="text-zinc-700">|</span>
          <Box className="w-6 h-6 text-emerald-400" />
          <h1 className="text-xl font-bold text-zinc-100">Workloads</h1>
          <span className="text-sm text-zinc-500 ml-auto">{loading ? "…" : `${pods.length} pods`}</span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Filter Pills */}
        <div className="flex items-center gap-2 mb-4">
          {(["all", "system", "app"] as FilterType[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filter === f
                  ? "bg-indigo-600 text-white"
                  : "bg-zinc-800/60 text-zinc-400 hover:bg-zinc-700/60 hover:text-zinc-200 border border-zinc-700/40"
              }`}
            >
              {f === "all" ? "All" : f === "system" ? "System" : "App"}
            </button>
          ))}
        </div>

        {loading && pods.length === 0 ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-12rem)]">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : pods.length === 0 ? (
          <div className="glass-card p-8 rounded-xl text-center">
            <Box className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Workloads Found</h3>
            <p className="text-sm text-zinc-500">
              Deploy a cluster first using the <a href="/deploy" className="text-indigo-400 hover:underline">Deploy</a> tab.
            </p>
          </div>
        ) : (
          <div className="glass-card rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Name</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Namespace</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Type</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Status</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Node</th>
                </tr>
              </thead>
              <tbody>
                {pods.map((pod) => (
                  <tr key={pod.id} className="border-b border-zinc-800/40 hover:bg-zinc-800/30">
                    <td className="px-4 py-3 text-sm text-zinc-200 font-mono">{pod.name}</td>
                    <td className="px-4 py-3 text-sm text-zinc-400">{pod.namespace}</td>
                    <td className="px-4 py-3">
                      {pod.appType ? (
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          pod.appType === "system" ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20" :
                          "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        }`}>{pod.appType}</span>
                      ) : (
                        <span className="text-xs text-zinc-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        pod.status === "Running" ? "badge-success" : "badge-warning"
                      }`}>{pod.status}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-zinc-500">{pod.node}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}