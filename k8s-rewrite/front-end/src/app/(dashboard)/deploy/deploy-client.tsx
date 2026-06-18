"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  Play,
  StopCircle,
  History,
  Terminal as TerminalIcon,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Skull,
  ChevronDown,
  Info,
  AlertTriangle,
  ShieldAlert,
  Trash2,
  ChevronRight,
} from "lucide-react";
import Link from "next/link";
import DeployLogViewer, { DeployLogViewerHandle } from "@/components/deploy/deploy-log-viewer";

interface Job {
  id: string;
  playbook: string;
  status: string;
  output: string;
  startedAt: string;
  finishedAt?: string;
}

interface RoleProgress {
  role: string;
  status: "running" | "success" | "failed";
}

const ALL_ROLES = [
  "bootstrap",
  "kubernetes",
  "network",
  "dns",
  "storage",
  "longhorn",
  "nfs",
  "samba",
  "ingress",
  "gitops",
  "secrets",
];

const ROLE_INFO: Record<string, { desc: string; order: number }> = {
  bootstrap:   { desc: "OS packages, containerd runtime, and kernel sysctl tuning — runs on all nodes.", order: 1 },
  kubernetes:  { desc: "kubeadm, kubelet, and kubectl — initializes the control plane or joins workers.", order: 2 },
  network:     { desc: "Calico CNI plugin for pod networking — master node only.", order: 3 },
  dns:         { desc: "CoreDNS cluster DNS resolver — master node only.", order: 4 },
  storage:     { desc: "local-path-provisioner for dynamic PVCs on node local storage — master only.", order: 5 },
  longhorn:    { desc: "Longhorn distributed block storage with replication and backups — master only.", order: 6 },
  nfs:         { desc: "NFS server + nfs-subdir-external-provisioner — only runs when nfs_enabled is true.", order: 7 },
  samba:       { desc: "Samba/SMB server + csi-driver-smb for Windows-friendly shares — when samba_enabled.", order: 8 },
  ingress:     { desc: "Traefik ingress controller for HTTP/S routing to services — master only.", order: 9 },
  gitops:      { desc: "FluxCD GitOps operator — syncs cluster state from Git repositories — master only.", order: 10 },
  secrets:     { desc: "K8s Secrets from secret_* DB variables — runs after gitops with prune-disabled.", order: 11 },
};

export default function DeployClient() {
  const [running, setRunning] = useState(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [roleProgress, setRoleProgress] = useState<RoleProgress[]>([]);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [infoExpanded, setInfoExpanded] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const terminalRef = useRef<DeployLogViewerHandle | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const doneReceivedRef = useRef(false);

  useEffect(() => {
    // Fetch immediately, then re-attach to any running job
    fetchJobsAndReconnect();
    const retry = setTimeout(fetchJobsAndReconnect, 2000);
    return () => clearTimeout(retry);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchJobsAndReconnect() {
    await fetchJobs();
    // If a job is still running, reconnect its SSE stream for live output
    setJobs((prev) => {
      const runningJob = prev.find((j) => j.status === "running");
      if (runningJob && runningJob.id !== currentJobId) {
        // Schedule reconnect outside setState callback
        setTimeout(() => reconnectToJob(runningJob.id, runningJob.output || ""), 0);
      }
      return prev;
    });
  }

  function reconnectToJob(jobId: string, existingOutput: string) {
    const term = terminalRef.current;
    if (term) {
      term.clear();
      if (existingOutput) {
        term.write(existingOutput);
        term.writeln("\nReconnected — streaming new output...\n");
      }
    }
    setRunning(true);
    setCurrentJobId(jobId);
    connectSSE(jobId);
  }

  const handleTerminalReady = useCallback((term: DeployLogViewerHandle) => {
    terminalRef.current = term;
    term.writeln("Select a role from the dropdown or click 'Deploy Cluster'.");
    term.writeln("");
  }, []);

  async function startDeploy(role?: string) {
    if (running) return;

    setRunning(true);
    setRoleProgress([]);
    setCurrentJobId(null);

    const roles = role ? [role] : [];
    const label = role || "site.yml";

    try {
      const term = terminalRef.current;
      if (term) {
        term.clear();
        term.writeln("Syncing config vars to Ansible...");
      }

      // Sync vars before kicking off the playbook
      try {
        const syncRes = await fetch("/api/vars/sync", { method: "POST" });
        if (syncRes.ok && term) {
          term.writeln("✓ Config vars synced");
        } else if (term) {
          const syncErr = await syncRes.json().catch(() => ({}));
          term.writeln(`⚠ Var sync skipped: ${syncErr.error || syncRes.status}`);
        }
      } catch (syncErr) {
        if (term) {
          term.writeln(`⚠ Var sync failed (non-fatal): ${syncErr}`);
        }
        // Non-fatal — continue with deploy even if sync fails
      }

      if (term) term.writeln("\nStarting deployment...\n");

      const res = await fetch("/api/deploy/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ playbook: "site.yml", roles }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setCurrentJobId(data.jobId);
      connectSSE(data.jobId);
    } catch (err) {
      try {
        const term = terminalRef.current;
        if (term) term.writeln(`\nError: ${err}`);
      } catch {
        // Terminal may be disposed
      }
      setRunning(false);
      fetchJobs();
    }
  }

  async function stopDeploy() {
    if (!currentJobId) return;

    try {
      if (terminalRef.current) {
        terminalRef.current.writeln("\nStopping deployment...");
      }

      await fetch(`/api/deploy/stop?jobId=${currentJobId}`, {
        method: "POST",
      });
    } catch (err) {
      console.error("Failed to stop deployment:", err);
    }

    disconnectSSE();
    setRunning(false);
    setCurrentJobId(null);
    fetchJobs();
  }

  async function killJob(jobId: string) {
    try {
      if (terminalRef.current) terminalRef.current.writeln(`\nKilling job ${jobId}...`);
      await fetch(`/api/deploy/stop?jobId=${jobId}`, { method: "POST" });
    } catch (err) {
      console.error("Failed to kill job:", err);
    }
    fetchJobs();
    if (currentJobId === jobId) {
      disconnectSSE();
      setRunning(false);
      setCurrentJobId(null);
    }
  }

  async function deleteJob(jobId: string) {
    try {
      await fetch(`/api/deploy/history?jobId=${jobId}`, { method: "DELETE" });
    } catch (err) {
      console.error("Failed to delete job:", err);
    }
    fetchJobs();
  }

  function connectSSE(jobId: string) {
    disconnectSSE();
    doneReceivedRef.current = false;

    const es = new EventSource(`/api/deploy/stream?jobId=${jobId}`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.done) {
          doneReceivedRef.current = true;
          disconnectSSE();
          setRunning(false);
          setCurrentJobId(null);
          fetchJobs();
          return;
        }

        // Write output to xterm terminal (handles ANSI codes natively)
        if (data.output && terminalRef.current) {
          terminalRef.current.write(data.output);
        }

        // Update role progress
        if (data.roleProgress) {
          setRoleProgress((prev) => {
            const existing = [...prev];
            for (const rp of data.roleProgress) {
              const idx = existing.findIndex((e) => e.role === rp.role);
              if (idx >= 0) {
                existing[idx] = rp;
              } else {
                existing.push(rp);
              }
            }
            return existing;
          });
        }
      } catch {
        // Ignore parse errors
      }
    };

    es.onerror = () => {
      if (doneReceivedRef.current) return;
      disconnectSSE();
      setRunning(false);
      setCurrentJobId(null);
      fetchJobs();
    };
  }

  function disconnectSSE() {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleClick);
    }
    return () => document.removeEventListener("mousedown", handleClick);
  }, [dropdownOpen]);

  async function fetchJobs() {
    try {
      const res = await fetch("/api/deploy/history");
      // Check content-type before parsing JSON (avoids SyntaxError on
      // Next.js compilation responses in dev mode)
      const contentType = res.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        return;
      }
      const data = await res.json();
      setJobs(data);
    } catch (err) {
      console.warn("Failed to fetch job history:", err);
    }
  }

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      disconnectSSE();
    };
  }, []);

  function viewJobOutput(job: Job) {
    const term = terminalRef.current;
    if (!term) return;
    try { term.clear(); } catch { /* not mounted */ }
    if (job.output) {
      term.write(job.output);
    } else {
      term.writeln("No output captured for this job.");
    }
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case "running":
        return <Loader2 className="w-3 h-3 animate-spin text-amber-400" />;
      case "success":
        return <CheckCircle2 className="w-3 h-3 text-emerald-400" />;
      case "failed":
        return <XCircle className="w-3 h-3 text-red-400" />;
      default:
        return <Clock className="w-3 h-3 text-zinc-500" />;
    }
  };

  return (
    <div className="flex flex-col min-h-0 h-full">

      <main className="px-4 sm:px-6 py-6 flex flex-col min-h-0 flex-1 space-y-5">

        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-4 text-xs text-zinc-500">
          <span className="text-zinc-300">Provisioning</span>
        </div>

        {/* ── Header ── */}
        <div className="flex items-center gap-3">
          <TerminalIcon className="w-6 h-6 text-emerald-400" />
          <h1 className="text-xl font-semibold text-zinc-100">Provisioning</h1>
          <span className="text-sm text-zinc-500 ml-auto">
            {running ? "Deploying…" : jobs.length > 0 ? `${jobs.length} job${jobs.length !== 1 ? "s" : ""}` : "Ready"}
          </span>
        </div>

        {/* ── Controls ── */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Deploy split-button with role dropdown */}
          <div className="relative flex" ref={dropdownRef}>
            <button
              onClick={() => { setDropdownOpen(false); setShowConfirm(true); }}
              disabled={running}
              className="flex items-center gap-2 px-5 py-2.5 rounded-l-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-600/20"
            >
              {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              {running ? "Deploying…" : selectedRole ? `Deploy ${selectedRole}` : "Deploy Cluster"}
            </button>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              disabled={running}
              className="flex items-center px-2 py-2.5 rounded-r-xl bg-indigo-600 hover:bg-indigo-500 text-white/70 hover:text-white border-l border-white/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-600/20"
            >
              <ChevronDown className={`w-4 h-4 transition-transform ${dropdownOpen ? "rotate-180" : ""}`} />
            </button>
            {dropdownOpen && (
              <div className="absolute top-full mt-1.5 w-52 rounded-xl bg-zinc-800 border border-zinc-700/60 shadow-xl shadow-black/40 z-30 py-1 overflow-hidden">
                <button
                  onClick={() => { setSelectedRole(null); setDropdownOpen(false); }}
                  className={`w-full text-left px-3.5 py-2 text-sm flex items-center gap-2 hover:bg-zinc-700/60 transition-colors ${selectedRole === null ? "text-white bg-indigo-600/20" : "text-zinc-300"}`}
                >
                  <TerminalIcon className="w-3.5 h-3.5" />
                  All Roles (site.yml)
                </button>
                <div className="border-t border-zinc-700/40 my-1" />
                {ALL_ROLES.map((role) => (
                  <button
                    key={role}
                    onClick={() => { setSelectedRole(role); setDropdownOpen(false); }}
                    className={`w-full text-left px-3.5 py-2 text-sm capitalize hover:bg-zinc-700/60 transition-colors ${selectedRole === role ? "text-white bg-indigo-600/20" : "text-zinc-300"}`}
                  >
                    {role}
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={stopDeploy}
            disabled={!running}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-red-600/20 border border-red-500/20 text-red-400 hover:bg-red-600/30 hover:text-red-300 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <StopCircle className="w-4 h-4" />
            Stop
          </button>

          <button
            onClick={fetchJobs}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-zinc-800/80 border border-zinc-700/40 text-zinc-400 hover:bg-zinc-700/80 hover:text-zinc-200 text-sm font-medium transition-colors"
          >
            <History className="w-4 h-4" />
            Refresh
          </button>

          {/* Info toggle */}
          <button
            onClick={() => setInfoExpanded(!infoExpanded)}
            className={`flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-sm transition-colors ${infoExpanded ? "bg-indigo-500/10 border border-indigo-500/20 text-indigo-300" : "bg-zinc-800/80 border border-zinc-700/40 text-zinc-500 hover:text-zinc-300"}`}
          >
            <Info className="w-3.5 h-3.5" />
            Roles
          </button>
        </div>

        {/* ── Role info (collapsible) ── */}
        {infoExpanded && (
          <div className="rounded-xl bg-indigo-500/5 border border-indigo-500/15 px-4 py-3">
            <p className="text-[13px] text-zinc-400 leading-relaxed mb-3">
              Use the dropdown on the <strong className="text-zinc-300">Deploy</strong> button to run a single role
              instead of the full playbook. Roles run in order; skip ahead only when you&apos;re certain earlier
              roles are already applied.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5">
              {ALL_ROLES.map((role) => {
                const info = ROLE_INFO[role];
                return (
                  <div key={role} className="flex items-start gap-2 px-2.5 py-1.5 rounded-lg hover:bg-indigo-500/5 transition-colors">
                    <span className="text-[10px] font-mono text-indigo-500/50 mt-0.5 min-w-[1rem] text-right tabular-nums">{info.order}</span>
                    <div className="min-w-0">
                      <span className="text-[12px] font-medium text-zinc-300 capitalize">{role}</span>
                      <p className="text-[11px] text-zinc-500 leading-relaxed mt-0.5">{info.desc}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Log Viewer ── */}
        <section className="flex flex-col min-h-0 flex-1 rounded-xl bg-zinc-900/70 border border-zinc-800 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center gap-2 bg-zinc-900/80 flex-shrink-0">
            <div className={`w-2 h-2 rounded-full ${running ? "bg-amber-400 animate-pulse" : "bg-zinc-600"}`} />
            <span className="text-xs text-zinc-500">
              {running ? `Running — ${selectedRole || "site.yml"}` : "Idle"}
            </span>
            {currentJobId && (
              <span className="text-[10px] text-zinc-600 ml-auto font-mono">{currentJobId.slice(0, 8)}</span>
            )}
          </div>
          <div className="flex-1 min-h-0">
            <DeployLogViewer
              className="h-full"
              onReady={handleTerminalReady}
            />
          </div>
        </section>

        {/* ── Role Progress Pills ── */}
        {roleProgress.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] text-zinc-500 mr-1">Roles:</span>
            {roleProgress.map((rp) => (
              <span
                key={rp.role}
                className={`inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full font-medium ${
                  rp.status === "success"
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : rp.status === "failed"
                    ? "bg-red-500/10 text-red-400 border border-red-500/20"
                    : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                }`}
              >
                {statusIcon(rp.status)}
                {rp.role}
                {rp.status === "running" && <Loader2 className="w-3 h-3 animate-spin text-amber-400" />}
              </span>
            ))}
          </div>
        )}

        {/* ── Job History ── */}
        <section className="rounded-xl bg-zinc-900/70 border border-zinc-800 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center gap-2 bg-zinc-900/80">
            <History className="w-4 h-4 text-zinc-400" />
            <h2 className="text-sm font-medium text-zinc-300">Deployment History</h2>
            <span className="text-[10px] text-zinc-600 ml-auto">{jobs.length}</span>
          </div>
          {jobs.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-sm">
              <TerminalIcon className="w-8 h-8 text-zinc-700 mx-auto mb-2 opacity-50" />
              <p>No deployments yet.</p>
              <p className="text-xs text-zinc-600 mt-1">Use the dropdown to deploy a single role or the full cluster.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-800/40 bg-zinc-900/40">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wider">Playbook</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wider">Status</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wider">Started</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wider">Finished</th>
                  <th className="text-right px-4 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/30">
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    onClick={() => viewJobOutput(job)}
                    className="hover:bg-zinc-800/40 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-sm text-zinc-200 font-mono">{job.playbook}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium ${
                        job.status === "success"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : job.status === "failed"
                          ? "bg-red-500/10 text-red-400 border border-red-500/20"
                          : job.status === "running"
                          ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                          : "bg-zinc-800 text-zinc-500 border border-zinc-700/40"
                      }`}>
                        {statusIcon(job.status)}
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-zinc-500">{new Date(job.startedAt).toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm text-zinc-500">
                      {job.finishedAt ? new Date(job.finishedAt).toLocaleString() : <span className="text-zinc-600">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center gap-2 justify-end">
                        {job.status === "running" && (
                          <button
                            onClick={(e) => { e.stopPropagation(); killJob(job.id); }}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 hover:text-red-300 text-xs font-medium transition-colors"
                          >
                            <Skull className="w-3 h-3" />
                            Kill
                          </button>
                        )}
                        {job.status !== "running" && (
                          <>
                            <button
                              onClick={(e) => { e.stopPropagation(); viewJobOutput(job); }}
                              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                            >
                              View Output
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); deleteJob(job.id); }}
                              className="inline-flex items-center p-1.5 rounded-lg text-zinc-600 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                              title="Delete entry"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}
                        {job.status === "running" && (
                          <button disabled className="inline-flex items-center p-1.5 rounded-lg text-zinc-700 cursor-not-allowed" title="Cannot delete a running job">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

      </main>

      {/* ── Confirmation Modal ── */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setShowConfirm(false)} />
          <div className="relative z-10 w-full max-w-lg mx-4 rounded-2xl bg-zinc-900 border border-red-500/20 shadow-2xl shadow-red-500/10 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 pt-6 pb-4 flex items-start gap-4">
              <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-semibold text-red-400">
                  {selectedRole ? `Deploy ${selectedRole}` : "Deploy Full Cluster"}
                </h3>
                <p className="text-sm text-zinc-400 mt-1">
                  {selectedRole
                    ? <>You are about to run the <strong className="text-zinc-200 capitalize">{selectedRole}</strong> role against the cluster.</>
                    : <>You are about to run the <strong className="text-zinc-200">site.yml</strong> playbook across all roles on the entire cluster.</>
                  }
                </p>
              </div>
            </div>
            <div className="mx-6 mb-5 px-4 py-3 rounded-xl bg-amber-500/5 border border-amber-500/15 flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-amber-300">Warning — Proceed at Your Own Risk</p>
                <p className="text-[13px] text-amber-400/70 mt-1 leading-relaxed">
                  This could potentially <strong className="text-amber-300">destroy your cluster</strong> if you
                  don&apos;t know what you are doing. Roles are re-applied and may overwrite existing
                  configuration, workloads, and data.
                </p>
              </div>
            </div>
            <div className="px-6 pb-6 flex items-center gap-3 justify-end border-t border-zinc-800/60 pt-4">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-5 py-2.5 rounded-xl bg-zinc-800/80 border border-zinc-700/40 text-zinc-300 hover:bg-zinc-700 hover:text-white text-sm font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => { setShowConfirm(false); startDeploy(selectedRole || undefined); }}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-sm font-semibold transition-colors shadow-lg shadow-red-600/20"
              >
                <AlertTriangle className="w-4 h-4" />
                Deploy at My Own Risk
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
