"use client";

import Link from "next/link";
import { HardDrive, Loader2 } from "lucide-react";
import { useState, useEffect } from "react";

interface VolumeData {
  id: string;
  name: string;
  namespace: string;
  status: string;
  capacity: string;
  node: string;
}

export default function StoragePage() {
  const [volumes, setVolumes] = useState<VolumeData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchVolumes();
  }, []);

  async function fetchVolumes() {
    try {
      const res = await fetch("/api/cluster/volumes");
      const data = await res.json();
      setVolumes(data.volumes || []);
    } catch {
      setVolumes([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center gap-3">
          <Link href="/cluster" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors mr-2">
            Cluster
          </Link>
          <span className="text-zinc-700">|</span>
          <HardDrive className="w-6 h-6 text-purple-400" />
          <h1 className="text-xl font-bold text-zinc-100">Storage</h1>
          <span className="text-sm text-zinc-500 ml-auto">{loading ? "…" : `${volumes.length} volumes`}</span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {loading ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : volumes.length === 0 ? (
          <div className="glass-card p-8 rounded-xl text-center">
            <HardDrive className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Volumes Found</h3>
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
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Status</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Capacity</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Node</th>
                </tr>
              </thead>
              <tbody>
                {volumes.map((vol) => (
                  <tr key={vol.id} className="border-b border-zinc-800/40 hover:bg-zinc-800/30">
                    <td className="px-4 py-3 text-sm text-zinc-200 font-mono">{vol.name}</td>
                    <td className="px-4 py-3 text-sm text-zinc-400">{vol.namespace}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        vol.status === "Attached" ? "badge-success" : "badge-warning"
                      }`}>{vol.status}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-zinc-300">{vol.capacity}</td>
                    <td className="px-4 py-3 text-sm text-zinc-500">{vol.node || "—"}</td>
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