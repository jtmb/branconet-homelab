"use client";

import { useState, useEffect, useCallback } from "react";
import { LayoutDashboard, Server, Activity, HardDrive, Box, Loader2, Trash2, GitBranch, Settings, Key, Shield, Terminal, ShieldAlert } from "lucide-react";
import ViewportWrapper from "./viewport-wrapper";

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
  const [secretCount, setSecretCount] = useState(0);
  const [configCount, setConfigCount] = useState(0);

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

  const fetchVarCounts = useCallback(async () => {
    try {
      const res = await fetch("/api/vars");
      const data = await res.json();
      if (Array.isArray(data)) {
        setSecretCount(data.filter((v: { category: string }) => v.category === "secret").length);
        setConfigCount(data.filter((v: { category: string }) => v.category !== "secret").length);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchVarCounts();
  }, [fetchVarCounts]);

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
    <div className="flex flex-col min-h-0">

      {/* Confirmation Modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setShowConfirm(false)}
          />

          {/* Modal */}
          <div className="relative z-10 w-full max-w-lg mx-4 rounded-2xl bg-zinc-900 border border-red-500/20 shadow-2xl shadow-red-500/10 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="px-6 pt-6 pb-4 flex items-start gap-4">
              <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                <Trash2 className="w-5 h-5 text-red-400" />
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-semibold text-red-400">Remove Cluster</h3>
                <p className="text-sm text-zinc-400 mt-1">
                  This will clear the cluster configuration from the local database.
                </p>
              </div>
            </div>

            {/* Warning */}
            <div className="mx-6 mb-5 px-4 py-3 rounded-xl bg-amber-500/5 border border-amber-500/15 flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-amber-300">Are you sure?</p>
                <p className="text-[13px] text-amber-400/70 mt-1 leading-relaxed">
                  This will remove all cluster data — nodes, pods, volumes, and configuration
                  — from the app database. It does <strong className="text-amber-300">not</strong> affect
                  any running servers, only the local database.
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="px-6 pb-6 flex items-center gap-3 justify-end border-t border-zinc-800/60 pt-4">
              <button
                onClick={() => setShowConfirm(false)}
                disabled={removing}
                className="px-5 py-2.5 rounded-xl bg-zinc-800/80 border border-zinc-700/40 text-zinc-300 hover:bg-zinc-700 hover:text-white text-sm font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={removeCluster}
                disabled={removing}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-sm font-semibold transition-colors shadow-lg shadow-red-600/20 disabled:opacity-50"
              >
                {removing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                {removing ? "Removing…" : "Yes, Remove Cluster"}
              </button>
            </div>
          </div>
        </div>
      )}

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        <div className="flex items-center gap-3 mb-6">
          <LayoutDashboard className="page-header-icon text-indigo-400" />
          <h1 className="page-header-title">Overview</h1>
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
            <div className="grid md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
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

              <div className="glass-card p-4 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Key className="w-5 h-5 text-cyan-400" />
                  <span className="text-sm text-zinc-400">Secrets</span>
                </div>
                <p className="text-2xl font-bold text-zinc-100">
                  {secretCount}
                  <span className="text-sm text-zinc-500 ml-1">+ {configCount}</span>
                </p>
                <p className="text-xs text-zinc-500 mt-1">Secrets / Config Vars</p>
              </div>
            </div>

            {/* Quick Links */}
            <div className="grid md:grid-cols-2 lg:grid-cols-6 gap-4 mb-6">
              <a href="/nodes" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors">
                <Server className="w-8 h-8 text-blue-400 mb-3" />
                <h3 className="text-lg font-semibold text-zinc-100 mb-1">Nodes</h3>
                <p className="text-sm text-zinc-400">View and manage cluster nodes</p>
              </a>

              <a href="/workloads" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors">
                <Box className="w-8 h-8 text-emerald-400 mb-3" />
                <h3 className="text-lg font-semibold text-zinc-100 mb-1">Workloads</h3>
                <p className="text-sm text-zinc-400">View pods, deployments, and services</p>
              </a>

              <a href="/storage" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors">
                <HardDrive className="w-8 h-8 text-purple-400 mb-3" />
                <h3 className="text-lg font-semibold text-zinc-100 mb-1">Storage</h3>
                <p className="text-sm text-zinc-400">Manage Longhorn volumes and PVCs</p>
              </a>

              <a href="/flux" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors">
                <GitBranch className="w-8 h-8 text-emerald-400 mb-3" />
                <h3 className="text-lg font-semibold text-zinc-100 mb-1">Flux</h3>
                <p className="text-sm text-zinc-400">GitOps deployments via FluxCD</p>
              </a>

              <a href="/deploy" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors">
                <Terminal className="w-8 h-8 text-emerald-400 mb-3" />
                <h3 className="text-lg font-semibold text-zinc-100 mb-1">Deploy</h3>
                <p className="text-sm text-zinc-400">Run Ansible playbooks with live terminal output</p>
              </a>

              <a href="/secrets" className="glass-card p-6 rounded-xl hover:bg-zinc-800/80 transition-colors">
                <Key className="w-8 h-8 text-cyan-400 mb-3" />
                <h3 className="text-lg font-semibold text-zinc-100 mb-1">Secrets</h3>
                <p className="text-sm text-zinc-400">Manage variables and encrypted secrets</p>
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
              in the Secrets Engine if you already have a cluster running.
            </p>
          </div>
        ) : (
          <div className="mt-6">
            <a
              href="/nodes"
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
      </ViewportWrapper>
    </div>
  );
}