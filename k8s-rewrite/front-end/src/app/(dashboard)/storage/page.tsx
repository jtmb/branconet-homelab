"use client";

import Link from "next/link";
import { HardDrive, Loader2, Search } from "lucide-react";
import ViewportWrapper from "../viewport-wrapper";
import { useState, useEffect, useCallback, useMemo } from "react";
import { SortHeader, useSort } from "@/components/ui/sortable-header";

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

  const [search, setSearch] = useState("");

  const { sortKey, sortDir, toggle: toggleSort } = useSort("name");
  const { sortKey: scSortKey, sortDir: scSortDir, toggle: toggleScSort } = useSort("name");

  const filteredVolumes = useMemo(() => {
    let result = volumes;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = volumes.filter(
        (v) => v.name.toLowerCase().includes(q) || v.namespace.toLowerCase().includes(q)
      );
    }
    return [...result].sort((a, b) => {
      const va = String((a as any)[sortKey] ?? "").toLowerCase();
      const vb = String((b as any)[sortKey] ?? "").toLowerCase();
      return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }, [volumes, search, sortKey, sortDir]);

  const sortedStorageClasses = useMemo(() => {
    return [...storageClasses].sort((a, b) => {
      const va = String((a as any)[scSortKey] ?? "").toLowerCase();
      const vb = String((b as any)[scSortKey] ?? "").toLowerCase();
      return scSortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }, [storageClasses, scSortKey, scSortDir]);

  useEffect(() => {
    setLoading(true);
    fetchVolumes(filter);
  }, [filter, fetchVolumes]);

  useEffect(() => {
    const interval = setInterval(() => fetchVolumes(filter), 10000);
    return () => clearInterval(interval);
  }, [filter, fetchVolumes]);

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        <div className="flex items-center gap-3 mb-6">
          <HardDrive className="page-header-icon text-purple-400" />
          <h1 className="page-header-title">Storage</h1>
          <span className="text-sm text-zinc-500 ml-auto">{volumes.length} volumes</span>
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
          {/* Segmented Filter Control */}
          <div className="flex p-0.5">
            {STORAGE_TYPES.map(({ key, label }) => {
              const count = key === "all"
                ? volumes.length
                : volumes.filter((v) => v.storageClass?.toLowerCase().includes(key)).length;
              return (
                <button
                  key={key}
                  onClick={() => setFilter(key)}
                  className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                    filter === key
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  {label}
                  <span className={`ml-1.5 text-xs ${
                    filter === key ? "text-indigo-200" : "text-zinc-600"
                  }`}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
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
                      <th className="text-left px-4 py-2"><SortHeader label="Name" active={scSortKey==="name"} dir={scSortDir} onClick={()=>toggleScSort("name")} /></th>
                      <th className="text-left px-4 py-2"><SortHeader label="Provisioner" active={scSortKey==="provisioner"} dir={scSortDir} onClick={()=>toggleScSort("provisioner")} /></th>
                      <th className="text-left px-4 py-2"><SortHeader label="Default" active={scSortKey==="isDefault"} dir={scSortDir} onClick={()=>toggleScSort("isDefault")} /></th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedStorageClasses.map((sc) => (
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
                  <th className="text-left px-4 py-3"><SortHeader label="Name" active={sortKey==="name"} dir={sortDir} onClick={()=>toggleSort("name")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Namespace" active={sortKey==="namespace"} dir={sortDir} onClick={()=>toggleSort("namespace")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Type" active={sortKey==="storageClass"} dir={sortDir} onClick={()=>toggleSort("storageClass")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Status" active={sortKey==="status"} dir={sortDir} onClick={()=>toggleSort("status")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Capacity" active={sortKey==="capacity"} dir={sortDir} onClick={()=>toggleSort("capacity")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Node" active={sortKey==="node"} dir={sortDir} onClick={()=>toggleSort("node")} /></th>
                </tr>
              </thead>
              <tbody>
                {filteredVolumes.map((vol) => (
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
      </ViewportWrapper>
    </div>
  );
}