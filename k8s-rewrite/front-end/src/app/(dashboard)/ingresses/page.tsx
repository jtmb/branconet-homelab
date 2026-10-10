"use client";

import { Network, Loader2, Search, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ViewportWrapper from "../viewport-wrapper";
import { useState, useEffect, useCallback, useMemo } from "react";
import { SortHeader, useSort } from "@/components/ui/sortable-header";

interface IngressData {
  name: string;
  namespace: string;
  state: string;
  host: string;
  target: string;
  age: string;
}

export default function IngressesPage() {
  const router = useRouter();
  const [ingresses, setIngresses] = useState<IngressData[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchIngresses = useCallback(async () => {
    try {
      const res = await fetch("/api/cluster/ingresses");
      const data = await res.json();
      setIngresses(data.ingresses || []);
    } catch {
      setIngresses([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const [search, setSearch] = useState("");

  const { sortKey, sortDir, toggle: toggleSort } = useSort("name");

  const filteredIngresses = useMemo(() => {
    let result = ingresses;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = ingresses.filter(
        (ing) => ing.name.toLowerCase().includes(q) || ing.namespace.toLowerCase().includes(q)
      );
    }
    return [...result].sort((a, b) => {
      const va = String((a as any)[sortKey] ?? "").toLowerCase();
      const vb = String((b as any)[sortKey] ?? "").toLowerCase();
      return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }, [ingresses, search, sortKey, sortDir]);

  useEffect(() => {
    setLoading(true);
    fetchIngresses();
  }, [fetchIngresses]);

  useEffect(() => {
    const interval = setInterval(() => fetchIngresses(), 10000);
    return () => clearInterval(interval);
  }, [fetchIngresses]);

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-4 text-xs text-zinc-500">
          <span className="text-zinc-300">Ingresses</span>
        </div>
        <div className="flex items-center gap-3 mb-6">
          <Network className="page-header-icon text-sky-400" />
          <h1 className="page-header-title">Ingresses</h1>
          <span className="text-sm text-zinc-500 ml-auto">{ingresses.length} ingresses</span>
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

        {loading && ingresses.length === 0 ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-12rem)]">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : ingresses.length === 0 ? (
          <div className="glass-card p-8 rounded-xl text-center">
            <Network className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Ingresses Found</h3>
            <p className="text-sm text-zinc-500">
              Create an Ingress resource to route external traffic to your services.
            </p>
          </div>
        ) : (
          <div className="glass-card rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-4 py-3"><SortHeader label="State" active={sortKey==="state"} dir={sortDir} onClick={()=>toggleSort("state")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Name" active={sortKey==="name"} dir={sortDir} onClick={()=>toggleSort("name")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Host" active={sortKey==="host"} dir={sortDir} onClick={()=>toggleSort("host")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Target" active={sortKey==="target"} dir={sortDir} onClick={()=>toggleSort("target")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Age" active={sortKey==="age"} dir={sortDir} onClick={()=>toggleSort("age")} /></th>
                </tr>
              </thead>
              <tbody>
                {filteredIngresses.map((ing) => (
                  <tr
                    key={`${ing.namespace}-${ing.name}`}
                    className="border-b border-zinc-800/40 hover:bg-zinc-800/30 cursor-pointer"
                    onClick={() => router.push(`/ingresses/${encodeURIComponent(ing.namespace)}/${encodeURIComponent(ing.name)}`)}
                  >
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${ing.state === "Ready" ? "badge-success" : "badge-warning"}`}>{ing.state}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-zinc-200 font-mono max-w-[260px] truncate" title={ing.name}>{ing.name}</td>
                    <td className="px-4 py-3 text-sm text-zinc-400 font-mono max-w-[220px] truncate" title={ing.host}>{ing.host}</td>
                    <td className="px-4 py-3 text-sm text-zinc-400 font-mono max-w-[300px] truncate" title={ing.target}>{ing.target}</td>
                    <td className="px-4 py-3 text-sm text-zinc-500">{ing.age}</td>
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
