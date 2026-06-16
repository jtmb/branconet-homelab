"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import dynamicNext from "next/dynamic";
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
} from "lucide-react";
import Link from "next/link";

const DeployTerminal = dynamicNext(
  () => import("@/components/deploy/deploy-terminal"),
  {
    ssr: false,
    loading: () => (
      <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden min-h-[300px] flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
      </div>
    ),
  }
);

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

export default function DeployClient() {
  const [running, setRunning] = useState(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [roleProgress, setRoleProgress] = useState<RoleProgress[]>([]);
  const terminalRef = useRef<any>(null);
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
    // Write existing output to terminal first so user sees history
    const term = terminalRef.current;
    if (term) {
      try { term.clear(); } catch { /* not ready */ }
      if (existingOutput) {
        // Replay what's already captured, then stream new output live
        term.write(existingOutput);
        term.writeln("\r\n\x1b[33mReconnected — streaming new output...\x1b[0m\r\n");
      }
    }
    setRunning(true);
    setCurrentJobId(jobId);
    connectSSE(jobId);
  }

  const handleTerminalReady = useCallback((term: any) => {
    terminalRef.current = term;
    term.writeln("Click 'Deploy Cluster' to start the deployment.");
    term.writeln("");
  }, []);

  async function startDeploy() {
    if (running) return;

    setRunning(true);
    setRoleProgress([]);
    setCurrentJobId(null);

    try {
      const term = terminalRef.current;
      if (term) {
        try { term.clear(); } catch { /* terminal may not be fully initialized */ }
        term.writeln("\x1b[36mSyncing config vars to Ansible...\x1b[0m\r\n");
      }

      // Sync vars before kicking off the playbook
      try {
        const syncRes = await fetch("/api/vars/sync", { method: "POST" });
        if (syncRes.ok && term) {
          term.writeln("\x1b[32m✓ Config vars synced\x1b[0m\r\n");
        } else if (term) {
          const syncErr = await syncRes.json().catch(() => ({}));
          term.writeln(`\x1b[33m⚠ Var sync skipped: ${syncErr.error || syncRes.status}\x1b[0m\r\n`);
        }
      } catch (syncErr) {
        if (term) {
          term.writeln(`\x1b[33m⚠ Var sync failed (non-fatal): ${syncErr}\x1b[0m\r\n`);
        }
        // Non-fatal — continue with deploy even if sync fails
      }

      if (term) term.writeln("\r\nStarting deployment...\r\n");

      const res = await fetch("/api/deploy/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ playbook: "site.yml", roles: [] }),
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
        if (term) term.writeln(`\r\n\x1b[31mError: ${err}\x1b[0m`);
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
        terminalRef.current.writeln("\r\n\x1b[33mStopping deployment...\x1b[0m");
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
      if (terminalRef.current) {
        terminalRef.current.writeln(`\r\n\x1b[33mKilling job ${jobId}...\x1b[0m`);
      }
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
    <div className="min-h-screen bg-zinc-950">
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center gap-3">
          <Link href="/" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors mr-2">
            Home
          </Link>
          <span className="text-zinc-700">|</span>
          <TerminalIcon className="w-6 h-6 text-emerald-400" />
          <h1 className="text-xl font-bold text-zinc-100">Deploy Cluster</h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Controls */}
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={startDeploy}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {running ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {running ? "Deploying..." : "Deploy Cluster"}
          </button>

          <button
            onClick={stopDeploy}
            disabled={!running}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600/20 text-red-400 hover:bg-red-600/30 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <StopCircle className="w-4 h-4" />
            Stop
          </button>

          <button
            onClick={fetchJobs}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 text-zinc-400 hover:bg-zinc-700 font-medium transition-colors"
          >
            <History className="w-4 h-4" />
            Refresh History
          </button>
        </div>

        {/* Terminal + Role Progress */}
        <div className="flex gap-4 mb-6">
          {/* Terminal */}
          <div className="flex-1 min-w-0">
            <div className="border border-zinc-800 rounded-xl overflow-hidden">
              <div className="px-4 py-2 bg-zinc-900 border-b border-zinc-800 flex items-center gap-2">
                <TerminalIcon className="w-4 h-4 text-emerald-400" />
                <span className="text-xs text-zinc-500">Terminal Output</span>
              </div>
              <DeployTerminal onReady={handleTerminalReady} />
            </div>
          </div>

          {/* Role Progress Sidebar */}
          {roleProgress.length > 0 && (
            <div className="w-64 flex-shrink-0">
              <div className="border border-zinc-800 rounded-xl overflow-hidden">
                <div className="px-4 py-2 bg-zinc-900 border-b border-zinc-800 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-zinc-400" />
                  <span className="text-xs text-zinc-500">Roles</span>
                </div>
                <div className="max-h-[500px] overflow-y-auto p-3 space-y-2">
                  {roleProgress.map((rp) => (
                    <div
                      key={rp.role}
                      className="flex items-center gap-2 text-xs"
                    >
                      {statusIcon(rp.status)}
                      <span
                        className={`truncate ${
                          rp.status === "success"
                            ? "text-emerald-400"
                            : rp.status === "failed"
                            ? "text-red-400"
                            : "text-zinc-300"
                        }`}
                      >
                        {rp.role}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Job History */}
        <div className="border border-zinc-700/40 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-zinc-700/40 flex items-center gap-2">
            <History className="w-4 h-4 text-zinc-400" />
            <h2 className="text-sm font-medium text-zinc-300">
              Deployment History
            </h2>
          </div>
          {jobs.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-sm">
              No deployments yet.
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-800/40">
                  <th className="text-left px-4 py-2 text-xs font-medium text-zinc-500">
                    Playbook
                  </th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-zinc-500">
                    Status
                  </th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-zinc-500">
                    Started
                  </th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-zinc-500">
                    Finished
                  </th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-zinc-500">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    onClick={() => viewJobOutput(job)}
                    className="border-b border-zinc-800/30 hover:bg-zinc-800/20 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-2 text-sm text-zinc-300">
                      {job.playbook}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                          job.status === "success"
                            ? "bg-emerald-500/20 text-emerald-400"
                            : job.status === "failed"
                            ? "bg-red-500/20 text-red-400"
                            : "bg-zinc-800 text-zinc-400"
                        }`}
                      >
                        {statusIcon(job.status)}
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm text-zinc-500">
                      {new Date(job.startedAt).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-sm text-zinc-500">
                      {job.finishedAt
                        ? new Date(job.finishedAt).toLocaleString()
                        : "-"}
                    </td>
                    <td className="px-4 py-2">
                      {job.status === "running" && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            killJob(job.id);
                          }}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded bg-red-600/20 text-red-400 hover:bg-red-600/40 text-xs font-medium transition-colors"
                        >
                          <Skull className="w-3 h-3" />
                          Kill
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </div>
  );
}
