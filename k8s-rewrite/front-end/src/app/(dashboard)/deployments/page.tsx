"use client";

import { Rocket, Loader2, Search, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ViewportWrapper from "../viewport-wrapper";
import { useState, useEffect, useCallback, useMemo } from "react";
import { SortHeader, useSort } from "@/components/ui/sortable-header";

interface DeploymentData {
  name: string;
  namespace: string;
  state: string;
  image: string;
  ready: string;
  upToDate: number;
  available: number;
  restarts: number;
  age: string;
  health: string;
}

export default function DeploymentsPage() {
  const router = useRouter();
  const [deployments, setDeployments] = useState<DeploymentData[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDeployments = useCallback(async () => {
    try {
      const res = await fetch("/api/cluster/deployments");
      const data = await res.json();
      setDeployments(data.deployments || []);
    } catch {
      setDeployments([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const [search, setSearch] = useState("");

  const { sortKey, sortDir, toggle: toggleSort } = useSort("name");

  const filteredDeployments = useMemo(() => {
    let result = deployments;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = deployments.filter(
        (d) => d.name.toLowerCase().includes(q) || d.namespace.toLowerCase().includes(q)
      );
    }
    return [...result].sort((a, b) => {
      const va = String((a as any)[sortKey] ?? "").toLowerCase();
      const vb = String((b as any)[sortKey] ?? "").toLowerCase();
      return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }, [deployments, search, sortKey, sortDir]);

  useEffect(() => {
    setLoading(true);
    fetchDeployments();
  }, [fetchDeployments]);

  useEffect(() => {
    const interval = setInterval(() => fetchDeployments(), 10000);
    return () => clearInterval(interval);
  }, [fetchDeployments]);

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-4 text-xs text-zinc-500">
          <span className="text-zinc-300">Deployments</span>
        </div>
        <div className="flex items-center gap-3 mb-6">
          <Rocket className="page-header-icon text-amber-400" />
          <h1 className="page-header-title">Deployments</h1>
          <span className="text-sm text-zinc-500 ml-auto">{deployments.length} deployments</span>
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

        {loading && deployments.length === 0 ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-12rem)]">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : deployments.length === 0 ? (
          <div className="glass-card p-8 rounded-xl text-center">
            <Rocket className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Deployments Found</h3>
            <p className="text-sm text-zinc-500">
              Deploy workloads via GitOps or use the <a href="/deploy" className="text-indigo-400 hover:underline">Deploy</a> tab.
            </p>
          </div>
        ) : (
          <div className="glass-card rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-3 py-3"><SortHeader label="State" active={sortKey==="state"} dir={sortDir} onClick={()=>toggleSort("state")} /></th>
                  <th className="text-left px-3 py-3"><SortHeader label="Name" active={sortKey==="name"} dir={sortDir} onClick={()=>toggleSort("name")} /></th>
                  <th className="text-left px-3 py-3"><SortHeader label="Image" active={sortKey==="image"} dir={sortDir} onClick={()=>toggleSort("image")} /></th>
                  <th className="text-left px-3 py-3"><SortHeader label="Ready" active={sortKey==="ready"} dir={sortDir} onClick={()=>toggleSort("ready")} /></th>
                  <th className="text-left px-3 py-3"><SortHeader label="Up To Date" active={sortKey==="upToDate"} dir={sortDir} onClick={()=>toggleSort("upToDate")} /></th>
                  <th className="text-left px-3 py-3"><SortHeader label="Available" active={sortKey==="available"} dir={sortDir} onClick={()=>toggleSort("available")} /></th>
                  <th className="text-left px-3 py-3"><SortHeader label="Restarts" active={sortKey==="restarts"} dir={sortDir} onClick={()=>toggleSort("restarts")} /></th>
                  <th className="text-left px-3 py-3"><SortHeader label="Age" active={sortKey==="age"} dir={sortDir} onClick={()=>toggleSort("age")} /></th>
                  <th className="text-left px-3 py-3"><SortHeader label="Health" active={sortKey==="health"} dir={sortDir} onClick={()=>toggleSort("health")} /></th>
                </tr>
              </thead>
              <tbody>
                {filteredDeployments.map((dep) => (
                  <tr key={`${dep.namespace}-${dep.name}`} className="border-b border-zinc-800/40 hover:bg-zinc-800/30 cursor-pointer" onClick={() => router.push(`/deployments/${encodeURIComponent(dep.namespace)}/${encodeURIComponent(dep.name)}`)}>
                    <td className="px-3 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${dep.state === "Ready" ? "badge-success" : dep.state === "Updating" ? "badge-warning" : "badge-error"}`}>{dep.state}</span>
                    </td>
                    <td className="px-3 py-3 text-sm text-zinc-200 font-mono max-w-[200px] truncate" title={dep.name}>{dep.name}</td>
                    <td className="px-3 py-3 text-xs text-zinc-400 font-mono max-w-[260px] truncate" title={dep.image}>{dep.image}</td>
                    <td className="px-3 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${dep.ready.split("/")[0] === dep.ready.split("/")[1] ? "badge-success" : "badge-warning"}`}>{dep.ready}</span>
                    </td>
                    <td className="px-3 py-3 text-sm text-zinc-400">{dep.upToDate}</td>
                    <td className="px-3 py-3 text-sm text-zinc-400">{dep.available}</td>
                    <td className="px-3 py-3 text-sm text-zinc-400">{dep.restarts}</td>
                    <td className="px-3 py-3 text-sm text-zinc-500">{dep.age}</td>
                    <td className="px-3 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${dep.health === "Healthy" ? "badge-success" : dep.health === "Degraded" ? "badge-warning" : "badge-error"}`}>{dep.health}</span>
                    </td>
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
