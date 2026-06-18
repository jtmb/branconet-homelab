"use client";

import {
  GitBranch,
  RefreshCw,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { FluxTreeNode } from "@/lib/flux";
import Link from "next/link";

interface FluxTreeRowProps {
  node: FluxTreeNode;
  onSync?: (id: string, name: string) => void;
  onDelete?: (id: string, name: string) => void;
  syncingId?: string | null;
  deletingId?: string | null;
}

export default function FluxTreeRow({
  node,
  onSync,
  onDelete,
  syncingId,
  deletingId,
}: FluxTreeRowProps) {

  function statusDot() {
    if (node.ready) {
      return <CheckCircle2 className="w-4 h-4 text-emerald-400" title="Ready" />;
    }
    const lower = node.status.toLowerCase();
    if (lower.includes("error") || lower.includes("fail") || lower.includes("invalid")) {
      return <AlertTriangle className="w-4 h-4 text-red-400" title={node.status} />;
    }
    return <Loader2 className="w-4 h-4 text-amber-400 animate-spin" title={node.status || "Reconciling"} />;
  }

  function formatTime(ts: string | null) {
    if (!ts) return "—";
    try {
      const d = new Date(ts);
      if (isNaN(d.getTime())) return ts;
      return d.toLocaleString();
    } catch {
      return ts;
    }
  }

  function shortRevision(rev: string | null) {
    if (!rev) return null;
    const parts = rev.split(":");
    const hash = parts[parts.length - 1] || rev;
    return hash.slice(0, 8);
  }

  return (
    <Link
      href={`/flux/${encodeURIComponent(node.name)}`}
      className="group flex items-center gap-2 py-2.5 px-3 rounded-lg hover:bg-zinc-800/30 transition-colors whitespace-nowrap cursor-pointer"
    >
      {/* Kind icon */}
      <GitBranch className="w-4 h-4 text-emerald-400 flex-shrink-0" />

      {/* Name + info */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-zinc-200 truncate group-hover:text-indigo-400 transition-colors">
            {node.name}
          </span>
          <span className="text-[10px] px-1.5 py-px rounded border font-medium bg-emerald-500/10 text-emerald-400 border-emerald-500/20 flex-shrink-0">
            GitRepository
          </span>
        </div>
        {node.url && (
          <div className="flex items-center gap-2 text-[11px] text-zinc-500 mt-0.5 min-w-0">
            <span className="truncate max-w-[300px]">{node.url}</span>
            {node.branch && node.branch !== "main" && (
              <>
                <span className="flex-shrink-0">·</span>
                <span className="font-mono flex-shrink-0">{node.branch}</span>
              </>
            )}
            {node.path && (
              <>
                <span className="flex-shrink-0">·</span>
                <span className="font-mono flex-shrink-0">{node.path}</span>
              </>
            )}
          </div>
        )}
      </div>

      {/* Status + revision */}
      <div className="flex items-center gap-4 flex-shrink-0">
        <span className="w-4 flex items-center justify-center flex-shrink-0">{statusDot()}</span>
        <span className="text-[10px] text-zinc-600 w-12 text-right hidden sm:inline flex-shrink-0 truncate">
          {shortRevision(node.revision) || "—"}
        </span>
        <span className="text-[10px] text-zinc-600 w-28 text-right hidden md:inline flex-shrink-0 truncate">
          {formatTime(node.lastSync)}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onSync?.(node.id, node.name); }}
          disabled={syncingId === node.id}
          className="p-1 rounded hover:bg-indigo-500/10 text-zinc-500 hover:text-indigo-400 transition-colors disabled:opacity-50"
          title="Sync"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${syncingId === node.id ? "animate-spin" : ""}`} />
        </button>
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete?.(node.id, node.name); }}
          disabled={deletingId === node.id}
          className="p-1 rounded hover:bg-red-500/10 text-zinc-500 hover:text-red-400 transition-colors disabled:opacity-50"
          title="Delete"
        >
          {deletingId === node.id ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Trash2 className="w-3.5 h-3.5" />
          )}
        </button>
      </div>
    </Link>
  );
}
