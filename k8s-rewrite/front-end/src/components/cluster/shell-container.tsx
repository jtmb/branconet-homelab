"use client";

import { useEffect, useState } from "react";
import { X, Maximize, Trash2, Loader2, Terminal as TerminalIcon } from "lucide-react";
import dynamicNext from "next/dynamic";
import {
  closeShell,
  maximizeShell,
  minimizeShell,
  ShellInstance,
  useShells,
} from "@/lib/shell-manager";

import { K8sIcon } from "@/components/icons/k8s-icon";

const KubectlShell = dynamicNext(
  () => import("@/components/cluster/kubectl-shell"),
  { ssr: false }
);

/**
 * Multi-shell container.
 * - Minimized shells render as a single centered console bar at bottom.
 * - The maximized shell renders as the full slide-up KubectlShell overlay.
 */
export default function ShellContainer() {
  const [mounted, setMounted] = useState(false);
  const { shells, maximized } = useShells();

  useEffect(() => {
    setMounted(true);
  }, []);

  // Don't render shells until after mount to avoid hydration mismatch
  // (sessionStorage restores shells on client but not server)
  if (!mounted) return null;

  const minimized = shells.filter((s) => s.state === "minimized");

  const tabLabel = (s: ShellInstance) =>
    s.type === "kubectl" ? "kubectl" : `${s.namespace}/${s.podName}`;

  return (
    <>
      {/* Minimized console bar — spans content area width */}
      {minimized.length > 0 && !maximized && (
        <div className="absolute bottom-0 left-2 right-2 z-[60]">
          <div
            className="h-6 px-1.5 w-full flex items-center rounded-t-md bg-zinc-900 text-zinc-200 select-none"
          >
            {/* Tab labels — left side, scrollable */}
            <div className="flex items-center gap-1.5 flex-1 min-w-0 overflow-x-auto">
              {minimized.map((s, i) => (
                <span
                  key={s.id}
                  className="flex items-center gap-1.5 text-[11px] font-medium whitespace-nowrap shrink-0 cursor-pointer text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800/50 rounded px-1 py-0.5 transition-colors"
                  onClick={() => maximizeShell(s.id)}
                  title={`Restore ${tabLabel(s)}`}
                >
                  {i > 0 && <span className="text-zinc-700">|</span>}
                  {s.type === "kubectl" ? (
                    <K8sIcon className="w-3 h-3 shrink-0 text-current" />
                  ) : (
                    <TerminalIcon className="w-3 h-3 shrink-0 text-current" />
                  )}
                  <span>{tabLabel(s)} Shell</span>
                  {s.running && (
                    <Loader2 className="w-2.5 h-2.5 shrink-0 animate-spin text-amber-400" />
                  )}
                </span>
              ))}
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-0.5 px-1 shrink-0">
              <button
                onClick={(e) => e.stopPropagation()}
                className="w-5 h-5 rounded flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
                title="Clear terminal"
              >
                <Trash2 className="w-3 h-3" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  maximizeShell(minimized[0].id);
                }}
                className="w-5 h-5 rounded flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
                title="Maximize"
              >
                <Maximize className="w-3 h-3" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  closeShell(minimized[0].id);
                }}
                className="w-5 h-5 rounded flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
                title="Close shell"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Maximized shell */}
      {maximized && (
        <KubectlShell
          key={maximized.id}
          open={true}
          onClose={() => closeShell(maximized.id)}
          onMinimize={() => minimizeShell(maximized.id)}
          namespace={maximized.namespace}
          podName={maximized.podName}
          shells={shells}
          activeShellId={maximized.id}
          onSwitchTab={(id) => maximizeShell(id)}
          onCloseTab={(id) => closeShell(id)}
        />
      )}
    </>
  );
}
