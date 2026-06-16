"use client";

import {
  ChevronRight,
  ChevronDown,
  GitBranch,
  Layers,
  Ship,
  Box,
  RefreshCw,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { FluxTreeNode } from "@/lib/flux";
import { useState } from "react";

interface FluxTreeRowProps {
  node: FluxTreeNode;
  depth: number;
  isLast: boolean;
  parentIsLast: boolean[];
  onSync?: (id: string, name: string) => void;
  onDelete?: (id: string, name: string) => void;
  syncingId?: string | null;
  deletingId?: string | null;
}

export default function FluxTreeRow({
  node,
  depth,
  isLast,
  parentIsLast,
  onSync,
  onDelete,
  syncingId,
  deletingId,
}: FluxTreeRowProps) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children.length > 0;

  function kindIcon() {
    switch (node.kind) {
      case "GitRepository":
        return <GitBranch className="w-4 h-4 text-emerald-400" />;
      case "Kustomization":
        return <Layers className="w-4 h-4 text-indigo-400" />;
      case "HelmRelease":
        return <Ship className="w-4 h-4 text-amber-400" />;
      case "Namespace":
        return <Box className="w-4 h-4 text-cyan-400" />;
      default:
        return <GitBranch className="w-4 h-4 text-zinc-400" />;
    }
  }

  function kindBadge() {
    const colors: Record<string, string> = {
      GitRepository: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
      Kustomization: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
      HelmRelease: "bg-amber-500/10 text-amber-400 border-amber-500/20",
      Namespace: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
    };
    return (
      <span
        className={`text-[10px] px-1.5 py-px rounded border font-medium ${colors[node.kind] || "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"}`}
      >
        {node.kind}
      </span>
    );
  }

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
      return new Date(ts).toLocaleString();
    } catch {
      return ts;
    }
  }

  function shortRevision(rev: string | null) {
    if (!rev) return null;
    // Flux revisions look like: "main@sha1:abc123def..." — show last segment short
    const parts = rev.split(":");
    const hash = parts[parts.length - 1] || rev;
    return hash.slice(0, 8);
  }

  const isRootGitRepo = node.kind === "GitRepository" && depth === 0;

  return (
    <div>
      {/* This row */}
      <div className="group flex items-center gap-2 py-2.5 px-3 rounded-lg hover:bg-zinc-800/30 transition-colors min-w-0">
        {/* Tree indent lines + expand chevron */}
        <div className="flex items-center flex-shrink-0" style={{ width: depth * 20 + (hasChildren ? 20 : 28) }}>
          {/* Ancestor tree lines */}
          {Array.from({ length: depth }).map((_, i) => (
            <div key={i} className="flex-shrink-0 w-5 flex justify-center">
              {!parentIsLast[i] && <div className="w-px h-full min-h-[28px] bg-zinc-700/50" />}
            </div>
          ))}

          {/* Current node tree line + expand chevron */}
          {hasChildren ? (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center justify-center w-5 h-5 rounded hover:bg-zinc-700/50 text-zinc-500 hover:text-zinc-300 transition-colors flex-shrink-0"
            >
              {expanded ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5" />
              )}
            </button>
          ) : (
            <div className="flex items-center justify-center w-5 flex-shrink-0">
              {/* Elbow + leaf */}
              <svg width="20" height="24" viewBox="0 0 20 24" className="text-zinc-700/50">
                <path
                  d={isLast ? "M10 0 L10 12 L18 12" : "M10 0 L10 24 M10 12 L18 12"}
                  stroke="currentColor"
                  strokeWidth="1"
                  fill="none"
                />
              </svg>
            </div>
          )}
        </div>

        {/* Kind icon */}
        <div className="flex-shrink-0">{kindIcon()}</div>

        {/* Name + info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-zinc-200 truncate">{node.name}</span>
            {kindBadge()}
            {node.path && node.kind !== "GitRepository" && (
              <span className="text-[10px] font-mono text-zinc-600 truncate hidden sm:inline">{node.path}</span>
            )}
          </div>
          {node.kind === "GitRepository" && node.url && (
            <div className="flex items-center gap-2 text-[11px] text-zinc-500 mt-0.5">
              <span className="truncate max-w-[300px]">{node.url}</span>
              {node.branch && node.branch !== "main" && (
                <>
                  <span>·</span>
                  <span className="font-mono">{node.branch}</span>
                </>
              )}
              {node.path && (
                <>
                  <span>·</span>
                  <span className="font-mono">{node.path}</span>
                </>
              )}
            </div>
          )}
          {node.kind !== "GitRepository" && (
            <div className="text-[10px] text-zinc-500 font-mono mt-0.5">{node.namespace}</div>
          )}
        </div>

        {/* Status + revision */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {statusDot()}
          <span className="text-[10px] text-zinc-600 w-12 text-right hidden sm:inline">
            {shortRevision(node.revision) || "—"}
          </span>
          <span className="text-[10px] text-zinc-600 w-20 text-right hidden md:inline">
            {formatTime(node.lastSync)}
          </span>
        </div>

        {/* Actions (root GitRepos only) */}
        {isRootGitRepo && (
          <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => onSync?.(node.id, node.name)}
              disabled={syncingId === node.id}
              className="p-1 rounded hover:bg-indigo-500/10 text-zinc-500 hover:text-indigo-400 transition-colors disabled:opacity-50"
              title="Sync"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${syncingId === node.id ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={() => onDelete?.(node.id, node.name)}
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
        )}
      </div>

      {/* Children (animated expand/collapse) */}
      {hasChildren && expanded && (
        <div>
          {node.children.map((child, i) => (
            <FluxTreeRow
              key={child.id}
              node={child}
              depth={depth + 1}
              isLast={i === node.children.length - 1}
              parentIsLast={[...parentIsLast, isLast]}
              onSync={onSync}
              onDelete={onDelete}
              syncingId={syncingId}
              deletingId={deletingId}
            />
          ))}
        </div>
      )}
    </div>
  );
}
