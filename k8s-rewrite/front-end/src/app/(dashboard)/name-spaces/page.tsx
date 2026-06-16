"use client";

import { FolderTree, Loader2, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import ViewportWrapper from "../viewport-wrapper";
import { SortHeader, useSort } from "@/components/ui/sortable-header";
import { useState, useEffect, useCallback, useMemo } from "react";

interface NamespaceData {
  name: string;
  status: string;
  age: string;
}

export default function NamespacesPage() {
  const router = useRouter();
  const [namespaces, setNamespaces] = useState<NamespaceData[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchNamespaces = useCallback(async () => {
    try {
      const res = await fetch("/api/cluster/namespaces");
      const data = await res.json();
      setNamespaces(data.namespaces || []);
    } catch {
      setNamespaces([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const [search, setSearch] = useState("");

  const { sortKey, sortDir, toggle: toggleSort } = useSort("name");

  const filteredNamespaces = useMemo(() => {
    let result = namespaces;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = namespaces.filter((ns) => ns.name.toLowerCase().includes(q));
    }
    return [...result].sort((a, b) => {
      const va = String((a as any)[sortKey] ?? "").toLowerCase();
      const vb = String((b as any)[sortKey] ?? "").toLowerCase();
      return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }, [namespaces, search, sortKey, sortDir]);

  useEffect(() => {
    setLoading(true);
    fetchNamespaces();
  }, [fetchNamespaces]);

  useEffect(() => {
    const interval = setInterval(() => fetchNamespaces(), 10000);
    return () => clearInterval(interval);
  }, [fetchNamespaces]);

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        <div className="flex items-center gap-3 mb-6">
          <FolderTree className="page-header-icon text-violet-400" />
          <h1 className="page-header-title">Namespaces</h1>
          <span className="text-sm text-zinc-500 ml-auto">{namespaces.length} namespaces</span>
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

        {loading && namespaces.length === 0 ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-12rem)]">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : namespaces.length === 0 ? (
          <div className="glass-card p-8 rounded-xl text-center">
            <FolderTree className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Namespaces Found</h3>
            <p className="text-sm text-zinc-500">
              Deploy a cluster first using the <a href="/deploy" className="text-indigo-400 hover:underline">Deploy</a> tab.
            </p>
          </div>
        ) : (
          <div className="glass-card rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-4 py-3"><SortHeader label="Name" active={sortKey==="name"} dir={sortDir} onClick={()=>toggleSort("name")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Status" active={sortKey==="status"} dir={sortDir} onClick={()=>toggleSort("status")} /></th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Age</th>
                </tr>
              </thead>
              <tbody>
                {filteredNamespaces.map((ns) => (
                  <tr key={ns.name} className="border-b border-zinc-800/40 hover:bg-zinc-800/30 cursor-pointer" onClick={() => router.push(`/name-spaces/${encodeURIComponent(ns.name)}`)}>
                    <td className="px-4 py-3 text-sm text-zinc-200 font-mono">{ns.name}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        ns.status === "Active" ? "badge-success" : "badge-warning"
                      }`}>{ns.status}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-zinc-500">{ns.age}</td>
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
