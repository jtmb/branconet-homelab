"use client";

import Link from "next/link";
import { Server, Loader2, Plus, Trash2, Save, Pencil, Search } from "lucide-react";
import ViewportWrapper from "../viewport-wrapper";
import { useState, useEffect, useCallback, useMemo } from "react";
import { SortHeader, useSort } from "@/components/ui/sortable-header";

interface NodeData {
  id: string;
  name?: string;
  hostname: string;
  ipAddress: string;
  externalIp?: string | null;
  role: string;
  status: string;
  cpu?: number | null;
  memory?: number | null;
  k8sVersion?: string | null;
  osImage?: string | null;
  pods?: number | null;
  age?: string | null;
}

export default function NodesPage() {
  const [dbNodes, setDbNodes] = useState<NodeData[]>([]);
  const [liveNodes, setLiveNodes] = useState<NodeData[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<"readonly" | "write" | null>(null);
  const [form, setForm] = useState({ name: "", hostname: "", ipAddress: "", role: "worker" });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editHost, setEditHost] = useState("");
  const [editIp, setEditIp] = useState("");
  const [editRole, setEditRole] = useState("");

  const fetchDbNodes = useCallback(async () => {
    try {
      const res = await fetch("/api/nodes");
      setDbNodes(await res.json());
    } catch { /* ignore */ }
  }, []);

  const fetchLive = useCallback(async () => {
    try {
      const res = await fetch("/api/cluster/nodes");
      const data = await res.json();
      setLiveNodes(data.nodes || []);
    } catch {
      setLiveNodes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDbNodes();
    fetchLive();
    const interval = setInterval(fetchLive, 10000);
    return () => clearInterval(interval);
  }, [fetchDbNodes, fetchLive]);

  useEffect(() => {
    fetch("/api/auth/session")
      .then((r) => r.json())
      .then((d) => { if (d.role) setRole(d.role); })
      .catch(() => {});
  }, []);

  async function addNode() {
    if (!form.hostname || !form.ipAddress) return;
    const res = await fetch("/api/nodes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    if (res.ok) {
      setForm({ name: "", hostname: "", ipAddress: "", role: "worker" });
      setAdding(false);
      fetchDbNodes();
    }
  }

  function startEdit(n: NodeData) {
    setEditingId(n.id);
    setEditName(n.name || n.hostname);
    setEditHost(n.hostname);
    setEditIp(n.ipAddress);
    setEditRole(n.role);
  }

  async function saveEdit(id: string) {
    await fetch("/api/nodes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: editName, hostname: editHost, ipAddress: editIp, role: editRole }),
    });
    setEditingId(null);
    fetchDbNodes();
    fetchLive();  // force-live refresh so display updates immediately
  }

  async function deleteNode(id: string) {
    await fetch(`/api/nodes/${id}`, { method: "DELETE" });
    fetchDbNodes();
    fetchLive();
  }

  const totalNodes = liveNodes.length || dbNodes.length;
  const unfilteredNodes = liveNodes.length > 0 ? liveNodes : dbNodes;

  const { sortKey, sortDir, toggle: toggleSort } = useSort("hostname");

  const displayNodes = useMemo(() => {
    let result = search.trim()
      ? unfilteredNodes.filter((n) => {
          const q = search.toLowerCase();
          return (
            (n.name || "").toLowerCase().includes(q) ||
            n.hostname.toLowerCase().includes(q) ||
            n.ipAddress.toLowerCase().includes(q) ||
            n.role.toLowerCase().includes(q) ||
            (n.osImage || "").toLowerCase().includes(q) ||
            (n.k8sVersion || "").toLowerCase().includes(q)
          );
        })
      : unfilteredNodes;
    return [...result].sort((a, b) => {
      const va = String((a as any)[sortKey] ?? "").toLowerCase();
      const vb = String((b as any)[sortKey] ?? "").toLowerCase();
      return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }, [unfilteredNodes, search, sortKey, sortDir]);

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        <div className="flex items-center gap-3 mb-4">
          <Server className="page-header-icon text-blue-400" />
          <h1 className="page-header-title">Nodes</h1>
          <span className="text-sm text-zinc-500 ml-auto">
            {loading ? "…" : `${totalNodes} nodes`}
          </span>
        </div>

        {/* Filter Bar */}
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
          {/* Add Node Form */}
          {role === "write" && (
            !adding ? (
              <button
                onClick={() => setAdding(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors ml-auto"
              >
                <Plus className="w-4 h-4" />
                Add Node
              </button>
            ) : (
              <div className="glass-card p-4 rounded-xl mb-6 flex items-end gap-3 flex-wrap">
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">Name</label>
                  <input
                    value={form.name}
                    onChange={e => setForm({ ...form, name: e.target.value })}
                    placeholder="Living Room"
                    className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 w-32"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">Hostname</label>
                  <input
                    value={form.hostname}
                    onChange={e => setForm({ ...form, hostname: e.target.value })}
                    placeholder="u4"
                    className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 w-28"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">IP Address</label>
                  <input
                    value={form.ipAddress}
                    onChange={e => setForm({ ...form, ipAddress: e.target.value })}
                    placeholder="192.168.0.28"
                    className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 w-40"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">Role</label>
                  <select
                    value={form.role}
                    onChange={e => setForm({ ...form, role: e.target.value })}
                    className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200"
                  >
                    <option value="worker">Worker</option>
                    <option value="master">Master</option>
                  </select>
                </div>
                <button
                  onClick={addNode}
                  disabled={!form.hostname || !form.ipAddress}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setAdding(false)}
                  className="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
                >
                  Cancel
                </button>
              </div>
            )
          )}
        </div>

        {/* Node List */}
        {loading ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-16rem)]">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : displayNodes.length === 0 ? (
          <div className="glass-card p-8 rounded-xl text-center">
            <Server className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Nodes Configured</h3>
            <p className="text-sm text-zinc-500">
              Add nodes above, then sync and deploy.
            </p>
          </div>
        ) : (
          <div className="glass-card rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-2 py-2.5"><SortHeader label="State" active={sortKey==="status"} dir={sortDir} onClick={()=>toggleSort("status")} /></th>
                  <th className="text-left px-2 py-2.5"><SortHeader label="Name" active={sortKey==="hostname"} dir={sortDir} onClick={()=>toggleSort("hostname")} /></th>
                  <th className="text-left px-2 py-2.5"><SortHeader label="Roles" active={sortKey==="role"} dir={sortDir} onClick={()=>toggleSort("role")} /></th>
                  <th className="text-left px-2 py-2.5"><SortHeader label="Version" active={sortKey==="k8sVersion"} dir={sortDir} onClick={()=>toggleSort("k8sVersion")} /></th>
                  <th className="text-left px-2 py-2.5"><SortHeader label="Internal IP" active={sortKey==="ipAddress"} dir={sortDir} onClick={()=>toggleSort("ipAddress")} /></th>
                  <th className="text-left px-2 py-2.5"><SortHeader label="External IP" active={sortKey==="externalIp"} dir={sortDir} onClick={()=>toggleSort("externalIp")} /></th>
                  <th className="text-left px-2 py-2.5"><SortHeader label="OS" active={sortKey==="osImage"} dir={sortDir} onClick={()=>toggleSort("osImage")} /></th>
                  <th className="text-left px-2 py-2.5"><SortHeader label="CPU" active={sortKey==="cpu"} dir={sortDir} onClick={()=>toggleSort("cpu")} /></th>
                  <th className="text-left px-2 py-2.5"><SortHeader label="RAM" active={sortKey==="mem"} dir={sortDir} onClick={()=>toggleSort("mem")} /></th>
                  <th className="text-left px-2 py-2.5"><SortHeader label="Pods" active={sortKey==="pods"} dir={sortDir} onClick={()=>toggleSort("pods")} /></th>
                  <th className="text-left px-2 py-2.5"><SortHeader label="Age" active={sortKey==="age"} dir={sortDir} onClick={()=>toggleSort("age")} /></th>
                  {role === "write" && <th className="text-right px-2 py-2.5 text-xs font-medium text-zinc-400">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {displayNodes.map((node) => {
                  const liveInfo = liveNodes.find(
                    (ln) => ln.hostname === node.hostname || ln.ipAddress === node.ipAddress
                  );
                  const isReady = (liveInfo?.status || node.status) === "ready";
                  const isLive = !!liveInfo;
                  const roles = (liveInfo?.role || node.role || "worker").split(",");
                  return (
                    <tr key={node.id} className="border-b border-zinc-800/40 hover:bg-zinc-800/30">
                      <td className="px-2 py-2.5">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          isReady ? "badge-success" : isLive ? "badge-warning" : "badge-error"
                        }`}>
                          {isReady ? "Active" : isLive ? "Not Ready" : "Offline"}
                        </span>
                      </td>
                      <td className="px-2 py-2.5 text-sm font-medium whitespace-nowrap">
                        <Link
                          href={`/nodes/${encodeURIComponent(liveInfo?.hostname || node.hostname)}`}
                          className="text-zinc-200 hover:text-indigo-400 transition-colors"
                        >
                          {node.name || node.hostname}
                        </Link>
                      </td>
                      <td className="px-2 py-2.5">
                        <div className="flex flex-wrap gap-1">
                          {roles.map((r) => (
                            <span key={r} className={`text-[10px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded whitespace-nowrap ${
                              r === "control-plane" || r === "master" ? "bg-amber-500/10 text-amber-400" : "bg-blue-500/10 text-blue-400"
                            }`}>{r}</span>
                          ))}
                        </div>
                      </td>
                      <td className="px-2 py-2.5 text-sm text-zinc-400 font-mono whitespace-nowrap">
                        {liveInfo?.k8sVersion ? `v${liveInfo.k8sVersion}` : node.k8sVersion ? `v${node.k8sVersion}` : "—"}
                      </td>
                      <td className="px-2 py-2.5 text-sm text-zinc-300 font-mono whitespace-nowrap">
                        {liveInfo?.ipAddress || node.ipAddress || "—"}
                      </td>
                      <td className="px-2 py-2.5 text-sm text-zinc-500 font-mono whitespace-nowrap">
                        {liveInfo?.externalIp || node.externalIp || "—"}
                      </td>
                      <td className="px-2 py-2.5 text-sm text-zinc-400 max-w-[140px] truncate" title={liveInfo?.osImage || node.osImage || undefined}>
                        {liveInfo?.osImage || node.osImage || "—"}
                      </td>
                      <td className="px-2 py-2.5 text-sm text-zinc-400 font-mono tabular-nums whitespace-nowrap">
                        {liveInfo?.cpu != null ? liveInfo.cpu : node.cpu != null ? node.cpu : "—"}
                      </td>
                      <td className="px-2 py-2.5 text-sm text-zinc-400 font-mono tabular-nums whitespace-nowrap">
                        {liveInfo?.memory != null ? `${liveInfo.memory}G` : node.memory != null ? `${node.memory}G` : "—"}
                      </td>
                      <td className="px-2 py-2.5 text-sm text-zinc-400 font-mono tabular-nums whitespace-nowrap">
                        {liveInfo?.pods != null ? liveInfo.pods : node.pods != null ? node.pods : "—"}
                      </td>
                      <td className="px-2 py-2.5 text-sm text-zinc-500 whitespace-nowrap">
                        {liveInfo?.age || node.age || "—"}
                      </td>
                      {role === "write" && (
                      <td className="px-2 py-2.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => startEdit(node)}
                            className="p-1.5 rounded-lg hover:bg-zinc-700/50 text-zinc-500 hover:text-zinc-300 transition-colors"
                            title="Edit"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => deleteNode(node.id)}
                            className="p-1.5 rounded-lg hover:bg-red-500/10 text-zinc-500 hover:text-red-400 transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Edit Modal */}
        {editingId && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="bg-zinc-900 border border-zinc-700/60 rounded-2xl w-full max-w-sm mx-4 shadow-2xl overflow-hidden">
              <div className="px-5 py-4 border-b border-zinc-700/40">
                <h3 className="text-sm font-semibold text-zinc-200">Edit Node</h3>
              </div>
              <div className="p-5 flex flex-col gap-3">
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">Name</label>
                  <input
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    placeholder="Name"
                    className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500 outline-none focus:ring-0 transition-colors"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">Hostname</label>
                  <input
                    value={editHost}
                    onChange={e => setEditHost(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500 outline-none focus:ring-0 transition-colors"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">IP Address</label>
                  <input
                    value={editIp}
                    onChange={e => setEditIp(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500 outline-none focus:ring-0 transition-colors"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 mb-1 block">Role</label>
                  <select
                    value={editRole}
                    onChange={e => setEditRole(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500 outline-none focus:ring-0 transition-colors"
                  >
                    <option value="worker">Worker</option>
                    <option value="master">Master</option>
                  </select>
                </div>
              </div>
              <div className="px-5 py-3 border-t border-zinc-700/40 flex items-center justify-end gap-2">
                <button
                  onClick={() => setEditingId(null)}
                  className="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => saveEdit(editingId)}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors"
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
      </ViewportWrapper>
    </div>
  );
}