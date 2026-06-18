"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Rocket, Loader2, ChevronRight } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import ViewportWrapper from "../../../viewport-wrapper";
import ResourceActionsMenu from "../../../resource-actions-menu";

function formatAge(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 365) return `${d}d`;
  return `${Math.floor(d / 365)}y`;
}

export default function DeploymentDetailPage() {
  const router = useRouter();
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const [deployment, setDeployment] = useState<any>(null);
  const [pods, setPods] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [editingDesired, setEditingDesired] = useState(false);
  const [desiredInput, setDesiredInput] = useState("");
  const [scalingDesired, setScalingDesired] = useState(false);

  const fetchDeployment = useCallback(async () => {
    try {
      const res = await fetch(`/api/cluster/deployments/${namespace}/${name}`);
      if (res.status === 404) { setNotFound(true); setLoading(false); return; }
      const data = await res.json();
      setDeployment(data.deployment);
      setPods(data.pods || []);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [namespace, name]);

  const doScaleDesired = useCallback(async (newReplicas: number) => {
    setScalingDesired(true);
    try {
      const res = await fetch(`/api/cluster/deployments/${namespace}/${name}/scale`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ replicas: newReplicas }),
      });
      if (res.ok) {
        await fetchDeployment();
        router.refresh();
      }
    } finally {
      setScalingDesired(false);
    }
  }, [namespace, name, fetchDeployment, router]);

  useEffect(() => { fetchDeployment(); }, [fetchDeployment]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (notFound || !deployment) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <Rocket className="w-12 h-12 text-zinc-600" />
        <h2 className="text-lg font-semibold text-zinc-300">Deployment Not Found</h2>
        <p className="text-sm text-zinc-500">{namespace}/{name}</p>
        <Link href="/deployments" className="text-indigo-400 hover:underline text-sm">← Back to Deployments</Link>
      </div>
    );
  }

  const created = deployment.metadata?.creationTimestamp;
  const ageMs = created ? Date.now() - new Date(created).getTime() : 0;
  const ns = deployment.metadata?.namespace || namespace;
  const desired = deployment.spec?.replicas ?? 0;
  const ready = deployment.status?.readyReplicas ?? 0;
  const available = deployment.status?.availableReplicas ?? 0;
  const updated = deployment.status?.updatedReplicas ?? 0;
  const strategy = deployment.spec?.strategy?.type || "RollingUpdate";
  const minReady = deployment.spec?.minReadySeconds ?? 0;
  const selector = deployment.spec?.selector?.matchLabels || {};

  const conditions = (deployment.status?.conditions || []).map((c: any) => ({
    type: c.type,
    status: c.status,
    reason: c.reason || "-",
    message: c.message || "-",
  }));

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-4 text-xs text-zinc-500">
          <Link href="/deployments" className="hover:text-zinc-300 transition-colors">Deployments</Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-zinc-300">{deployment.metadata?.name}</span>
        </div>
        <div className="flex items-center gap-3 mb-6">
          <Rocket className="page-header-icon text-amber-400" />
          <h1 className="page-header-title">{deployment.metadata?.name}</h1>
          <span className="text-xs px-2 py-0.5 rounded-full badge-success">{ready}/{desired} ready</span>
          <span className="text-xs text-zinc-500 bg-zinc-800/60 px-2 py-0.5 rounded-full">{ns}</span>
          <span className="text-xs text-zinc-500 ml-auto">{ageMs > 0 ? formatAge(ageMs) : "…"}</span>
          <ResourceActionsMenu resourceType="deployment" resource={deployment} onAction={fetchDeployment} />
        </div>

        {/* Summary */}
        <section className="glass-card p-4 rounded-xl mb-6">
        <h2 className="text-sm font-semibold text-zinc-200">Summary</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <p className="text-xs text-zinc-500 mb-0.5">Desired</p>
            {editingDesired ? (
              <input
                autoFocus
                type="number"
                min={0}
                className="w-20 text-sm font-medium bg-zinc-800 border border-indigo-500/50 rounded px-2 py-0.5 text-zinc-200 outline-none focus:border-indigo-400"
                value={desiredInput}
                onChange={(e) => setDesiredInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    const v = parseInt(desiredInput, 10);
                    if (!isNaN(v) && v >= 0 && v !== desired) {
                      doScaleDesired(v);
                    }
                    setEditingDesired(false);
                  }
                  if (e.key === "Escape") setEditingDesired(false);
                }}
                onBlur={() => {
                  const v = parseInt(desiredInput, 10);
                  if (!isNaN(v) && v >= 0 && v !== desired) {
                    doScaleDesired(v);
                  }
                  setEditingDesired(false);
                }}
              />
            ) : (
              <p
                className="text-sm font-medium text-zinc-200 cursor-pointer hover:text-indigo-400 transition-colors border border-transparent hover:border-indigo-500/30 rounded px-2 py-0.5 -mx-2"
                onClick={() => {
                  setDesiredInput(String(desired));
                  setEditingDesired(true);
                }}
                title="Click to edit desired replicas"
              >
                {scalingDesired ? (
                  <Loader2 className="w-3.5 h-3.5 inline animate-spin text-indigo-400 mr-1" />
                ) : null}
                {desired}
              </p>
            )}
          </div>
          <SummaryItem label="Ready" value={String(ready)} highlight={ready !== desired} />
          <SummaryItem label="Up-to-date" value={String(updated)} />
          <SummaryItem label="Available" value={String(available)} highlight={available !== desired} />
        </div>
        <div className="grid grid-cols-2 gap-3 pt-1 border-t border-zinc-700/40">
          <SummaryItem label="Strategy" value={strategy} />
          <SummaryItem label="Min Ready Seconds" value={`${minReady}s`} />
        </div>
        {Object.keys(selector).length > 0 && (
          <div>
            <p className="text-xs text-zinc-500 mb-1.5">Selector</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(selector).map(([k, v]) => (
                <span key={k} className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono">
                  {k}={v as string}
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

        {/* Pods */}
        <section className="glass-card rounded-xl overflow-hidden mb-6">
        <div className="px-4 py-3 border-b border-zinc-700/40">
          <h2 className="text-sm font-semibold text-zinc-200">
            Pods {pods.length > 0 && `(${pods.length})`}
          </h2>
        </div>
        {pods.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-zinc-500">No pods found for this deployment</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-700/40">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Name</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Status</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Node</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Age</th>
              </tr>
            </thead>
            <tbody>
              {pods.map((p: any) => {
                const pCreated = p.metadata?.creationTimestamp;
                const pAgeMs = pCreated ? Date.now() - new Date(pCreated).getTime() : 0;
                return (
                  <tr key={p.metadata?.uid || p.metadata?.name} className="border-b border-zinc-800/40 hover:bg-zinc-800/30 cursor-pointer" onClick={() => router.push(`/pods/${encodeURIComponent(ns)}/${encodeURIComponent(p.metadata?.name)}`)}>
                    <td className="px-4 py-2.5 text-sm text-zinc-200 font-mono">{p.metadata?.name}</td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        p.status?.phase === "Running" ? "badge-success" : p.status?.phase === "Pending" ? "badge-warning" : "badge-error"
                      }`}>{p.status?.phase || "Unknown"}</span>
                    </td>
                    <td className="px-4 py-2.5 text-sm text-zinc-500">{p.spec?.nodeName || "-"}</td>
                    <td className="px-4 py-2.5 text-sm text-zinc-500">{pAgeMs > 0 ? formatAge(pAgeMs) : "…"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

        {/* Conditions */}
        <section className="glass-card rounded-xl overflow-hidden mb-6">
        <div className="px-4 py-3 border-b border-zinc-700/40">
          <h2 className="text-sm font-semibold text-zinc-200">
            Conditions {conditions.length > 0 && `(${conditions.length})`}
          </h2>
        </div>
        {conditions.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-zinc-500">No conditions</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-700/40">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Type</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Status</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Reason</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Message</th>
              </tr>
            </thead>
            <tbody>
              {conditions.map((c: any) => (
                <tr key={c.type} className="border-b border-zinc-800/40">
                  <td className="px-4 py-2.5 text-sm text-zinc-200">{c.type}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      c.status === "True" ? "badge-success" : "badge-warning"
                    }`}>{c.status}</span>
                  </td>
                  <td className="px-4 py-2.5 text-sm text-zinc-400">{c.reason}</td>
                  <td className="px-4 py-2.5 text-sm text-zinc-500 max-w-xs truncate">{c.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        </section>
      </main>
      </ViewportWrapper>
    </div>
  );
}

function SummaryItem({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <p className="text-xs text-zinc-500 mb-0.5">{label}</p>
      <p className={`text-sm font-medium ${highlight ? "text-amber-400" : "text-zinc-200"}`}>{value}</p>
    </div>
  );
}
