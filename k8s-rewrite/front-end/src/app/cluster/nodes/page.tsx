"use client";

import Link from "next/link";
import { Server, Loader2, Plus, Trash2, Save, Pencil, Search } from "lucide-react";
import ViewportWrapper from "@/app/(dashboard)/viewport-wrapper";
import { useState, useEffect, useCallback, useMemo } from "react";
import { requestJson, useSession } from "@/lib/use-query";
import { useMutation } from "@/lib/use-mutation";
import { SortHeader, useSort } from "@/components/ui/sortable-header";
import { Modal } from "@/components/ui/modal";
import { findLegacyLiveNode, sortLegacyClusterRows } from "@/lib/legacy-cluster-sort";

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
  const session = useSession();
  const mutation = useMutation(session.canWrite);
  const [dbNodes, setDbNodes] = useState<NodeData[]>([]);
  const [liveNodes, setLiveNodes] = useState<NodeData[]>([]);
  const [loading, setLoading] = useState(true);
  const [inventoryError, setInventoryError] = useState("");
  const [notice, setNotice] = useState("");
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState({ name: "", hostname: "", ipAddress: "", role: "worker" });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editHost, setEditHost] = useState("");
  const [editIp, setEditIp] = useState("");
  const [editRole, setEditRole] = useState("");

  useEffect(() => {
    if (session.canWrite) return;
    setNotice("");
    setAdding(false);
    setForm({ name: "", hostname: "", ipAddress: "", role: "worker" });
    setEditingId(null);
    setEditName(""); setEditHost(""); setEditIp(""); setEditRole("");
  }, [session.canWrite]);

  const fetchDbNodes = useCallback(async () => {
    try {
      const nodes = await requestJson<NodeData[]>("/api/nodes");
      if (!Array.isArray(nodes)) throw new Error("Invalid inventory response");
      setDbNodes(nodes); setInventoryError("");
    } catch { setInventoryError("Node inventory unavailable. Refresh inventory before managing records."); }
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

  async function addNode() {
    if (!session.canWrite || inventoryError || mutation.busy || !form.hostname || !form.ipAddress) return;
    setNotice("");
    await mutation.mutate("/api/nodes", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
    }, () => {
      setForm({ name: "", hostname: "", ipAddress: "", role: "worker" }); setAdding(false);
      setNotice("Inventory record saved. Live cluster nodes were not changed.");
      void fetchDbNodes(); void fetchLive();
    });
  }

  function startEdit(n: NodeData) {
    if (!session.canWrite || inventoryError || mutation.busy) return;
    mutation.clear(); setNotice("");
    setEditingId(n.id);
    setEditName(n.name || n.hostname); setEditHost(n.hostname); setEditIp(n.ipAddress); setEditRole(n.role);
  }

  async function saveEdit(inventoryId: string) {
    if (!session.canWrite || inventoryError || mutation.busy) return;
    setNotice("");
    await mutation.mutate(`/api/nodes/${encodeURIComponent(inventoryId)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: editName, hostname: editHost, ipAddress: editIp, role: editRole }),
    }, () => {
      setEditingId(null); setNotice("Inventory record updated. Live cluster nodes were not changed.");
      void fetchDbNodes(); void fetchLive();
    });
  }

  async function deleteNode(inventoryId: string) {
    if (!session.canWrite || inventoryError || mutation.busy) return;
    setNotice("");
    await mutation.mutate(`/api/nodes/${encodeURIComponent(inventoryId)}`, { method: "DELETE" }, () => {
      setNotice("Inventory record removed. The live cluster node was not deleted.");
      void fetchDbNodes(); void fetchLive();
    });
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
    return sortLegacyClusterRows(result, "nodes", sortKey, sortDir);
  }, [unfilteredNodes, search, sortKey, sortDir]);

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        <div className="flex items-center gap-3 mb-4">
          <Server className="page-header-icon text-blue-400" />
          <h1 className="page-header-title">Nodes</h1>
          <span className="text-sm text-zinc-400 ml-auto">
            {loading ? "…" : `${totalNodes} nodes`}
          </span>
        </div>

        <p className="mb-3 text-sm text-zinc-400">Inventory changes do not join, rename or delete live Kubernetes nodes. <Link href="/nodes" className="underline">Manage all inventory records</Link>.</p>
        {notice && <p role="status" className="mb-3 text-emerald-300">{notice}</p>}
        {!editingId && inventoryError && <p role="status" className="mb-3 text-amber-300">{inventoryError}<button onClick={fetchDbNodes} className="ml-2 underline">Refresh inventory</button></p>}
        {!editingId && session.canWrite && mutation.error && <p role="alert" className="mb-3 text-red-300">{mutation.error} Refresh inventory to check the result before retrying.<button onClick={fetchDbNodes} className="ml-2 underline">Refresh inventory</button></p>}
        {/* Filter Bar */}
        <div className="flex items-center gap-3 mb-6">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              aria-label="Search inventory nodes"
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
          {session.canWrite && (!adding ? (
            <button
              onClick={() => { if (!session.canWrite || inventoryError || mutation.busy) return; mutation.clear(); setNotice(""); setAdding(true); }}
              disabled={mutation.busy || !!inventoryError}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors ml-auto"
            >
              <Plus className="w-4 h-4" />
              Add inventory node
            </button>
          ) : (
          <div className="glass-card p-4 rounded-xl mb-6 flex items-end gap-3 flex-wrap">
            <div>
              <label htmlFor="inventory-add-name" className="text-xs text-zinc-500 mb-1 block">Name</label>
              <input
                id="inventory-add-name"
                value={form.name}
                disabled={mutation.busy}
                onChange={e => setForm({ ...form, name: e.target.value })}
                placeholder="Living Room"
                className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 w-32"
              />
            </div>
            <div>
              <label htmlFor="inventory-add-hostname" className="text-xs text-zinc-500 mb-1 block">Hostname</label>
              <input
                id="inventory-add-hostname"
                value={form.hostname}
                disabled={mutation.busy}
                onChange={e => setForm({ ...form, hostname: e.target.value })}
                placeholder="u4"
                className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 w-28"
              />
            </div>
            <div>
              <label htmlFor="inventory-add-ip" className="text-xs text-zinc-500 mb-1 block">IP Address</label>
              <input
                id="inventory-add-ip"
                value={form.ipAddress}
                disabled={mutation.busy}
                onChange={e => setForm({ ...form, ipAddress: e.target.value })}
                placeholder="192.168.0.28"
                className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 w-40"
              />
            </div>
            <div>
              <label htmlFor="inventory-add-role" className="text-xs text-zinc-500 mb-1 block">Role</label>
              <select
                id="inventory-add-role"
                value={form.role}
                disabled={mutation.busy}
                onChange={e => setForm({ ...form, role: e.target.value })}
                className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200"
              >
                <option value="worker">Worker</option>
                <option value="master">Master</option>
                <option value="control-plane">Control plane</option>
              </select>
            </div>
            <button
              onClick={addNode}
              aria-label="Save inventory node"
              disabled={mutation.busy || !!inventoryError || !form.hostname || !form.ipAddress}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
            </button>
            <button
              onClick={() => { mutation.clear(); setAdding(false); }}
              disabled={mutation.busy}
              className="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
            >
              Cancel
            </button>
          </div>
        ))}
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
                  <th className="text-right px-2 py-2.5 text-xs font-medium text-zinc-400">Actions</th>
                </tr>
              </thead>
              <tbody>
                {displayNodes.map((node) => {
                  const liveInfo = findLegacyLiveNode(liveNodes, node);
                  const inventory = dbNodes.find(record => record.hostname === node.hostname);
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
                      <td className="px-2 py-2.5 text-sm text-zinc-400 whitespace-nowrap">
                        {liveInfo?.age || node.age || "—"}
                      </td>
                      <td className="px-2 py-2.5 text-right">
                        {session.canWrite && inventory && <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => startEdit(inventory)}
                            disabled={mutation.busy || !!inventoryError}
                            className="p-1.5 rounded-lg hover:bg-zinc-700/50 text-zinc-500 hover:text-zinc-300 transition-colors"
                            title={`Edit inventory ${inventory.hostname}`}
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => deleteNode(inventory.id)}
                            disabled={mutation.busy || !!inventoryError}
                            className="p-1.5 rounded-lg hover:bg-red-500/10 text-zinc-500 hover:text-red-400 transition-colors"
                            title={`Delete inventory ${inventory.hostname}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Edit Modal */}
        {session.canWrite && editingId && (
          <Modal open title="Edit Node" onClose={() => { if (mutation.busy) return; mutation.clear(); setEditingId(null); }}>
              <div className="flex flex-col gap-3">
                {inventoryError && <p role="status" className="text-sm text-amber-300">{inventoryError}<button onClick={fetchDbNodes} className="ml-2 underline">Refresh inventory</button></p>}
                {mutation.error && <p role="alert" className="text-sm text-red-300">{mutation.error} Refresh inventory to check the result before retrying.<button onClick={fetchDbNodes} className="ml-2 underline">Refresh inventory</button></p>}
                <div>
                  <label htmlFor="inventory-edit-name" className="text-xs text-zinc-400 mb-1 block">Name</label>
                  <input
                    id="inventory-edit-name"
                    value={editName}
                    disabled={mutation.busy}
                    onChange={e => setEditName(e.target.value)}
                    placeholder="Name"
                    className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500 outline-none focus:ring-0 transition-colors"
                  />
                </div>
                <div>
                  <label htmlFor="inventory-edit-hostname" className="text-xs text-zinc-400 mb-1 block">Hostname</label>
                  <input
                    id="inventory-edit-hostname"
                    value={editHost}
                    disabled={mutation.busy}
                    onChange={e => setEditHost(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500 outline-none focus:ring-0 transition-colors"
                  />
                </div>
                <div>
                  <label htmlFor="inventory-edit-ip" className="text-xs text-zinc-400 mb-1 block">IP Address</label>
                  <input
                    id="inventory-edit-ip"
                    value={editIp}
                    disabled={mutation.busy}
                    onChange={e => setEditIp(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500 outline-none focus:ring-0 transition-colors"
                  />
                </div>
                <div>
                  <label htmlFor="inventory-edit-role" className="text-xs text-zinc-400 mb-1 block">Role</label>
                  <select
                    id="inventory-edit-role"
                    value={editRole}
                    disabled={mutation.busy}
                    onChange={e => setEditRole(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500 outline-none focus:ring-0 transition-colors"
                  >
                    <option value="worker">Worker</option>
                    <option value="master">Master</option>
                    <option value="control-plane">Control plane</option>
                  </select>
                </div>
              </div>
              <div className="mt-4 border-t border-zinc-700/40 pt-3 flex items-center justify-end gap-2">
                <button
                  onClick={() => { mutation.clear(); setEditingId(null); }}
                  disabled={mutation.busy}
                  className="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => saveEdit(editingId)}
                  disabled={mutation.busy || !!inventoryError || !editHost || !editIp}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors"
                >
                  Save
                </button>
              </div>
          </Modal>
        )}
      </main>
      </ViewportWrapper>
    </div>
  );
}
