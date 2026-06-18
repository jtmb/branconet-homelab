"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  GitBranch,
  Loader2,
  Layers,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  Clock,
  Tag,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import ViewportWrapper from "../../viewport-wrapper";
import type { GitRepoDetail, BundleSummary } from "@/lib/flux";

function shortRev(rev: string | null): string {
  if (!rev) return "—";
  const parts = rev.split(":");
  return parts[parts.length - 1]?.slice(0, 8) || rev.slice(0, 8);
}

function fmtTime(ts: string | null): string {
  if (!ts) return "—";
  try { return new Date(ts).toLocaleString(); } catch { return ts; }
}

export default function GitRepoDetailPage() {
  const router = useRouter();
  const params = useParams<{ repoName: string }>();
  const repoName = decodeURIComponent(params.repoName);

  const [detail, setDetail] = useState<GitRepoDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [showAnnotations, setShowAnnotations] = useState(false);

  const fetchDetail = useCallback(async () => {
    try {
      const res = await fetch(`/api/flux/repos/${encodeURIComponent(repoName)}/detail`);
      if (res.status === 404) { setNotFound(true); setLoading(false); return; }
      const data = await res.json();
      setDetail(data);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [repoName]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (notFound || !detail) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <GitBranch className="w-12 h-12 text-zinc-600" />
        <h2 className="text-lg font-semibold text-zinc-300">Repository Not Found</h2>
        <p className="text-sm text-zinc-500">{repoName}</p>
        <Link href="/flux" className="text-indigo-400 hover:underline text-sm">← Back to Flux</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-0">
      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-4 text-xs text-zinc-500">
          <Link href="/flux" className="hover:text-zinc-300 transition-colors">Flux</Link>
          <ChevronRight className="w-3 h-3" />
          <span className="text-zinc-300">{repoName}</span>
        </div>

        {/* Header */}
        <div className="flex items-center gap-3 mb-2 flex-wrap">
          <GitBranch className="page-header-icon text-emerald-400" />
          <h1 className="page-header-title">{repoName}</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            detail.ready ? "badge-success" : "badge-warning"
          }`}>{detail.ready ? "Active" : "Not Ready"}</span>
          {detail.suspended && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-500/10 text-zinc-400 border border-zinc-500/20">Suspended</span>
          )}
        </div>

        {/* Meta line */}
        <div className="flex items-center gap-4 text-xs text-zinc-500 mb-6 flex-wrap">
          <span>Namespace: <span className="text-zinc-300 font-mono">{detail.namespace}</span></span>
          <span>Age: <span className="text-zinc-300">{detail.age || "—"}</span></span>
          <a href={detail.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300 transition-colors font-mono truncate max-w-[400px]">
            {detail.url} <ExternalLink className="w-3 h-3 shrink-0" />
          </a>
          <span>Branch: <span className="text-zinc-300 font-mono">{detail.branch}</span></span>
          {detail.path !== "./" && (
            <span>Path: <span className="text-zinc-300 font-mono">{detail.path}</span></span>
          )}
        </div>

        {/* Labels */}
        {detail.labels.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {detail.labels.filter(l => !l.key.startsWith("kustomize.toolkit.fluxcd.io")).map((l) => (
              <span key={l.key} className="text-[10px] px-1.5 py-0.5 rounded-md bg-zinc-800/80 text-zinc-400 font-mono ring-1 ring-zinc-700/40">
                {l.key}={l.value}
              </span>
            ))}
          </div>
        )}

        {/* Annotations (collapsible) */}
        {detail.annotations.length > 0 && (
          <div className="mb-6">
            <button
              onClick={() => setShowAnnotations(!showAnnotations)}
              className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors flex items-center gap-1"
            >
              {showAnnotations ? "Hide" : "Show"} {detail.annotations.length} annotation{detail.annotations.length !== 1 ? "s" : ""}
            </button>
            {showAnnotations && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {detail.annotations.map((a) => (
                  <span key={a.key} className="text-[10px] px-1.5 py-0.5 rounded-md bg-zinc-800/80 text-zinc-500 font-mono ring-1 ring-zinc-700/40 truncate max-w-[400px]" title={`${a.key}=${a.value}`}>
                    {a.key}={a.value}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Summary cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
          <div className="glass-card rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              <h3 className="text-sm font-semibold text-zinc-200">Bundles</h3>
            </div>
            <p className="text-2xl font-bold text-zinc-100">
              {detail.bundles.filter(b => b.ready).length}<span className="text-base font-normal text-zinc-500"> / {detail.bundles.length}</span>
            </p>
            <p className="text-xs text-zinc-500 mt-0.5">Bundles ready</p>
          </div>
          <div className="glass-card rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Tag className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-semibold text-zinc-200">Resources</h3>
            </div>
            <p className="text-2xl font-bold text-zinc-100">
              {detail.readyResources}<span className="text-base font-normal text-zinc-500"> / {detail.totalResources}</span>
            </p>
            <p className="text-xs text-zinc-500 mt-0.5">Resources ready</p>
          </div>
        </div>

        {/* Bundles table */}
        <section className="glass-card rounded-xl overflow-hidden mb-6">
          <div className="px-4 py-3 border-b border-zinc-700/40">
            <h2 className="text-sm font-semibold text-zinc-200">
              Bundles {detail.bundles.length > 0 && `(${detail.bundles.length})`}
            </h2>
          </div>
          {detail.bundles.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-zinc-500">No bundles</div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 w-8">State</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Name</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 hidden sm:table-cell">Deployments</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 hidden sm:table-cell">Last Updated</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500 hidden md:table-cell">Date</th>
                </tr>
              </thead>
              <tbody>
                {detail.bundles.map((bundle) => (
                  <tr
                    key={bundle.name}
                    onClick={() => router.push(`/flux/${encodeURIComponent(repoName)}/${encodeURIComponent(bundle.name)}`)}
                    className="border-b border-zinc-800/40 hover:bg-zinc-800/30 transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-3">
                      {bundle.ready
                        ? <CheckCircle2 className="w-4 h-4 text-emerald-400" title="Ready" />
                        : <AlertTriangle className="w-4 h-4 text-red-400" title={bundle.status} />
                      }
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm font-medium text-zinc-200 hover:text-indigo-400 transition-colors">{bundle.name}</span>
                      <div className="text-[10px] font-mono text-zinc-600 truncate hidden sm:hidden mt-0.5">{bundle.path}</div>
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell">
                      <span className="text-sm text-zinc-400">
                        {bundle.totalResources} resource{bundle.totalResources !== 1 ? "s" : ""}
                      </span>
                      {bundle.resourceCounts.length > 0 && (
                        <div className="text-[10px] text-zinc-600 mt-0.5">
                          {bundle.resourceCounts.slice(0, 3).map(r => `${r.count} ${r.kind}`).join(", ")}
                          {bundle.resourceCounts.length > 3 && ` +${bundle.resourceCounts.length - 3} more`}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell text-sm text-zinc-400">
                      {bundle.lastSync ? new Date(bundle.lastSync).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-sm text-zinc-500">
                      {fmtTime(bundle.lastSync)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {/* Conditions */}
        <section className="glass-card rounded-xl overflow-hidden mb-6">
          <div className="px-4 py-3 border-b border-zinc-700/40">
            <h2 className="text-sm font-semibold text-zinc-200">
              Conditions {detail.conditions.length > 0 && `(${detail.conditions.length})`}
            </h2>
          </div>
          {detail.conditions.length === 0 ? (
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
                {detail.conditions.map((c) => (
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

        {/* Recent Events */}
        <section className="glass-card rounded-xl overflow-hidden mb-6">
          <div className="px-4 py-3 border-b border-zinc-700/40">
            <h2 className="text-sm font-semibold text-zinc-200">
              Recent Events {detail.events.length > 0 && `(${detail.events.length})`}
            </h2>
          </div>
          {detail.events.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-zinc-500">No recent events</div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/40">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Type</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Reason</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Message</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-zinc-500">Age</th>
                </tr>
              </thead>
              <tbody>
                {detail.events.map((ev, i) => (
                  <tr key={i} className="border-b border-zinc-800/40">
                    <td className="px-4 py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        ev.type === "Warning" ? "bg-amber-500/10 text-amber-400" : "bg-emerald-500/10 text-emerald-400"
                      }`}>{ev.type}</span>
                    </td>
                    <td className="px-4 py-2.5 text-sm text-zinc-400">{ev.reason}</td>
                    <td className="px-4 py-2.5 text-sm text-zinc-500 max-w-md truncate">{ev.message}</td>
                    <td className="px-4 py-2.5 text-sm text-zinc-500">{ev.age}</td>
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
