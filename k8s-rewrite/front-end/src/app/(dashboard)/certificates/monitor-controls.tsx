"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import type { CertificateControls, MonitoringPolicy, MonitorView } from "@/lib/certificate-control";

const input = "mt-1 block w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-50";
const date = (value: string | null | undefined) => value ? new Date(value).toLocaleString() : "Unknown";
const deliveryLabel = (state: MonitorView["notificationDelivery"] | undefined) =>
  state === "delivered" ? "delivery confirmed by the sender"
  : state === "pending-delivery" ? "delivery pending"
  : state === "no-delivery-yet" ? "no delivery confirmed yet"
  : "no sender configured";
const deliveryTone = (state: MonitorView["notificationDelivery"] | undefined) =>
  state === "delivered" ? "text-emerald-200" : state === "pending-delivery" ? "text-amber-200" : "text-zinc-400";

export default function MonitorControls({ controls, canManage, refresh }: {
  controls: CertificateControls; canManage: boolean; refresh: () => Promise<void>;
}) {
  const policy = controls.policy;
  const [draft, setDraft] = useState<MonitoringPolicy | null>(policy?.desired ?? null);
  const [saving, setSaving] = useState(false), [message, setMessage] = useState(""), [error, setError] = useState("");
  const seenPolicy = useRef(policy);
  useEffect(() => {
    const previous = seenPolicy.current;
    seenPolicy.current = policy;
    // Heartbeats refresh the response object, not the operator's unsaved edit.
    if (previous?.uid === policy?.uid && previous?.revision === policy?.revision) return;
    setDraft(policy?.desired ?? null);
  }, [policy]);
  const monitor = controls.monitor;
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!policy || !draft || saving || !canManage) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const response = await fetch("/api/certificates/policy", {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(15000),
        body: JSON.stringify({ uid: policy.uid, revision: policy.revision, policy: draft }),
      });
      const result = await response.json();
      if (!response.ok) throw Error(typeof result.error === "string" ? result.error : "Policy save could not be verified.");
      setMessage("Monitoring policy saved. Check runner acknowledgement below before relying on the change.");
      await refresh();
    } catch (failure) {
      setError(failure instanceof Error && failure.name !== "TimeoutError" && failure.name !== "AbortError" ?
        failure.message : "Policy outcome unknown. Refresh before retrying; do not repeat an unverified save.");
      await refresh();
    } finally { setSaving(false); }
  }
  return <section aria-labelledby="monitor-heading" className="min-w-0 space-y-4 rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 [overflow-wrap:anywhere]">
    <div><h2 id="monitor-heading" className="text-lg font-medium">Independent monitoring</h2>
      <p className="mt-2 text-sm text-zinc-300"><span className="font-medium capitalize">{controls.state}</span> — {controls.message}</p>
      <p className="mt-2 text-sm text-zinc-400">This policy controls metadata monitoring only. It cannot approve CSRs, renew certificates or retire resources.</p></div>
    <dl className="grid gap-3 text-sm sm:grid-cols-3">
      <div><dt className="text-zinc-400">Runner heartbeat</dt><dd className="mt-1">{date(monitor?.heartbeatAt)}</dd></div>
      <div><dt className="text-zinc-400">Acknowledged policy revision</dt><dd className="mt-1 break-all">{monitor?.policyRevision ?? "None"}</dd></div>
      <div><dt className="text-zinc-400">Notifications awaiting delivery</dt><dd className="mt-1">{monitor?.notificationsPending ?? "Unknown"} <span className={deliveryTone(monitor?.notificationDelivery)}>· {deliveryLabel(monitor?.notificationDelivery)}</span></dd></div>
    </dl>
    {policy && draft ? <form onSubmit={event => void save(event)} className="space-y-3 border-t border-zinc-800 pt-4">
      <p className="text-xs text-zinc-400">Requested policy revision {policy.revision}. Changes use compare-and-swap; stale edits are refused.</p>
      <fieldset disabled={!canManage || saving} className="grid gap-4 sm:grid-cols-3">
        <legend className="sr-only">Requested monitoring policy</legend>
        <label className="text-sm text-zinc-300">Monitoring mode<select className={input} value={draft.mode} onChange={event => setDraft({ ...draft, mode: event.target.value as MonitoringPolicy["mode"] })}>
          <option value="paused">Paused</option><option value="monitor">Monitor</option></select></label>
        <label className="text-sm text-zinc-300">Scan interval (seconds)<input type="number" min={60} max={900} step={1} required className={input} value={draft.scanIntervalSeconds}
          onChange={event => setDraft({ ...draft, scanIntervalSeconds: Number(event.target.value) })} /></label>
        <label className="text-sm text-zinc-300">Cert-manager expiry warning (days)<input type="number" min={1} max={30} step={1} required className={input} value={draft.expiryWarningDays}
          onChange={event => setDraft({ ...draft, expiryWarningDays: Number(event.target.value) })} /></label>
      </fieldset>
      {canManage ? <button disabled={saving} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-300 disabled:opacity-50">{saving ? "Saving…" : "Save monitoring policy"}</button> :
        <p className="text-sm text-zinc-400">Read-only policy. An infrastructure operator can change monitoring.</p>}
    </form> : <p className="text-sm text-amber-200">Policy controls are unavailable until the fixed control ConfigMaps and scoped permissions are provisioned.</p>}
    <p role="status" aria-live="polite" aria-atomic="true" className="text-sm text-emerald-200">{message}</p>
    {error && <p role="alert" className="text-sm text-red-200">{error}</p>}
    {monitor && <>
      <div className="space-y-2 text-sm">
        <h3 className="font-medium">Durable run status</h3>
        <p className="text-zinc-400">{monitor.lastRun ? `${monitor.lastRun.state} · started ${date(monitor.lastRun.startedAt)} · finished ${date(monitor.lastRun.finishedAt)}` : "No monitoring run has completed."}</p>
        {monitor.sources.map(source => <p key={source.resource} className={!source.available || source.stale ? "text-amber-200" : "text-zinc-400"}>
          {source.resource}: {!source.available ? "unavailable" : source.stale ? "stale" : "available"} · checked {date(source.checkedAt)}
        </p>)}
      </div>
      <details className="border-t border-zinc-800 pt-3"><summary className="cursor-pointer text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400">Durable observations ({monitor.observations.length})</summary>
        <p className="mt-2 text-xs text-zinc-400">Historical metadata from the independent runner, not proof of endpoint verification. Check source availability and observation age above.</p>
        <ul className="mt-3 max-h-80 divide-y divide-zinc-800 overflow-auto text-sm">{monitor.observations.map(row =>
          <li key={`${row.resource}/${row.uid}`} className="py-3"><p className="break-all">{row.namespace ? `${row.namespace}/` : ""}{row.name} · {row.state}</p><p className="mt-1 text-xs text-zinc-400">{row.resource} · observed {date(row.observedAt)}{row.notAfter ? ` · expires ${date(row.notAfter)}` : ""}</p></li>)}</ul>
      </details>
    </>}
    {!!policy?.audit.length && <details className="border-t border-zinc-800 pt-3"><summary className="cursor-pointer text-sm font-medium">Policy history (last {policy.audit.length} changes)</summary>
      <ol className="mt-3 space-y-3 text-xs text-zinc-400">{[...policy.audit].reverse().map((entry, index) =>
        <li key={`${entry.at}/${index}`} className="break-words">{date(entry.at)} · operator {entry.actor} · {entry.policy.mode}, every {entry.policy.scanIntervalSeconds}s, warning {entry.policy.expiryWarningDays} days · previous revision {entry.previousRevision}</li>)}</ol>
    </details>}
  </section>;
}
