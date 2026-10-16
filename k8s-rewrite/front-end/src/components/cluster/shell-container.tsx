"use client";

import { Component, type ReactNode, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { X, Maximize, Loader2, Terminal as TerminalIcon } from "lucide-react";
import dynamicNext from "next/dynamic";
import {
  closeShell,
  maximizeShell,
  minimizeShell,
  ShellInstance,
  useShells,
} from "@/lib/shell-manager";

import { K8sIcon } from "@/components/icons/k8s-icon";
import { useSession } from "@/lib/use-query";
import { closeAllShells } from "@/lib/shell-manager";

const KubectlShell = dynamicNext(
  () => import("@/components/cluster/kubectl-shell"),
  { ssr: false, loading: () => <p role="status" className="bg-zinc-900 p-3 text-sm text-zinc-200">Loading terminal…</p> }
);

class TerminalLoadBoundary extends Component<{ children: ReactNode; onClose: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed ? <section aria-label="Terminal unavailable" className="border border-zinc-700 bg-zinc-900 p-3 text-sm text-zinc-200">
      <p role="status">Terminal could not load. Close it and reload the page before retrying.</p>
      <button onClick={this.props.onClose} className="mt-2 rounded border border-zinc-600 px-3 py-2">Close unavailable terminal</button>
    </section> : this.props.children;
  }
}

/**
 * Multi-shell container.
 * - Minimized shells render as a single centered console bar at bottom.
 * - The maximized shell renders as the full slide-up KubectlShell overlay.
 */
export default function ShellContainer() {
  const [mounted, setMounted] = useState(false);
  const { shells, maximized } = useShells();
  const session = useSession();
  const pathname = usePathname();
  const previousPath = useRef(pathname);
  const anchor = useRef<HTMLDivElement>(null);
  const [bounds, setBounds] = useState<{ left: number; width: number }>();
  const previousMaximized = useRef<string>();
  useEffect(() => {
    const previous = previousMaximized.current; previousMaximized.current = maximized?.id;
    if (!previous || maximized || !session.canWrite) return;
    const frame = requestAnimationFrame(() => document.getElementById(`restore-shell-${previous}`)?.focus());
    return () => cancelAnimationFrame(frame);
  }, [maximized, session.canWrite]);

  useEffect(() => {
    setMounted(true);
  }, []);
  useEffect(() => {
    const parent = anchor.current?.parentElement;
    if (!parent) return;
    const measure = () => { const box = parent.getBoundingClientRect(); setBounds({ left: box.left, width: box.width }); };
    measure(); const observer = new ResizeObserver(measure); observer.observe(parent);
    window.addEventListener("resize", measure);
    return () => { observer.disconnect(); window.removeEventListener("resize", measure); };
  }, []);
  useEffect(() => {
    if (previousPath.current !== pathname) closeAllShells();
    previousPath.current = pathname;
  }, [pathname]);
  useEffect(() => {
    const hidden = () => { if (document.visibilityState === "hidden") closeAllShells(); };
    document.addEventListener("visibilitychange", hidden);
    window.addEventListener("pagehide", closeAllShells);
    return () => { document.removeEventListener("visibilitychange", hidden); window.removeEventListener("pagehide", closeAllShells); };
  }, []);
  useEffect(() => {
    if (!session.loading && !session.canWrite) closeAllShells();
    else if (session.canWrite) shells.forEach(shell => {
      if (shell.type === "kubectl" ? !session.data?.capabilities?.operatorShell : !session.data?.capabilities?.podExec) closeShell(shell.id);
    });
  }, [session.loading, session.canWrite, session.data?.capabilities, shells]);

  // Don't render shells until after mount to avoid hydration mismatch
  // (sessionStorage restores shells on client but not server)
  const available = mounted && session.canWrite && !!bounds;

  const minimized = shells.filter((s) => s.state === "minimized");

  const tabLabel = (s: ShellInstance) =>
    s.type === "kubectl" ? "kubectl" : `${s.namespace}/${s.podName}`;

  return (
    <>
      <div ref={anchor} aria-hidden="true" />
      {available && <div className="fixed bottom-0 z-[60]" style={bounds}>
      {/* Minimized console bar — spans content area width */}
      {minimized.length > 0 && !maximized && (
        <div aria-label="Minimized terminals" role="region" className="mx-2">
          <div
            className="min-h-9 px-1.5 w-full flex items-center rounded-t-md bg-zinc-900 text-zinc-200 select-none"
          >
            {/* Tab labels — left side, scrollable */}
            <div className="flex items-center gap-1.5 flex-1 min-w-0 overflow-x-auto">
              {minimized.map((s, i) => (
                <button
                  key={s.id}
                  id={`restore-shell-${s.id}`}
                  className="flex min-h-8 items-center gap-1.5 text-xs font-medium whitespace-nowrap shrink-0 text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800/50 rounded px-1 py-0.5 transition-colors"
                  onClick={() => maximizeShell(s.id)}
                  title={`Restore ${tabLabel(s)}`}
                  aria-label={`Restore ${tabLabel(s)} Shell`}
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
                </button>
              ))}
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-0.5 px-1 shrink-0">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  maximizeShell(minimized[0].id);
                }}
                className="w-8 h-8 rounded flex items-center justify-center text-zinc-300 hover:bg-zinc-800 transition-colors"
                title="Maximize"
                aria-label="Maximize terminal"
              >
                <Maximize className="w-3 h-3" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  closeShell(minimized[0].id, true);
                }}
                className="w-8 h-8 rounded flex items-center justify-center text-zinc-300 hover:bg-zinc-800 transition-colors"
                title="Close shell"
                aria-label="Close shell"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Maximized shell */}
      {maximized && (
        <TerminalLoadBoundary key={maximized.id} onClose={() => closeShell(maximized.id, true)}>
        <KubectlShell
          key={maximized.id}
          open={true}
          onClose={() => closeShell(maximized.id, true)}
          onMinimize={() => minimizeShell(maximized.id)}
          namespace={maximized.namespace}
          podName={maximized.podName}
          shells={shells}
          activeShellId={maximized.id}
          onSwitchTab={(id) => maximizeShell(id)}
          onCloseTab={(id) => closeShell(id, true)}
        />
        </TerminalLoadBoundary>
      )}
      </div>}
    </>
  );
}
