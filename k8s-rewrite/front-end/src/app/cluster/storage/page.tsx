"use client";

import Link from "next/link";
import { HardDrive, Loader2 } from "lucide-react";
import { useState, useEffect, useCallback } from "react";

type StorageType = "all" | "local" | "nfs" | "samba" | "longhorn";

interface VolumeData {
  id: string;
  name: string;
  namespace: string;
  status: string;
  capacity: string;
  node: string;
  storageClass: string;
}

interface StorageClassData {
  name: string;
  provisioner: string;
  isDefault: boolean;
}

const STORAGE_TYPES: { key: StorageType; label: string }[] = [
  { key: "all", label: "All" },
  { key: "local", label: "Local" },
  { key: "nfs", label: "NFS" },
  { key: "samba", label: "Samba" },
  { key: "longhorn", label: "Longhorn" },
];

export default function StoragePage() {
  const [volumes, setVolumes] = useState<VolumeData[]>([]);
  const [storageClasses, setStorageClasses] = useState<StorageClassData[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StorageType>("all");

  const fetchVolumes = useCallback(async (type: StorageType) => {
    try {
      const url =
        type === "all"
          ? "/api/cluster/volumes"
          : `/api/cluster/volumes?type=${type}`;
      const res = await fetch(url);
      const data = await res.json();
      setVolumes(data.volumes || []);
      setStorageClasses(data.storageClasses || []);
    } catch {
      setVolumes([]);
      setStorageClasses([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchVolumes(filter);
  }, [filter, fetchVolumes]);

  useEffect(() => {
    const interval = setInterval(() => fetchVolumes(filter), 10000);
    return () => clearInterval(interval);
  }, [filter, fetchVolumes]);

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
        {/* Filter Pills */}
        <div className="flex items-center gap-2 mb-4">
          {STORAGE_TYPES.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filter === key
                  ? "bg-indigo-600 text-white"
                  : "bg-zinc-800/60 text-zinc-400 hover:bg-zinc-700/60 hover:text-zinc-200 border border-zinc-700/40"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {loading && volumes.length === 0 ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-12rem)]">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : volumes.length === 0 ? (
          <>
            {/* Storage Classes — always visible when cluster is up */}
            {storageClasses.length > 0 && (
              <div className="glass-card rounded-xl overflow-hidden mb-4">
                <div className="px-4 py-3 border-b border-zinc-700/40">
                  <h3 className="text-sm font-medium text-zinc-300">Available Storage Classes</h3>
                </div>
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-zinc-700/40">
                      <th className="text-left px-4 py-2 text-xs font-medium text-zinc-500">Name</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-zinc-500">Provisioner</th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-zinc-500">Default</th>
                    </tr>
                  </thead>
                  <tbody>
                    {storageClasses.map((sc) => (
                      <tr key={sc.name} className="border-b border-zinc-800/40">
                        <td className="px-4 py-2 text-sm text-zinc-200 font-mono">{sc.name}</td>
                        <td className="px-4 py-2 text-sm text-zinc-400">{sc.provisioner}</td>
                        <td className="px-4 py-2">
                          {sc.isDefault ? (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">
                              Default
                            </span>
                          ) : (
                            <span className="text-xs text-zinc-600">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="glass-card p-8 rounded-xl text-center">
              <HardDrive className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Volumes Yet</h3>
              <p className="text-sm text-zinc-500 max-w-md mx-auto">
                {filter !== "all"
                  ? `No ${filter} volumes found. Try another filter or deploy storage first.`
                  : "No volumes have been provisioned. Create a PVC referencing one of the Storage Classes above to provision your first volume."}
              </p>
            </div>
          </>
        ) : (
          <div className="glass-card rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Name</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Namespace</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Type</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Status</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Capacity</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Node</th>
                </tr>
              </thead>
              <tbody>
                {volumes.map((vol) => (
                  <tr key={vol.id || vol.name} className="border-b border-zinc-800/40 hover:bg-zinc-800/30">
                    <td className="px-4 py-3 text-sm text-zinc-200 font-mono">{vol.name}</td>
                    <td className="px-4 py-3 text-sm text-zinc-400">{vol.namespace}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400">
                        {vol.storageClass || "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        vol.status === "Bound" || vol.status === "Attached" || vol.status === "attached"
                          ? "bg-emerald-500/20 text-emerald-400"
                          : "bg-amber-500/20 text-amber-400"
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