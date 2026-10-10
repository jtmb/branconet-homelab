"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { requestJson, useQuery, useSession } from "@/lib/use-query";
import { appendLogTail } from "@/lib/log-tail";
import { ResourceTable } from "@/components/cluster/resource-list";
import ViewportWrapper from "../viewport-wrapper";

const ConfirmDialog = dynamic(() => import("../confirm-dialog"), { ssr: false });
type Job = { id: string; playbook: string; status: string; startedAt: string; finishedAt?: string };
type Action = { kind: "start" | "stop" | "delete"; job?: Job; role?: string };
const ROLES = ["bootstrap", "kubernetes", "network", "dns", "storage", "longhorn", "nfs", "samba", "ingress", "gitops", "secrets"];
export default function DeployClient() {
  const session = useSession();
  const history = useQuery<Job[]>("/api/deploy/history");
  const refetchHistory = history.refetch;
  const [role, setRole] = useState("");
  const [action, setAction] = useState<Action>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selected, setSelected] = useState<string>();
  const [visible, setVisible] = useState(true);
  const [retry, setRetry] = useState(0);
  const [streamState, setStreamState] = useState("Idle");
  const [streamError, setStreamError] = useState("");
  const [log, setLog] = useState({ output: "", truncated: false });
  const cursor = useRef(0), initialConnection = useRef(false), mounted = useRef(false);
  const eventSource = useRef<EventSource>();
  const pending = useRef<AbortController>();
  const permitted = session.canWrite && session.data?.capabilities?.provisioning === true;
  const jobs = useMemo(() => Array.isArray(history.data) ? history.data : [], [history.data]);
  const running = jobs.some(job => job.status === "running");

  function select(jobId: string, initialOutput = "", initialCursor = 0, truncated = false) {
    eventSource.current?.close(); eventSource.current = undefined;
    cursor.current = initialCursor;
    const tail = appendLogTail("", initialOutput);
    setLog({ output: tail.output, truncated: truncated || tail.truncated });
    setStreamError(""); setSelected(jobId); setRetry(value => value + 1);
  }
  useEffect(() => {
    mounted.current = true;
    const updateVisibility = () => setVisible(document.visibilityState !== "hidden");
    updateVisibility(); document.addEventListener("visibilitychange", updateVisibility);
    return () => { mounted.current = false; pending.current?.abort(); eventSource.current?.close(); document.removeEventListener("visibilitychange", updateVisibility); };
  }, []);
  useEffect(() => {
    if (!session.loading && !session.data?.authenticated) {
      pending.current?.abort(); setAction(undefined); setSelected(undefined); setLog({ output: "", truncated: false });
    } else if (!session.canWrite) setAction(undefined);
  }, [session.loading, session.data?.authenticated, session.canWrite]);
  useEffect(() => {
    if (initialConnection.current || !history.updatedAt || !session.data?.authenticated) return;
    initialConnection.current = true;
    const job = jobs.find(item => item.status === "running");
    if (job) select(job.id);
  }, [history.updatedAt, session.data?.authenticated, jobs]);
  useEffect(() => {
    if (!selected || !visible || !session.data?.authenticated) return;
    setStreamState("Connecting"); setStreamError("");
    const stream = new EventSource(`/api/deploy/stream?jobId=${encodeURIComponent(selected)}&cursor=${cursor.current}`);
    let terminal = false;
    eventSource.current = stream;
    stream.onopen = () => { if (eventSource.current === stream && !terminal) setStreamState("Connected; waiting for output"); };
    stream.onmessage = event => {
      if (eventSource.current !== stream) return;
      try {
        const data = JSON.parse(event.data);
        if (data.error) { terminal = true; setStreamError(data.error); setStreamState("Disconnected; inspect job status"); stream.close(); return; }
        if (data.reset) { cursor.current = 0; setLog({ output: "", truncated: false }); return; }
        if (!Number.isSafeInteger(data.cursor) || data.cursor < cursor.current) throw new Error("Invalid cursor");
        if (data.output && data.cursor > cursor.current) setLog(previous => {
          const tail = appendLogTail(previous.output, data.output);
          return { output: tail.output, truncated: previous.truncated || tail.truncated };
        });
        cursor.current = data.cursor;
        setStreamState(data.status === "running" ? "Streaming" : data.status);
        if (data.done) { terminal = true; stream.close(); refetchHistory(); }
      } catch { terminal = true; stream.close(); setStreamError("Invalid output stream; retry to inspect current status."); }
    };
    stream.onerror = () => {
      if (eventSource.current !== stream || terminal) return;
      stream.close(); setStreamError("Output stream disconnected. Job status is unknown; refresh or retry."); setStreamState("Disconnected");
    };
    return () => { stream.close(); if (eventSource.current === stream) eventSource.current = undefined; };
  }, [selected, retry, visible, session.data?.authenticated, refetchHistory]);

  async function loadOutput(job: Job) {
    if (saving) return;
    setSaving(true); setError("");
    pending.current?.abort(); const controller = new AbortController(); pending.current = controller;
    const deadline = setTimeout(() => controller.abort(), 20000);
    try {
      const data = await requestJson<{ output: string; cursor: number; truncated: boolean }>(`/api/deploy/history?jobId=${encodeURIComponent(job.id)}&tail=65536`, { signal: controller.signal });
      if (mounted.current && !controller.signal.aborted) select(job.id, data.output, data.cursor, data.truncated);
    } catch (failure) { if (mounted.current) setError(controller.signal.aborted ? "Output request interrupted. Retry when ready." : failure instanceof Error ? failure.message : "Output unavailable"); }
    finally { clearTimeout(deadline); if (mounted.current) setSaving(false); }
  }
  async function submit() {
    if (!action || saving || !session.canWrite || action.kind === "start" && !permitted) return;
    setSaving(true); setError(""); setNotice("");
    const controller = new AbortController(); pending.current = controller;
    const deadline = setTimeout(() => controller.abort(), 20000);
    try {
      if (action.kind === "start") {
        const result = await requestJson<{ jobId: string }>("/api/deploy/start", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ playbook: "site.yml", roles: action.role ? [action.role] : [] }), signal: controller.signal });
        if (mounted.current) select(result.jobId);
      } else {
        await requestJson(`/api/deploy/${action.kind === "stop" ? "stop" : "history"}?jobId=${encodeURIComponent(action.job!.id)}`,
          { method: action.kind === "stop" ? "POST" : "DELETE", signal: controller.signal });
        if (mounted.current && action.kind === "stop") setNotice("Cancellation requested. Inspect job status until the process finishes.");
        if (mounted.current && action.kind === "delete" && selected === action.job!.id) { setSelected(undefined); setLog({ output: "", truncated: false }); }
      }
      if (mounted.current) { setAction(undefined); history.refetch(); }
    } catch (failure) { if (mounted.current) setError(controller.signal.aborted ? "Request interrupted; refresh job status before retrying." : failure instanceof Error ? failure.message : "Job operation failed"); }
    finally { clearTimeout(deadline); if (mounted.current) setSaving(false); }
  }
  return <ViewportWrapper><main className="min-w-0 space-y-5 px-3 py-6 sm:px-4 lg:px-6">
    <h1 className="text-2xl font-semibold">Provisioning</h1>
    <p className="text-sm text-zinc-400">Bootstrap credentials and playbooks belong to the independent operator environment. Native Secrets are imported independently.</p>
    {!session.loading && !session.data?.capabilities?.provisioning && <p role="status" className="rounded border border-amber-800 p-3 text-amber-200">Provisioning is disabled in this runtime. Run it from the independent operator environment.</p>}
    {error && <p role="alert" className="text-red-300">{error}</p>}{notice && <p role="status" className="text-amber-200">{notice}</p>}
    {permitted && <div className="flex flex-wrap items-end gap-3"><label className="text-sm">Role<select value={role} onChange={event => setRole(event.target.value)} disabled={saving || running} className="mt-1 block rounded border border-zinc-700 bg-zinc-900 p-2">
      <option value="">Full site.yml</option>{ROLES.map(item => <option key={item}>{item}</option>)}</select></label>
      <button disabled={saving || running} onClick={() => setAction({ kind: "start", role })} className="rounded bg-indigo-600 px-3 py-2 disabled:opacity-50">Run provisioning</button></div>}
    <section aria-label="Job output" className="rounded border border-zinc-800 bg-zinc-900 p-3">
      <div className="mb-3 flex flex-wrap items-center gap-3"><h2 className="font-semibold">Output · {visible ? streamState : "Paused while page is hidden"}</h2>
        <button onClick={() => setLog({ output: "", truncated: false })} className="rounded bg-zinc-800 px-3 py-1">Clear output</button>
        {selected && streamError && <button onClick={() => setRetry(value => value + 1)} className="underline">Retry output</button>}</div>
      {streamError && <p role="status" className="mb-2 text-amber-200">{streamError}</p>}
      {log.truncated && <p className="mb-2 text-sm text-zinc-400">Showing the latest 65,536 characters. Older captured output remains in job history.</p>}
      <pre tabIndex={0} aria-label="Captured job output" className="max-h-[50dvh] min-h-32 overflow-auto whitespace-pre-wrap break-all rounded bg-black p-3 font-mono text-sm">{log.output || "Select View output to load a job's captured output."}</pre>
    </section>
    <section><h2 className="mb-3 text-lg font-semibold">Job history · latest 50</h2>
      {history.error && <p role="status" className="mb-3 text-amber-200">{history.error}. Retained metadata may be stale.<button onClick={history.refetch} className="ml-3 underline">Retry history</button></p>}
      {history.loading ? <p role="status">Loading job metadata…</p> : !history.data ? <p>Job metadata unavailable.</p> : <ResourceTable rows={jobs} resetKey=""
        columns={[{ key: "playbook", label: "Playbook" }, { key: "status", label: "Status" }, { key: "startedAt", label: "Started", sort: "date" }, { key: "finishedAt", label: "Finished", sort: "date" }]}
        renderActions={row => <div className="flex gap-3"><button disabled={saving} aria-label={`View output for ${row.id}`} onClick={() => { void loadOutput(row as Job); }} className="underline">View output</button>
          {permitted && row.status === "running" && <button disabled={saving} aria-label={`Stop job ${row.id}`} onClick={() => setAction({ kind: "stop", job: row as Job })} className="text-red-300 underline">Stop</button>}
          {session.canWrite && row.status !== "running" && <button disabled={saving} aria-label={`Delete job ${row.id}`} onClick={() => setAction({ kind: "delete", job: row as Job })} className="text-red-300 underline">Delete</button>}</div>} />}
    </section>
    {action && session.canWrite && <ConfirmDialog open title={action.kind === "start" ? "Run provisioning" : action.kind === "stop" ? "Request job cancellation" : "Delete job history"}
      message={action.kind === "start" ? `Run site.yml ${action.role ? "role " + action.role : "with all roles"} using the operator's configured inventory and credentials?` : action.kind === "stop" ? "Request cancellation in this process. Inspect job state for completion and partial effects." : "Permanently remove this completed job's captured output and metadata?"}
      confirmLabel={action.kind === "start" ? "Run" : action.kind === "stop" ? "Request cancellation" : "Delete"} confirmName={action.kind === "delete" ? action.job!.id : undefined}
      loading={saving} error={error} danger onClose={() => { if (!saving) setAction(undefined); }} onConfirm={() => { void submit(); }} />}
  </main></ViewportWrapper>;
}
