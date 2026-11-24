"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import type { CertificateInventory, CertificateHealth } from "@/lib/certificate-inventory";
import type { CertificateControls } from "@/lib/certificate-control";
import MonitorControls from "./monitor-controls";

const date = (value: string | null) => value ? new Date(value).toLocaleString() : "Unknown";
const colors: Record<CertificateHealth, string> = {
  healthy: "text-emerald-300", renewing: "text-sky-300", warning: "text-amber-300",
  expired: "text-red-300", unknown: "text-zinc-400",
};
const button = "rounded-lg border border-zinc-700 px-3 py-2 text-sm hover:bg-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 disabled:opacity-50";

export default function CertificatesScreen({ canManage }: { canManage: boolean }) {
  const [report, setReport] = useState<(CertificateInventory & { controls: CertificateControls }) | null>(null);
  const [error, setError] = useState(""), [loading, setLoading] = useState(true), [search, setSearch] = useState("");
  const request = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setLoading(true);
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch("/api/certificates", { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw Error(response.status === 401 ? "Your session expired. Sign in again." : "Certificate inventory unavailable. Refresh to retry.");
      const next: CertificateInventory & { controls: CertificateControls } = await response.json();
      if (request.current === controller && !controller.signal.aborted) { setReport(next); setError(""); }
    } catch (failure) {
      if (request.current === controller) {
        // A superseding request or unmount clears the ref before aborting.
        setError(controller.signal.aborted ? "Certificate inventory timed out. Refresh to retry." :
          failure instanceof Error ? failure.message : "Certificate inventory unavailable.");
        setReport(null);
      }
    } finally {
      clearTimeout(timeout);
      if (request.current === controller) setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
    return () => { const active = request.current; request.current = null; active?.abort(); };
  }, [refresh]);
  useEffect(() => {
    const timer = setInterval(() => { if (document.visibilityState === "visible") void refresh(); }, 60000);
    const visible = () => { if (document.visibilityState === "visible") void refresh(); };
    document.addEventListener("visibilitychange", visible);
    return () => { clearInterval(timer); document.removeEventListener("visibilitychange", visible); };
  }, [refresh]);
  const needle = search.toLowerCase();
  const certificates = (report?.certificates ?? []).filter(row =>
    [row.name, row.namespace, row.issuer, ...row.names].some(value => value.toLowerCase().includes(needle)));
  const certsAvailable = report?.sources.find(source => source.resource === "certificates.cert-manager.io")?.available;
  const requestsAvailable = report?.sources.find(source => source.resource.startsWith("certificatesigningrequests."))?.available;

  return <main className="mx-auto max-w-[1600px] space-y-6 p-4 text-zinc-100 md:p-6 lg:p-8">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="text-xs uppercase tracking-widest text-indigo-300">Cluster trust</p>
        <h1 className="mt-2 flex items-center gap-3 text-2xl font-semibold"><ShieldCheck aria-hidden="true" className="h-7 w-7 text-indigo-400" />Certificates &amp; Trust</h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">Track certificate expiry, renewal ownership and pending requests without exposing private keys.</p></div>
      <button className={button} disabled={loading} onClick={() => void refresh()}><RefreshCw aria-hidden="true" className="mr-2 inline h-4 w-4" />{loading ? "Checking…" : "Refresh inventory"}</button>
    </header>
    <p role="status" aria-live="polite" aria-atomic="true" className="text-sm text-zinc-400">
      {loading ? "Checking visible certificate metadata…" : report ? `Inventory checked ${date(report.sampledAt)}. This is a point-in-time observation, not continuous monitoring.` : "No current inventory is available."}
    </p>
    {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-200">{error}</p>}
    {report && <>
      <MonitorControls controls={report.controls} canManage={canManage} refresh={refresh} />
      <section aria-label="Coverage gaps" className="space-y-2 text-sm text-amber-200">
        {report.warnings.map(warning => <p key={warning}>{warning}</p>)}
      </section>
      <section aria-labelledby="certificate-heading">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="certificate-heading" className="text-lg font-medium">Managed certificates</h2>
          <label className="text-sm text-zinc-400">Search certificates
            <input value={search} onChange={event => setSearch(event.target.value)} className="ml-2 max-w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-indigo-400" placeholder="Name, namespace, hostname…" /></label>
        </div>
        {!certsAvailable ? <p className="mt-4 text-sm text-amber-200">Certificate source unavailable. Restore resource access before assessing coverage.</p> :
          !certificates.length ? <p className="mt-4 text-sm text-zinc-400">{report.certificates.length ? "No certificates match your search." : "No cert-manager certificates are visible. This does not establish that the cluster has no certificates."}</p> :
          <div role="region" aria-label="Certificate metadata table" tabIndex={0} className="mt-4 overflow-x-auto rounded-lg border border-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"><table className="w-full min-w-[800px] text-left text-sm">
            <caption className="sr-only">Cert-manager metadata. Endpoint trust and installed certificates are not verified.</caption>
            <thead className="bg-zinc-900 text-zinc-400"><tr>{["Certificate", "Health", "Issuer / owner", "Expiry / renewal"].map(label => <th key={label} scope="col" className="p-3 font-medium">{label}</th>)}</tr></thead>
            <tbody>{certificates.map(row => <tr key={row.id} className="border-t border-zinc-800 align-top">
              <th scope="row" className="max-w-sm break-words p-3 font-normal"><p>{row.namespace}/{row.name}</p><p className="mt-1 text-xs text-zinc-400">{row.names.join(", ") || "No DNS names declared"}</p></th>
              <td className="max-w-xs p-3"><p className={colors[row.health]}>{row.health}</p><p className="mt-1 text-xs text-zinc-400">{row.message}</p></td>
              <td className="p-3">{row.issuer}<p className="mt-1 text-xs text-zinc-400">{row.renewalOwner}</p></td>
              <td className="p-3">{date(row.notAfter)}<p className="mt-1 text-xs text-zinc-400">Renewal: {date(row.renewalTime)}</p></td>
            </tr>)}</tbody>
          </table></div>}
      </section>
      <section aria-labelledby="request-heading">
        <h2 id="request-heading" className="text-lg font-medium">Certificate signing requests</h2>
        <p className="mt-2 text-sm text-zinc-400">Approval is not issuance. Issuance is not proof that a node installed or serves the certificate.</p>
        {!requestsAvailable ? <p className="mt-4 text-sm text-amber-200">Request source unavailable. Pending request coverage is unknown.</p> :
          !report.requests.length ? <p className="mt-4 text-sm text-zinc-400">No signing requests are visible in this snapshot.</p> :
          <ul className="mt-4 divide-y divide-zinc-800 rounded-lg border border-zinc-800">{report.requests.map(row =>
            <li key={row.id} className="p-4"><div className="flex flex-wrap justify-between gap-2"><h3 className="break-all text-sm font-medium">{row.name}</h3><span className="text-sm text-indigo-300">{row.state}</span></div>
              <p className="mt-2 break-all text-sm text-zinc-300">{row.requester} · {row.signer}</p>
              <p className="mt-1 text-xs text-zinc-400">Created {date(row.createdAt)}</p><p className="mt-2 text-sm text-zinc-400">{row.message}</p></li>)}</ul>}
      </section>
    </>}
  </main>;
}
