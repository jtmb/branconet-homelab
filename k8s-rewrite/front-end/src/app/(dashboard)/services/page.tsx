"use client";

import { Network, Loader2, Search } from "lucide-react";
import ViewportWrapper from "../viewport-wrapper";
import { useState, useEffect, useCallback, useMemo } from "react";
import { SortHeader, useSort } from "@/components/ui/sortable-header";

interface ServiceData {
  name: string;
  namespace: string;
  type: string;
  clusterIP: string;
  externalIP: string;
  ports: string;
  selector: string;
}

export default function ServicesPage() {
  const [services, setServices] = useState<ServiceData[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchServices = useCallback(async () => {
    try {
      const res = await fetch("/api/cluster/services");
      const data = await res.json();
      setServices(data.services || []);
    } catch {
      setServices([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const [search, setSearch] = useState("");

  const { sortKey, sortDir, toggle: toggleSort } = useSort("name");

  const filteredServices = useMemo(() => {
    let result = services;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = services.filter(
        (s) => s.name.toLowerCase().includes(q) || s.namespace.toLowerCase().includes(q)
      );
    }
    return [...result].sort((a, b) => {
      const va = String((a as any)[sortKey] ?? "").toLowerCase();
      const vb = String((b as any)[sortKey] ?? "").toLowerCase();
      return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }, [services, search, sortKey, sortDir]);

  useEffect(() => {
    setLoading(true);
    fetchServices();
  }, [fetchServices]);

  useEffect(() => {
    const interval = setInterval(() => fetchServices(), 10000);
    return () => clearInterval(interval);
  }, [fetchServices]);

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        <div className="flex items-center gap-3 mb-6">
          <Network className="page-header-icon text-rose-400" />
          <h1 className="page-header-title">Services</h1>
          <span className="text-sm text-zinc-500 ml-auto">{services.length} services</span>
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

        {loading && services.length === 0 ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-12rem)]">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : services.length === 0 ? (
          <div className="glass-card p-8 rounded-xl text-center">
            <Network className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Services Found</h3>
            <p className="text-sm text-zinc-500">
              Deploy workloads first using the <a href="/deploy" className="text-indigo-400 hover:underline">Deploy</a> tab.
            </p>
          </div>
        ) : (
          <div className="glass-card rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-4 py-3"><SortHeader label="Name" active={sortKey==="name"} dir={sortDir} onClick={()=>toggleSort("name")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Namespace" active={sortKey==="namespace"} dir={sortDir} onClick={()=>toggleSort("namespace")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Type" active={sortKey==="type"} dir={sortDir} onClick={()=>toggleSort("type")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Cluster IP" active={sortKey==="clusterIP"} dir={sortDir} onClick={()=>toggleSort("clusterIP")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="External IP" active={sortKey==="externalIP"} dir={sortDir} onClick={()=>toggleSort("externalIP")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Ports" active={sortKey==="ports"} dir={sortDir} onClick={()=>toggleSort("ports")} /></th>
                  <th className="text-left px-4 py-3"><SortHeader label="Selector" active={sortKey==="selector"} dir={sortDir} onClick={()=>toggleSort("selector")} /></th>
                </tr>
              </thead>
              <tbody>
                {filteredServices.map((svc) => (
                  <tr key={`${svc.namespace}-${svc.name}`} className="border-b border-zinc-800/40 hover:bg-zinc-800/30">
                    <td className="px-4 py-3 text-sm text-zinc-200 font-mono">{svc.name}</td>
                    <td className="px-4 py-3 text-sm text-zinc-400">{svc.namespace}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        svc.type === "LoadBalancer"
                          ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                          : svc.type === "NodePort"
                          ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                          : "bg-zinc-500/10 text-zinc-400 border border-zinc-500/20"
                      }`}>{svc.type}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-zinc-300 font-mono">{svc.clusterIP}</td>
                    <td className="px-4 py-3 text-sm text-zinc-400">{svc.externalIP}</td>
                    <td className="px-4 py-3 text-sm text-zinc-400 font-mono">{svc.ports}</td>
                    <td className="px-4 py-3 text-sm text-zinc-500 font-mono text-xs">{svc.selector}</td>
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
