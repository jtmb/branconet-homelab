"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ShieldCheck, RefreshCw, Search, X, ChevronDown, ChevronRight, ExternalLink, AlertTriangle, Layers, Container, Clock, ShieldAlert } from "lucide-react";
import { SEVERITIES, resultStale, safeAdvisoryURL, type ImageReport, type Severity, type SystemReport } from "@/lib/system-report-types";

const severityColors: Record<Severity, string> = { CRITICAL: "text-rose-300 bg-rose-500/10 border-rose-500/30", HIGH: "text-orange-300 bg-orange-500/10 border-orange-500/30", MEDIUM: "text-amber-300 bg-amber-500/10 border-amber-500/30", LOW: "text-sky-300 bg-sky-500/10 border-sky-500/30", UNKNOWN: "text-zinc-300 bg-zinc-800 border-zinc-700" };
const inputClass = "bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-violet-400";
function timestamp(value?: string | null) { return value ? new Date(value).toLocaleString() : "Unknown"; }
function imageStatus(image: ImageReport) { return resultStale(image) ? "stale" : image.state; }
function Badge({ severity }: { severity: Severity }) { return <span className={`inline-flex rounded border px-2 py-0.5 text-xs font-medium ${severityColors[severity]}`}>{severity}</span>; }

function ImageCard({ image, severity, fixable }: { image: ImageReport; severity: string; fixable: boolean }) {
  const [open, setOpen] = useState(false), [limit, setLimit] = useState(50);
  const status = imageStatus(image), complete = image.state === "complete";
  const findings = image.findings.filter(f => (severity === "all" || f.severity === severity) && (!fixable || f.fixed));
  const counts = Object.fromEntries(SEVERITIES.map(s => [s, image.findings.filter(f => f.severity === s).length]));
  return <article className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
    <button aria-expanded={open} onClick={() => setOpen(!open)} className="flex w-full items-start gap-3 p-4 text-left hover:bg-zinc-800/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-400">
      {open ? <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-zinc-400" /> : <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-zinc-400" />}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2"><span className="break-all font-mono text-sm text-zinc-100">{image.aliases[0]}</span><span className={`rounded-full border px-2 py-0.5 text-xs ${status === "complete" ? "border-emerald-500/30 text-emerald-300" : "border-amber-500/30 text-amber-300"}`}>{status === "complete" ? "Analyzed" : status}</span></div>
        <p className="mt-1 break-all font-mono text-xs text-zinc-500">{image.digest ?? "Runtime digest unavailable"}</p>
        <p className="mt-2 text-xs text-zinc-400">{image.consumers.length} running container{image.consumers.length === 1 ? "" : "s"} · {new Set(image.consumers.map(c => c.namespace)).size} namespace{new Set(image.consumers.map(c => c.namespace)).size === 1 ? "" : "s"}{complete ? ` · ${image.packageCount} package${image.packageCount === 1 ? "" : "s"} analyzed` : " · Coverage incomplete"}</p>
      </div>
      <div className="hidden sm:flex flex-wrap justify-end gap-2">{SEVERITIES.slice(0, 3).map(s => counts[s] > 0 && <span key={s} className={`rounded border px-2 py-1 text-xs ${severityColors[s]}`}>{counts[s]} {s.toLowerCase()}</span>)}{complete && !image.findings.length && <span className="text-sm text-zinc-300">No matches</span>}</div>
    </button>
    {open && <div className="border-t border-zinc-800 p-4 space-y-5">
      {image.message && <p role="status" className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-sm text-amber-200">{image.message}</p>}
      <div className="grid gap-3 text-xs text-zinc-400 sm:grid-cols-2 lg:grid-cols-4"><p>Scan time<br /><span className="text-zinc-200">{timestamp(image.scannedAt)}</span></p><p>Database updated<br /><span className="text-zinc-200">{timestamp(image.dbUpdatedAt)}</span></p><p>Database next update<br /><span className="text-zinc-200">{timestamp(image.dbNextUpdate)}</span></p><p>Scanner<br /><span className="text-zinc-200">Trivy {image.scannerVersion ?? "version not reported"}</span></p></div>
      {status === "stale" && <p className="text-sm text-amber-300">Scan or advisory database is stale. Prepare a current database and rescan before making update decisions.</p>}
      {image.endOfLife && <p className="text-sm text-amber-300">Scanner reports an end-of-life OS. Move to a maintained upstream image; package fixes may be unavailable.</p>}
      <div><h3 className="mb-2 text-sm font-medium text-zinc-200">Running consumers</h3><div className="max-h-56 overflow-auto rounded-lg border border-zinc-800"><table className="w-full min-w-[560px] text-left text-xs"><thead className="bg-zinc-900 text-zinc-400"><tr>{["Cluster / namespace", "Workload / Pod", "Container", "Services"].map(label => <th key={label} className="p-3 font-medium">{label}</th>)}</tr></thead><tbody>{image.consumers.map((c, i) => <tr key={i} className="border-t border-zinc-800 text-zinc-300"><td className="p-3">{c.cluster}<br />{c.namespace}</td><td className="p-3 break-all">{c.workload}<br /><span className="text-zinc-500">{c.pod}</span></td><td className="p-3">{c.container}<br /><span className="text-zinc-500">{c.kind}</span></td><td className="p-3">{c.services === null ? "Mapping unavailable" : c.services.join(", ") || "No selector match"}</td></tr>)}</tbody></table></div></div>
      {image.aliases.length > 1 && <p className="break-all text-xs text-zinc-400">Image aliases: {image.aliases.join(", ")}</p>}
      {complete && <div><h3 className="mb-2 text-sm font-medium text-zinc-200">Vulnerability matches <span className="text-zinc-500">({findings.length})</span></h3>
        {!findings.length ? <p className="text-sm text-zinc-400">{image.findings.length ? "No findings match these filters." : "No known vulnerability matches in the analyzed packages. This is not a guarantee of safety or complete package detection."}</p> : <div className="overflow-x-auto rounded-lg border border-zinc-800"><table className="w-full min-w-[640px] text-left text-sm"><thead className="bg-zinc-900 text-xs text-zinc-400"><tr>{["Severity / advisory", "Package / target", "Installed", "Fixed in"].map(label => <th key={label} className="p-3 font-medium">{label}</th>)}</tr></thead><tbody>{findings.slice(0, limit).map((f, i) => <tr key={i} className="border-t border-zinc-800 text-zinc-300"><td className="p-3"><Badge severity={f.severity} /><div className="mt-2">{safeAdvisoryURL(f.url) ? <a className="inline-flex items-center gap-1 text-violet-300 hover:underline" href={f.url!} target="_blank" rel="noopener noreferrer">{f.id}<ExternalLink className="h-3 w-3" /></a> : f.id}</div><p className="mt-1 max-w-md text-xs text-zinc-500">{f.title}</p></td><td className="p-3 font-mono text-xs break-all">{f.package}<br /><span className="text-zinc-500">{f.target}</span></td><td className="p-3 font-mono text-xs break-all">{f.installed}</td><td className="p-3 font-mono text-xs break-all">{f.fixed || <span className="font-sans text-amber-300">No fix reported</span>}</td></tr>)}</tbody></table></div>}
        {findings.length > limit && <button onClick={() => setLimit(limit + 50)} className="mt-3 text-sm text-violet-300 hover:underline">Show next 50 matches ({findings.length - limit} remaining)</button>}
      </div>}
      <p className="rounded-lg bg-violet-500/5 border border-violet-500/20 p-3 text-xs leading-relaxed text-zinc-300">Review the advisory and upstream release notes. For third-party images, update the maintained upstream version or digest in the authoritative deployment repository. A package fix does not prove an upstream image contains it. Rebuild owned images through their maintained source repository, then rescan. BORTUS does not patch workloads or rebuild images.</p>
    </div>}
  </article>;
}

export default function SystemReportScreen({ canScan }: { canScan: boolean }) {
  const [report, setReport] = useState<SystemReport | null>(null), [error, setError] = useState("");
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(""), [namespace, setNamespace] = useState("all"), [severity, setSeverity] = useState("all"), [status, setStatus] = useState("all"), [fixable, setFixable] = useState(false), [limit, setLimit] = useState(25);
  const generation = useRef(0), request = useRef<AbortController | null>(null), mounted = useRef(true);
  const invalidate = useCallback(() => { generation.current++; request.current?.abort(); }, []);
  const refresh = useCallback(async () => {
    const version = ++generation.current;
    request.current?.abort(); const controller = new AbortController(); request.current = controller;
    try {
      const response = await fetch("/api/system-report", { signal: controller.signal, cache: "no-store" });
      if (!response.ok) throw Error(response.status === 401 ? "Your session expired. Sign in again to view the report." : "System report unavailable. Refresh to retry.");
      const next: SystemReport = await response.json();
      if (mounted.current && generation.current === version) { setReport(next); setError(""); }
    } catch (e) { if (!controller.signal.aborted && mounted.current && generation.current === version) setError(e instanceof Error ? e.message : "Report unavailable"); }
    finally { if (mounted.current && generation.current === version) setLoading(false); }
  }, []);
  useEffect(() => {
    mounted.current = true; void refresh();
    return () => { mounted.current = false; invalidate(); };
  }, [refresh, invalidate]);
  const running = report?.job?.state === "running";
  useEffect(() => { if (busy) return; const timer = setInterval(() => void refresh(), running ? 2000 : 30000); return () => clearInterval(timer); }, [refresh, running, busy]);
  async function action(cancel: boolean) {
    setBusy(true); request.current?.abort(); generation.current++;
    const controller = new AbortController(); request.current = controller;
    try {
      const response = await fetch(`/api/system-report${cancel ? `?jobId=${encodeURIComponent(report!.job!.id)}` : ""}`, { method: cancel ? "DELETE" : "POST", signal: controller.signal });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || "Scan request failed");
      if (mounted.current) await refresh();
    } catch (e) { if (!controller.signal.aborted && mounted.current) setError(e instanceof Error ? e.message : "Scan request failed"); }
    finally { if (mounted.current) setBusy(false); }
  }
  const images = report?.images ?? [], analyzed = images.filter(image => image.state === "complete"), fresh = analyzed.filter(image => !resultStale(image));
  const namespaces = [...new Set(images.flatMap(image => image.consumers.map(c => c.namespace)))].sort();
  const filtered = images.filter(image => {
    const needle = search.toLowerCase();
    return (namespace === "all" || image.consumers.some(c => c.namespace === namespace)) && (status === "all" || imageStatus(image) === status) &&
      (severity === "all" || image.findings.some(f => f.severity === severity && (!fixable || f.fixed))) && (!fixable || image.findings.some(f => f.fixed && (severity === "all" || f.severity === severity))) &&
      (!needle || [...image.aliases, image.digest ?? "", ...image.consumers.flatMap(c => [c.workload, c.pod, c.namespace, ...(c.services ?? [])]), ...image.findings.flatMap(f => [f.id, f.package])].some(value => value.toLowerCase().includes(needle)));
  });
  const severityCounts = Object.fromEntries(SEVERITIES.map(s => [s, analyzed.reduce((sum, image) => sum + image.findings.filter(f => f.severity === s).length, 0)]));
  const clearFilters = () => { setSearch(""); setNamespace("all"); setSeverity("all"); setStatus("all"); setFixable(false); setLimit(25); };
  return <main className="mx-auto max-w-[1600px] p-4 md:p-6 lg:p-8 text-zinc-100">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="mb-2 text-xs font-medium uppercase tracking-widest text-violet-300">Cluster intelligence</p><h1 className="flex items-center gap-3 text-2xl font-semibold tracking-tight"><ShieldCheck className="h-7 w-7 text-violet-400" />System Report</h1><p className="mt-2 max-w-2xl text-sm text-zinc-400">Know what is running. Review known vulnerabilities. Plan upstream updates.</p></div><div className="flex items-center gap-2"><button disabled={busy} onClick={() => void refresh()} className="flex items-center gap-2 rounded-lg border border-zinc-700 px-3 py-2 text-sm hover:bg-zinc-800 disabled:opacity-50"><RefreshCw className="h-4 w-4" />Refresh</button>{canScan && <button disabled={busy || (!running && (!report?.scanner.configured || !report.available || report.stale))} onClick={() => void action(!!running)} className="flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50">{running ? <X className="h-4 w-4" /> : <ShieldAlert className="h-4 w-4" />}{busy ? "Working…" : running ? "Cancel scan" : "Scan images"}</button>}</div></div>
    <p className="mt-5 rounded-xl border border-violet-500/20 bg-violet-500/5 px-4 py-3 text-sm leading-relaxed text-zinc-300">Vulnerability matches identify affected software; they do not demonstrate exploitability. Unscanned images and unanalyzed packages have unknown risk.</p>
    {error && <div role="alert" className="mt-4 flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200"><AlertTriangle className="h-4 w-4 shrink-0" />{error}{report && " Previously loaded results may be out of date."}</div>}
    {loading && !report && <div role="status" className="mt-6 rounded-xl border border-zinc-800 p-8 text-zinc-400">Loading workload inventory and scan coverage…</div>}
    {report && <>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[
        { label: "Image coverage", value: report.available ? `${fresh.length} / ${images.length}` : "Unknown", detail: "Fresh analyzed / visible images", Icon: Layers },
        { label: "Running containers", value: report.available ? report.runningContainers : "Unknown", detail: report.available ? `${images.length} distinct image identities` : "Image identities unavailable", Icon: Container },
        { label: "Critical + high", value: analyzed.length ? severityCounts.CRITICAL + severityCounts.HIGH : "—", detail: "Matches across analyzed image digests", Icon: ShieldAlert },
        { label: "Needs attention", value: report.available ? images.length - fresh.length : "Unknown", detail: "Unscanned, stale, failed or unsupported", Icon: Clock },
      ].map(({ label, value, detail, Icon }) => <div key={label} className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4"><p className="flex items-center justify-between text-xs text-zinc-400">{label}<Icon className="h-4 w-4 text-violet-400" /></p><p className="mt-3 text-3xl font-semibold tabular-nums">{value}</p><p className="mt-2 text-xs text-zinc-500">{detail}</p></div>)}</div>
      <div className="mt-4 flex flex-wrap gap-2">{SEVERITIES.map(s => <button key={s} aria-pressed={severity === s} onClick={() => setSeverity(severity === s ? "all" : s)} className={`rounded-lg border px-3 py-2 text-xs ${severityColors[s]} ${severity === s ? "ring-2 ring-violet-400" : ""}`}>{s} <span className="ml-2 font-semibold">{severityCounts[s]}</span></button>)}</div>
      <div className="mt-5 space-y-2 text-xs text-zinc-400"><p>{report.scanner.message}</p><p>Connected cluster · Inventory sampled {timestamp(report.sampledAt)} · Scope: containers reported running in visible Pods, including running init and ephemeral containers. Kubernetes permissions define visibility.</p>{report.job && <p role="status">Scan {report.job.state === "complete" && images.some(image => imageStatus(image) !== "complete") ? "finished with coverage gaps" : report.job.state} · Started {timestamp(report.job.startedAt)}{report.job.finishedAt && ` · Finished ${timestamp(report.job.finishedAt)}`}{running && " · Images are scanned one at a time. Cancellation waits for process exit."}</p>}{!canScan && <p>Read-only report. An infrastructure operator can start or cancel scans.</p>}{report.warnings.map(warning => <p key={warning} className="text-amber-300">{warning}</p>)}</div>
      <section aria-label="Image security inventory" className="mt-6"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-base font-medium">Workload images <span className="ml-2 text-sm text-zinc-500">{filtered.length} of {images.length}</span></h2><button onClick={clearFilters} className="text-xs text-violet-300 hover:underline">Clear filters</button></div>
        <div className="my-4 flex flex-wrap gap-3"><label className="relative min-w-48 flex-1"><span className="sr-only">Search images, workloads, services or CVEs</span><Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" /><input value={search} onChange={e => setSearch(e.target.value)} className={`${inputClass} w-full pl-9`} placeholder="Search images, workloads, services, CVEs…" /></label><label><span className="sr-only">Namespace</span><select value={namespace} onChange={e => setNamespace(e.target.value)} className={inputClass}><option value="all">All namespaces</option>{namespaces.map(ns => <option key={ns}>{ns}</option>)}</select></label><label><span className="sr-only">Scan status</span><select value={status} onChange={e => setStatus(e.target.value)} className={inputClass}><option value="all">All scan states</option>{["complete", "stale", "unscanned", "queued", "scanning", "unsupported", "error", "cancelled"].map(state => <option key={state} value={state}>{state === "complete" ? "Analyzed" : state}</option>)}</select></label><label className="flex items-center gap-2 text-xs text-zinc-300"><input type="checkbox" checked={fixable} onChange={e => setFixable(e.target.checked)} className="accent-violet-500" />Fix version available</label></div>
        {!report.available ? <div className="rounded-xl border border-amber-500/30 p-8 text-sm text-amber-200">Workload inventory is unavailable. Coverage is unknown. Refresh after restoring the existing cluster read connection.</div> : !images.length ? <div className="rounded-xl border border-zinc-800 p-8 text-sm text-zinc-400">No running containers are visible in this inventory snapshot. This does not establish cluster-wide safety.</div> : !filtered.length ? <div className="rounded-xl border border-zinc-800 p-8 text-sm text-zinc-400">No images match these filters. Clear filters to see all coverage states.</div> : <div className="space-y-3">{filtered.slice(0, limit).map(image => <ImageCard key={image.key} image={image} severity={severity} fixable={fixable} />)}</div>}
        {filtered.length > limit && <button onClick={() => setLimit(limit + 25)} className="mt-4 text-sm text-violet-300 hover:underline">Show next 25 images</button>}
      </section>
    </>}
  </main>;
}
