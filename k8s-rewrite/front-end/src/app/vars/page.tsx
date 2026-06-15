"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, Pencil, Trash2, Save, Database, Loader2, RefreshCw, CheckCircle2 } from "lucide-react";

interface VarItem {
  id: string;
  key: string;
  value: string;
  category: string;
  encrypted: boolean;
}

const CATEGORIES = [
  "kubernetes",
  "networking",
  "storage",
  "runtime",
  "longhorn",
  "traefik",
  "general",
];

export default function VarsPage() {
  const [vars, setVars] = useState<VarItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncOk, setSyncOk] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    fetchVars();
  }, []);

  async function fetchVars() {
    try {
      const res = await fetch("/api/vars");
      const data = await res.json();
      setVars(data);
    } catch (err) {
      console.error("Failed to fetch vars:", err);
    } finally {
      setLoading(false);
    }
  }

  async function saveVar(v: VarItem) {
    try {
      const res = await fetch("/api/vars", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...v, value: editValue }),
      });
      if (res.ok) {
        setEditingId(null);
        fetchVars();
      }
    } catch (err) {
      console.error("Failed to save var:", err);
    }
  }

  async function deleteVar(id: string) {
    try {
      const res = await fetch(`/api/vars/${id}`, { method: "DELETE" });
      if (res.ok) fetchVars();
    } catch (err) {
      console.error("Failed to delete var:", err);
    }
  }

  async function syncToAnsible() {
    setSyncing(true);
    setSyncOk(false);
    try {
      const res = await fetch("/api/vars/sync", { method: "POST" });
      if (res.ok) {
        setSyncOk(true);
        setTimeout(() => setSyncOk(false), 3000);
      }
    } catch (err) {
      console.error("Sync failed:", err);
    } finally {
      setSyncing(false);
    }
  }

  const filtered = filter === "all" ? vars : vars.filter((v) => v.category === filter);

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center gap-3">
          <Link href="/" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors mr-2">
            Home
          </Link>
          <span className="text-zinc-700">|</span>
          <Database className="w-6 h-6 text-indigo-400" />
          <h1 className="text-xl font-bold text-zinc-100">Variables</h1>
          <span className="text-sm text-zinc-500 ml-auto">{vars.length} variables</span>
          <button
            onClick={syncToAnsible}
            disabled={syncing}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              syncOk
                ? "bg-emerald-600 text-white"
                : "bg-indigo-600 hover:bg-indigo-500 text-white"
            }`}
          >
            {syncing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : syncOk ? (
              <CheckCircle2 className="w-4 h-4" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            {syncing ? "Syncing..." : syncOk ? "Synced!" : "Sync to Ansible"}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Filters */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {["all", ...CATEGORIES].map((cat) => (
            <button
              key={cat}
              onClick={() => setFilter(cat)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filter === cat
                  ? "bg-indigo-600 text-white"
                  : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
              }`}
            >
              {cat === "all" ? "All" : cat.charAt(0).toUpperCase() + cat.slice(1)}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="glass-card rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-700/40">
                <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Key</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Value</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Category</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-zinc-400">Encrypted</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-zinc-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-zinc-500">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
                    Loading...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-zinc-500">
                    No variables found. Add one to get started.
                  </td>
                </tr>
              ) : (
                filtered.map((v) => (
                  <tr key={v.id} className="border-b border-zinc-800/40 hover:bg-zinc-800/30">
                    <td className="px-4 py-3 text-sm text-zinc-200 font-mono">{v.key}</td>
                    <td className="px-4 py-3 text-sm text-zinc-300">
                      {editingId === v.id ? (
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="w-full bg-zinc-800 border border-zinc-600 rounded px-2 py-1 text-zinc-200 text-sm"
                          autoFocus
                        />
                      ) : (
                        <span className="truncate max-w-xs block">{v.value}</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded-full">
                        {v.category}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        v.encrypted ? "bg-amber-500/20 text-amber-400" : "bg-zinc-800 text-zinc-500"
                      }`}>
                        {v.encrypted ? "Yes" : "No"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {editingId === v.id ? (
                        <button
                          onClick={() => saveVar(v)}
                          className="text-emerald-400 hover:text-emerald-300 p-1"
                        >
                          <Save className="w-4 h-4" />
                        </button>
                      ) : (
                        <button
                          onClick={() => { setEditingId(v.id); setEditValue(v.value); }}
                          className="text-zinc-400 hover:text-zinc-200 p-1"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => deleteVar(v.id)}
                        className="text-red-400 hover:text-red-300 p-1 ml-1"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Add button */}
        <button className="mt-6 flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors">
          <Plus className="w-4 h-4" />
          Add Variable
        </button>
      </main>
    </div>
  );
}