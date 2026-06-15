"use client";

import Link from "next/link";
import { Server, Loader2, Plus, Trash2, Save, RefreshCw } from "lucide-react";
import { useState, useEffect, useCallback } from "react";

interface NodeData {
  id: string;
  name?: string;
  hostname: string;
  ipAddress: string;
  role: string;
  status: string;
  cpu?: number;
  memory?: number;
}

export default function NodesPage() {
  const [dbNodes, setDbNodes] = useState<NodeData[]>([]);
  const [liveNodes, setLiveNodes] = useState<NodeData[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [adding, setAdding] = useState(false);
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
  }

  async function deleteNode(id: string) {
    await fetch(`/api/nodes/${id}`, { method: "DELETE" });
    fetchDbNodes();
  }

  async function syncInventory() {
    setSyncing(true);
    await fetch("/api/vars/sync", { method: "POST" });
    setSyncing(false);
  }

  const totalNodes = dbNodes.length || liveNodes.length;
  const displayNodes = dbNodes.length > 0 || liveNodes.length === 0 ? dbNodes : liveNodes;

  return (
    <div className="min-h-screen bg-zinc-950">
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center gap-3">
          <Link href="/cluster" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors mr-2">
            Cluster
          </Link>
          <span className="text-zinc-700">|</span>
          <Server className="w-6 h-6 text-blue-400" />
          <h1 className="text-xl font-bold text-zinc-100">Nodes</h1>
          <span className="text-sm text-zinc-500 ml-auto">
            {loading ? "…" : `${totalNodes} nodes`}
          </span>
          <button
            onClick={syncInventory}
            disabled={syncing || dbNodes.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/20 border border-indigo-500/20 text-indigo-400 hover:bg-indigo-600/30 text-xs font-medium transition-colors disabled:opacity-50 ml-2"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? "animate-spin" : ""}`} />
            Sync
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Add Node Form */}
        {!adding ? (
          <button
            onClick={() => setAdding(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors mb-6"
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
        )}

        {/* Node List */}
        {loading && dbNodes.length === 0 ? (
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
          <div className="grid gap-3">
            {displayNodes.map((node) => {
              const liveInfo = liveNodes.find(
                (ln) => ln.hostname === node.hostname || ln.ipAddress === node.ipAddress
              );
              return (
                <div key={node.id} className="glass-card p-4 rounded-xl">
                  {editingId === node.id ? (
                    <div className="flex items-center gap-3 flex-wrap">
                      <input
                        value={editName}
                        onChange={e => setEditName(e.target.value)}
                        className="bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-sm text-zinc-200 w-32"
                        placeholder="Name"
                      />
                      <input
                        value={editHost}
                        onChange={e => setEditHost(e.target.value)}
                        className="bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-sm text-zinc-200 w-28"
                      />
                      <input
                        value={editIp}
                        onChange={e => setEditIp(e.target.value)}
                        className="bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-sm text-zinc-200 w-36"
                      />
                      <select
                        value={editRole}
                        onChange={e => setEditRole(e.target.value)}
                        className="bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-sm text-zinc-200"
                      >
                        <option value="worker">Worker</option>
                        <option value="master">Master</option>
                      </select>
                      <button
                        onClick={() => saveEdit(node.id)}
                        className="px-3 py-1 rounded bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-500"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="px-3 py-1 rounded border border-zinc-700 text-zinc-400 text-xs hover:text-zinc-200"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className={`w-2.5 h-2.5 rounded-full ${
                          liveInfo?.status === "ready" ? "bg-emerald-400" :
                          liveInfo ? "bg-amber-400" : "bg-zinc-600"
                        }`} />
                        <div>
                          <h3 className="text-lg font-semibold text-zinc-100">{node.name || node.hostname}</h3>
                          <p className="text-sm text-zinc-500">
                            {node.name && node.name !== node.hostname
                              ? `${node.hostname} · ${node.ipAddress}`
                              : node.ipAddress}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {liveInfo && (
                          <span className="text-xs text-zinc-500">
                            {liveInfo.cpu ? `${liveInfo.cpu} CPU / ${liveInfo.memory}GB` : liveInfo.status}
                          </span>
                        )}
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          node.role === "master" ? "bg-amber-500/20 text-amber-400" : "bg-blue-500/20 text-blue-400"
                        }`}>{node.role}</span>
                        <button
                          onClick={() => startEdit(node)}
                          className="text-xs text-zinc-500 hover:text-zinc-300"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => deleteNode(node.id)}
                          className="text-xs text-red-500 hover:text-red-400"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}