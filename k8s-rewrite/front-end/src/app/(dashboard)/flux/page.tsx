"use client";

import { GitBranch, Loader2, Plus, RefreshCw, Trash2, XCircle, Globe, Key, Lock, X, ChevronDown, CheckCircle2, AlertTriangle, Search } from "lucide-react";
import ViewportWrapper from "../viewport-wrapper";
import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import FluxTreeRow from "./tree-row";
import type { FluxTreeNode } from "@/lib/flux";

interface DeleteStep {
  step: string;
  status: "pending" | "running" | "done" | "error";
  detail: string;
}

interface DeleteProgress {
  deleteId: string;
  repoName: string;
  namespace: string;
  steps: DeleteStep[];
  done: boolean;
  error?: string;
}

/** Recursively filter tree nodes: keep a node if its name matches OR any descendant matches */
function filterTree(nodes: FluxTreeNode[], q: string): FluxTreeNode[] {
  const lower = q.toLowerCase();
  return nodes
    .map((n) => {
      const nameMatch = n.name.toLowerCase().includes(lower);
      const filteredChildren = filterTree(n.children, q);
      if (nameMatch || filteredChildren.length > 0) {
        return { ...n, children: filteredChildren.length ? filteredChildren : n.children };
      }
      return null;
    })
    .filter(Boolean) as FluxTreeNode[];
}

/** Count all root GitRepositories (depth-0 nodes of kind GitRepository) */
function countRoots(trees: FluxTreeNode[]): number {
  return trees.filter((n) => n.kind === "GitRepository").length;
}

export default function FluxPage() {
  const [trees, setTrees] = useState<FluxTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState<{ id: string; name: string; namespace: string } | null>(null);
  const [deleteProgress, setDeleteProgress] = useState<DeleteProgress | null>(null);
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [form, setForm] = useState({
    name: "",
    url: "",
    branch: "main",
    path: "./",
    authMethod: "none" as "none" | "ssh" | "https",
    authData: "",
  });

  const fetchHierarchy = useCallback(async () => {
    try {
      const res = await fetch("/api/flux/hierarchy");
      if (!res.ok) return;
      const data = await res.json();
      setTrees(data.trees || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const [search, setSearch] = useState("");

  const filteredTrees = useMemo(() => {
    if (!search.trim()) return trees;
    return filterTree(trees, search);
  }, [trees, search]);

  useEffect(() => {
    fetchHierarchy();
    const interval = setInterval(fetchHierarchy, 10000);
    return () => clearInterval(interval);
  }, [fetchHierarchy]);

  async function addRepo() {
    if (!form.name || !form.url) return;
    setAddError(null);

    try {
      const res = await fetch("/api/flux/repos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          url: form.url,
          branch: form.branch,
          path: form.path,
          authMethod: form.authMethod,
          authData: form.authData || undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setAddError(data.error || "Failed to add repo");
        return;
      }

      setForm({ name: "", url: "", branch: "main", path: "./", authMethod: "none", authData: "" });
      setAdding(false);
      setAddError(null);
      fetchHierarchy();
    } catch (err) {
      setAddError(String(err));
    }
  }

  // Cleanup poll interval on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function deleteRepo(id: string, name: string, namespace: string) {
    setShowConfirm(null);
    setDeleteError(null);
    setDeleting(id);

    try {
      // 1. Kick off cascade delete
      const params = new URLSearchParams({ name, namespace });
      const res = await fetch(`/api/flux/repos/${encodeURIComponent(id)}?${params}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok || !data.deleteId) {
        setDeleteError(data.error || "Failed to start deletion");
        setDeleting(null);
        return;
      }

      // 2. Start polling progress
      const deleteId = data.deleteId;
      const poll = async () => {
        try {
          const pr = await fetch(`/api/flux/repos/${deleteId}/delete-progress`);
          if (!pr.ok) return;
          const progress: DeleteProgress = await pr.json();
          setDeleteProgress(progress);

          if (progress.done) {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setDeleting(null);
            fetchHierarchy();
            // Auto-dismiss after 2s
            setTimeout(() => setDeleteProgress(null), 2000);
          }
        } catch {
          // Keep polling
        }
      };

      pollRef.current = setInterval(poll, 1500);
      poll(); // Immediate first poll
    } catch {
      setDeleting(null);
    }
  }

  function cancelDelete() {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
    setDeleteProgress(null);
    setDeleteError(null);
    setDeleting(null);
  }

  async function triggerSync(id: string) {
    setSyncing(id);
    try {
      await fetch(`/api/flux/repos/${id}/sync`, { method: "POST" });
      setTimeout(fetchHierarchy, 2000);
    } catch {
      // ignore
    } finally {
      setSyncing(null);
    }
  }

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        <div className="flex items-center gap-3 mb-6">
          <GitBranch className="page-header-icon text-emerald-400" />
          <h1 className="page-header-title">Flux</h1>
          <span className="text-sm text-zinc-500 ml-auto">{countRoots(trees)} repos</span>
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
          <div className="ml-auto">
            {!adding ? (
              <button
                onClick={() => setAdding(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors whitespace-nowrap"
              >
                <Plus className="w-4 h-4" />
                Add Repository
              </button>
            ) : null}
          </div>
        </div>

        {/* Add Repo Modal */}
        {adding && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="bg-zinc-900 border border-zinc-700/60 rounded-2xl w-full max-w-lg mx-4 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
              {/* Modal header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                    <GitBranch className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <h2 className="text-base font-semibold text-zinc-100">Add Git Repository</h2>
                    <p className="text-xs text-zinc-500">FluxCD will auto-deploy resources at the given path</p>
                  </div>
                </div>
                <button
                  onClick={() => { setAdding(false); setAddError(null); }}
                  className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Modal body */}
              <div className="px-6 py-5 space-y-5">
                {addError && (
                  <div className="flex items-start gap-2.5 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                    <XCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-red-400">{addError}</p>
                  </div>
                )}

                {/* Name + URL row */}
                <div className="grid grid-cols-5 gap-3">
                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                      Name
                    </label>
                    <input
                      value={form.name}
                      onChange={e => setForm({ ...form, name: e.target.value })}
                      placeholder="my-app"
                      autoFocus
                      className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-colors"
                    />
                  </div>
                  <div className="col-span-3">
                    <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                      Git URL
                    </label>
                    <input
                      value={form.url}
                      onChange={e => setForm({ ...form, url: e.target.value })}
                      placeholder="https://github.com/user/repo.git"
                      className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono placeholder:text-zinc-600 outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-colors"
                    />
                  </div>
                </div>

                {/* Branch + Path row */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                      Branch
                    </label>
                    <div className="relative">
                      <input
                        value={form.branch}
                        onChange={e => setForm({ ...form, branch: e.target.value })}
                        className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg pl-3 pr-8 py-2 text-sm text-zinc-200 font-mono placeholder:text-zinc-600 outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-colors"
                      />
                      <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-600 pointer-events-none" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                      Kustomize Path
                    </label>
                    <input
                      value={form.path}
                      onChange={e => setForm({ ...form, path: e.target.value })}
                      placeholder="./"
                      className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono placeholder:text-zinc-600 outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-colors"
                    />
                  </div>
                </div>

                {/* Auth section */}
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-2">
                    Authentication
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {([
                      { key: "none" as const, icon: Globe, label: "Public", desc: "No auth" },
                      { key: "ssh" as const, icon: Key, label: "SSH Key", desc: "Deploy key" },
                      { key: "https" as const, icon: Lock, label: "HTTPS", desc: "Token" },
                    ]).map(({ key, icon: Icon, label, desc }) => (
                      <button
                        key={key}
                        onClick={() => setForm({ ...form, authMethod: key, authData: "" })}
                        className={`flex items-center gap-2.5 p-3 rounded-lg border text-left transition-all ${
                          form.authMethod === key
                            ? "border-indigo-500/50 bg-indigo-500/10 text-indigo-300"
                            : "border-zinc-700/50 bg-zinc-800/30 text-zinc-500 hover:border-zinc-600/50 hover:text-zinc-400"
                        }`}
                      >
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                          form.authMethod === key ? "bg-indigo-500/20" : "bg-zinc-700/30"
                        }`}>
                          <Icon className={`w-4 h-4`} />
                        </div>
                        <div>
                          <div className="text-sm font-medium">{label}</div>
                          <div className="text-[10px] opacity-70">{desc}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Auth credential input */}
                {form.authMethod !== "none" && (
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                      {form.authMethod === "ssh" ? "SSH Deploy Key" : "Personal Access Token"}
                    </label>
                    <textarea
                      value={form.authData}
                      onChange={e => setForm({ ...form, authData: e.target.value })}
                      placeholder={
                        form.authMethod === "ssh"
                          ? "-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----"
                          : "ghp_xxxxxxxxxxxxxxxxxxxx"
                      }
                      rows={form.authMethod === "ssh" ? 4 : 1}
                      className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono placeholder:text-zinc-600 outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-colors resize-none"
                    />
                    <p className="text-[10px] text-zinc-600 mt-1.5">
                      {form.authMethod === "ssh"
                        ? "Paste the entire private key. Stored encrypted at rest."
                        : "Create a fine-grained token with read-only repo access."}
                    </p>
                  </div>
                )}
              </div>

              {/* Modal footer */}
              <div className="flex items-center justify-end gap-2.5 px-6 py-4 border-t border-zinc-800 bg-zinc-900/50 rounded-b-2xl">
                <button
                  onClick={() => { setAdding(false); setAddError(null); }}
                  className="px-4 py-2 rounded-lg text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={addRepo}
                  disabled={!form.name || !form.url}
                  className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <GitBranch className="w-4 h-4" />
                  Add Repository
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tree View */}
        {loading && trees.length === 0 ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-16rem)]">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : trees.length === 0 ? (
          <div className="glass-card p-8 rounded-xl text-center">
            <GitBranch className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Git Repositories</h3>
            <p className="text-sm text-zinc-500">
              Add a Git repository above. FluxCD will automatically deploy the kustomize/Helm resources found at the path.
            </p>
          </div>
        ) : (
          <div className="glass-card rounded-xl overflow-hidden">
            {/* Column headers */}
            <div className="flex items-center gap-2 py-2.5 px-3 border-b border-zinc-800/60 text-[10px] text-zinc-500 uppercase tracking-wider">
              <div className="w-8 flex-shrink-0" /> {/* expand chevron */}
              <div className="min-w-0 flex-1 pl-5">Name</div>
              <div className="flex items-center gap-2 w-32 flex-shrink-0 justify-end">
                <span className="w-12 text-right">Rev</span>
                <span className="w-20 text-right hidden md:inline">Last Sync</span>
                <span className="w-16" /> {/* actions */}
              </div>
            </div>
            {filteredTrees.map((node, i) => (
              <FluxTreeRow
                key={node.id}
                node={node}
                depth={0}
                isLast={i === filteredTrees.length - 1}
                parentIsLast={[]}
                onSync={(id) => triggerSync(id)}
                onDelete={(id, name) => setShowConfirm({ id, name, namespace: node.namespace })}
                syncingId={syncing}
                deletingId={deleting}
              />
            ))}
          </div>
        )}

        {/* Delete Error */}
        {deleteError && (
          <div className="mt-3 p-3 rounded-lg bg-red-500/5 border border-red-500/10 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
              <span className="text-sm text-red-300">{deleteError}</span>
            </div>
            <button
              onClick={() => setDeleteError(null)}
              className="text-zinc-500 hover:text-zinc-300 ml-4 flex-shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Delete Confirmation */}
        {showConfirm && (
          <div className="mt-3 p-3 rounded-lg bg-red-500/5 border border-red-500/10 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-400" />
              <span className="text-sm text-zinc-300">
                Delete &quot;{showConfirm.name}&quot; and ALL resources in the <code className="text-xs bg-zinc-800 px-1 py-0.5 rounded">{showConfirm.namespace}</code> namespace?
              </span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowConfirm(null)}
                className="px-3 py-1.5 rounded border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteRepo(showConfirm.id, showConfirm.name, showConfirm.namespace)}
                className="px-3 py-1.5 rounded bg-red-600 hover:bg-red-700 text-white text-xs font-medium transition-colors"
              >
                Remove
              </button>
            </div>
          </div>
        )}

        {/* Delete Progress Modal */}
        {deleteProgress && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="bg-zinc-900 border border-zinc-700/60 rounded-2xl w-full max-w-md mx-4 shadow-2xl overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-red-500/10 flex items-center justify-center">
                    <Trash2 className="w-5 h-5 text-red-400" />
                  </div>
                  <div>
                    <h2 className="text-base font-semibold text-zinc-100">Deleting {deleteProgress.repoName}</h2>
                    <p className="text-xs text-zinc-500">Namespace: {deleteProgress.namespace}</p>
                  </div>
                </div>
                {deleteProgress.done && (
                  <button
                    onClick={() => setDeleteProgress(null)}
                    className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>

              {/* Steps */}
              <div className="px-6 py-5 space-y-4">
                {deleteProgress.steps.map((step, i) => (
                  <div key={step.step} className="flex items-start gap-3">
                    {/* Status icon */}
                    <div className="flex-shrink-0 mt-0.5">
                      {step.status === "pending" && (
                        <div className="w-5 h-5 rounded-full border-2 border-zinc-600" />
                      )}
                      {step.status === "running" && (
                        <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
                      )}
                      {step.status === "done" && (
                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      )}
                      {step.status === "error" && (
                        <AlertTriangle className="w-5 h-5 text-amber-400" />
                      )}
                    </div>
                    {/* Step detail */}
                    <div className="min-w-0">
                      <p className={`text-sm ${
                        step.status === "done" ? "text-zinc-500" :
                        step.status === "error" ? "text-amber-300" :
                        "text-zinc-200"
                      }`}>
                        {step.detail}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end gap-2.5 px-6 py-4 border-t border-zinc-800 bg-zinc-900/50 rounded-b-2xl">
                {deleteProgress.error && (
                  <p className="text-xs text-red-400 mr-auto">{deleteProgress.error}</p>
                )}
                {!deleteProgress.done ? (
                  <button
                    onClick={cancelDelete}
                    className="px-4 py-2 rounded-lg text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                  >
                    Dismiss
                  </button>
                ) : (
                  <button
                    onClick={() => setDeleteProgress(null)}
                    className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-medium transition-colors"
                  >
                    Close
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
      </ViewportWrapper>
    </div>
  );
}
