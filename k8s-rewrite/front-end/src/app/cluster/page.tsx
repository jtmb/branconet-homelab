"use client";

import Link from "next/link";
import { useState, useEffect, useCallback } from "react";
import { Server, Activity, HardDrive, Box, Loader2, Trash2, XCircle, GitBranch } from "lucide-react";

interface ClusterInfo {
  nodes: number;
  readyNodes: number;
  pods: number;
  runningPods: number;
  version: string;
  longhornVolumes: number;
  healthyVolumes: number;
  hasDbCluster: boolean;
  fluxRepos: number;
}

export default function ClusterPage() {
  const [info, setInfo] = useState<ClusterInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const fetchInfo = useCallback(async () => {
    try {
      const res = await fetch("/api/cluster/info");
      const data = await res.json();
      setInfo(data);
    } catch (err) {
      console.error("Failed to fetch cluster info:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInfo();
    const interval = setInterval(fetchInfo, 10000);
    return () => clearInterval(interval);
  }, [fetchInfo]);

  async function removeCluster() {
    setRemoving(true);
    setShowConfirm(false);
    try {
      await fetch("/api/cluster/remove", { method: "DELETE" });
      // Invalidate optimistic state immediately
      setInfo(null);
      setLoading(true);
      await fetchInfo();
    } catch (err) {
      console.error("Failed to remove cluster:", err);
    } finally {
      setRemoving(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center gap-3">
          <Link href="/" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors mr-2">
            Home
          </Link>
          <span className="text-zinc-700">|</span>
          <Server className="w-6 h-6 text-blue-400" />
          <h1 className="text-xl font-bold text-zinc-100">Cluster</h1>
          <span className="text-xs text-zinc-500 ml-auto">
            {info ? `K8s ${info.version || "N/A"}` : "Loading…"}
          </span>
          {info?.hasDbCluster && (
            <button
              onClick={() => setShowConfirm(true)}
              disabled={removing}
              className="ml-3 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 hover:text-red-300 text-xs font-medium transition-colors disabled:opacity-50"
            >
              {removing ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Trash2 className="w-3.5 h-3.5" />
              )}
              {removing ? "Removing…" : "Remove Cluster"}
            </button>
          )}
        </div>
      </header>

      {/* Confirmation Modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
                <XCircle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-zinc-100">Remove Cluster</h2>
                <p className="text-xs text-zinc-400">This cleans the database only</p>
              </div>
            </div>
            <p className="text-sm text-zinc-300 mb-6">
              This will remove the cluster configuration and all associated data
              (nodes, pods, volumes) from the app database. It does <strong>not</strong> affect
              any running servers — it only clears the local database.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                disabled={removing}
                className="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-300 hover:bg-zinc-800 text-sm transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={removeCluster}
                disabled={removing}
                className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {removing && <Loader2 className="w-4 h-4 animate-spin" />}
                {removing ? "Removing…" : "Remove"}
              </button>
            </div>
          </div>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {loading && !info ? (
          <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : (
          <>
            {/* Status Banner — only when there are nodes */}
            {info && info.nodes > 0 && (
              <div className={`mb-6 px-4 py-3 rounded-xl flex items-center gap-3 ${
                info.nodes === info.readyNodes
                  ? "bg-emerald-500/10 border border-emerald-500/20"
                  : "bg-amber-500/10 border border-amber-500/20"
              }`}>
                <span className={`w-3 h-3 rounded-full ${
                  info.nodes === info.readyNodes ? "dot-success" : "dot-warning"
                }`} />
                <span className="text-sm">
                  {info.nodes === info.readyNodes
                    ? "Cluster is healthy"
                    : "Cluster is not fully operational"}
                </span>
              </div>
            )}

            {/* Summary Cards */}
            <div className="grid md:grid-cols-5 gap-4 mb-6">
              <div className="glass-card p-4 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Server className="w-5 h-5 text-blue-400" />
                  <span className="text-sm text-zinc-400">Nodes</span>
                </div>
                <p className="text-2xl font-bold text-zinc-100">
                  {info?.readyNodes || 0}
                  <span className="text-sm text-zinc-500 ml-1">/ {info?.nodes || 0}</span>
                </p>
                <p className="text-xs text-zinc-500 mt-1">Ready / Total</p>
              </div>

              <div className="glass-card p-4 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Box className="w-5 h-5 text-emerald-400" />
                  <span className="text-sm text-zinc-400">Pods</span>
                </div>
                <p className="text-2xl font-bold text-zinc-100">
                  {info?.runningPods || 0}
                  <span className="text-sm text-zinc-500 ml-1">/ {info?.pods || 0}</span>
                </p>
                <p className="text-xs text-zinc-500 mt-1">Running / Total</p>
              </div>

              <div className="glass-card p-4 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <HardDrive className="w-5 h-5 text-purple-400" />
                  <span className="text-sm text-zinc-400">Longhorn Volumes</span>
                </div>
                <p className="text-2xl font-bold text-zinc-100">
                  {info?.healthyVolumes || 0}
                  <span className="text-sm text-zinc-500 ml-1">/ {info?.longhornVolumes || 0}</span>
                </p>
                <p className="text-xs text-zinc-500 mt-1">Healthy / Total</p>
              </div>

              <div className="glass-card p-4 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-5 h-5 text-indigo-400" />
                  <span className="text-sm text-zinc-400">Status</span>
                </div>
                <p className={`text-lg font-bold ${
                  info?.nodes && info.nodes > 0 ? "text-emerald-400" : "text-amber-400"
                }`}>
                  {info?.nodes && info.nodes > 0 ? "Operational" : "Not Deployed"}
                </p>
              </div>

              <div className="glass-card p-4 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <GitBranch className="w-5 h-5 text-emerald-400" />
                  <span className="text-sm text-zinc-400">Flux Repos</span>
                </div>
                <p className="text-2xl font-bold text-zinc-100">
                  {info?.fluxRepos || 0}
                </p>
                <p className="text-xs text-zinc-500 mt-1">GitOps repos</p>
              </div>
            </div>

            {/* Quick Links */}
            <div className="grid md:grid-cols-4 gap-4">
              <a href="/cluster/nodes" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors">
                <Server className="w-8 h-8 text-blue-400 mb-3" />
                <h3 className="text-lg font-semibold text-zinc-100 mb-1">Nodes</h3>
                <p className="text-sm text-zinc-400">View and manage cluster nodes</p>
              </a>

              <a href="/cluster/workloads" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors">
                <Box className="w-8 h-8 text-emerald-400 mb-3" />
                <h3 className="text-lg font-semibold text-zinc-100 mb-1">Workloads</h3>
                <p className="text-sm text-zinc-400">View pods, deployments, and services</p>
              </a>

              <a href="/cluster/storage" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors">
                <HardDrive className="w-8 h-8 text-purple-400 mb-3" />
                <h3 className="text-lg font-semibold text-zinc-100 mb-1">Storage</h3>
                <p className="text-sm text-zinc-400">Manage Longhorn volumes and PVCs</p>
              </a>

              <a href="/cluster/flux" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors">
                <GitBranch className="w-8 h-8 text-emerald-400 mb-3" />
                <h3 className="text-lg font-semibold text-zinc-100 mb-1">Flux</h3>
                <p className="text-sm text-zinc-400">GitOps deployments via FluxCD</p>
              </a>
            </div>
          </>
        )}

        {/* Sub-pages */}
        {loading ? null : (!info || info.nodes === 0) ? (
          <div className="mt-6 glass-card p-8 rounded-xl text-center">
            <Server className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Cluster Detected</h3>
            <p className="text-sm text-zinc-500 max-w-md mx-auto">
              Deploy a cluster first using the Deploy tab, or configure the kubeconfig 
              in the Variables tab if you already have a cluster running.
            </p>
          </div>
        ) : (
          <div className="mt-6">
            <a
              href="/cluster/nodes"
              className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors flex items-center justify-between"
            >
              <div>
                <h3 className="text-lg font-semibold text-zinc-100 mb-1">View Full Dashboard</h3>
                <p className="text-sm text-zinc-400">Manage nodes, workloads, and storage</p>
              </div>
              <span className="text-indigo-400">→</span>
            </a>
          </div>
        )}
      </main>
    </div>
  );
}