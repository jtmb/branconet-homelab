"use client";

import { useRef, useEffect, useCallback, useState } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "@xterm/addon-fit";
import { X, Trash2, Minimize2, Loader2, Terminal as TerminalIcon } from "lucide-react";
import "xterm/css/xterm.css";
import { K8sIcon } from "@/components/icons/k8s-icon";
import type { ShellInstance } from "@/lib/shell-manager";
import { setShellRunning } from "@/lib/shell-manager";
import { requestJson } from "@/lib/use-query";

interface KubectlShellProps {
  open: boolean;
  onClose: () => void;
  /** Called when the user clicks the minimize button or backdrop */
  onMinimize?: () => void;
  /** Commands are sent to the scoped pod-exec endpoint when a pod is selected. */
  namespace?: string;
  podName?: string;
  /** All open shells — rendered as terminal-style tabs in the header */
  shells?: ShellInstance[];
  /** Currently active shell id */
  activeShellId?: string;
  /** Called when user clicks a different tab */
  onSwitchTab?: (id: string) => void;
  /** Called when user closes a tab */
  onCloseTab?: (id: string) => void;
}

const PROMPT = "\r\n\x1b[1;32m$\x1b[0m ";

/**
 * Slide-up kubectl shell overlay using xterm.js.
 * Sends commands to POST /api/cluster/kubectl and displays output.
 */
export default function KubectlShell({ open, onClose, onMinimize, namespace, podName, shells, activeShellId, onSwitchTab, onCloseTab }: KubectlShellProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const mountedRef = useRef(false);
  const commandController = useRef<AbortController>();
  const commandBusy = useRef(false);
  const [visible, setVisible] = useState(open);

  // Compute shell id for the active shell — used to set running state
  const shellId = activeShellId ?? (namespace && podName ? `exec:${namespace}:${podName}` : "__kubectl__");
  const shellIdRef = useRef(shellId);
  shellIdRef.current = shellId;

  // --- resize ---
  const shellHeightRef = useRef(42); // vh
  const [shellHeight, setShellHeight] = useState(42);
  shellHeightRef.current = shellHeight;

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startH = shellHeightRef.current;
    const onMove = (ev: MouseEvent) => {
      const delta = (startY - ev.clientY) / window.innerHeight * 100;
      const newH = Math.min(80, Math.max(20, startH + delta));
      shellHeightRef.current = newH;
      setShellHeight(newH);
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, []);

  // Command buffer & history
  const inputBuffer = useRef("");
  const cursorPos = useRef(0);
  const history = useRef<string[]>([]);
  const historyIdx = useRef(-1);
  const promptLength = useRef(0);

  // Pod context refs — always current, avoids stale closure in onData handler
  const podCtxRef = useRef<{ namespace?: string; podName?: string }>({});
  podCtxRef.current = { namespace, podName };

  // Animate out before close (open→false). Mount already starts visible so no slide-up replay on tab switch.
  useEffect(() => {
    if (!open) {
      setVisible(false);
    }
  }, [open]);

  // Track mount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      commandController.current?.abort();
    };
  }, []);

  // Write text helper
  const write = useCallback((text: string) => {
    terminalRef.current?.write(text);
  }, []);

  // Write prompt and reset buffer
  const writePrompt = useCallback(() => {
    write(PROMPT);
    inputBuffer.current = "";
    cursorPos.current = 0;
    promptLength.current = 2; // "$ " after the ANSI codes
  }, [write]);

  // Public instructions wrap at the fitted terminal width; identities are never truncated.
  const writeWelcomeBanner = useCallback(() => {
    const term = terminalRef.current;
    if (!term) return;
    const lines = [
      namespace && podName ? "Pod command runner" : "Operator command runner",
      namespace && podName ? `${namespace}/${podName}` : "Application-host commands",
      "One command per request.",
      "No interactive PTY.",
      "Clear erases local input/history.",
      "Ctrl+C stops the client request.",
      "Inspect server state before retrying.",
    ];
    const width = Math.max(2, term.cols);
    for (const text of lines) {
      let remaining = text;
      while (remaining.length > width) {
        const space = remaining.lastIndexOf(" ", width);
        const end = space > 0 ? space : width;
        term.writeln(remaining.slice(0, end));
        remaining = remaining.slice(end).trimStart();
      }
      term.writeln(remaining);
    }
  }, [namespace, podName]);

  // Send command to API
  const executeCommand = useCallback(
    async (cmd: string) => {
      const term = terminalRef.current;
      if (!term || commandBusy.current) return;

      const trimmed = cmd.trim();
      if (!trimmed) {
        writePrompt();
        return;
      }

      // Add to history
      if (trimmed !== "clear") {
        history.current.push(trimmed);
        if (history.current.length > 200) history.current.shift();
      }
      historyIdx.current = -1;

      if (trimmed === "clear") {
        term.clear();
        writePrompt();
        return;
      }

      write("\r\n");

      const ctx = podCtxRef.current;
      const url = ctx.namespace && ctx.podName
        ? `/api/cluster/pods/${encodeURIComponent(ctx.namespace)}/${encodeURIComponent(ctx.podName)}/exec`
        : "/api/cluster/kubectl";
      const sid = shellIdRef.current;
      const controller = new AbortController();
      commandController.current = controller;
      commandBusy.current = true;
      const timeout = setTimeout(() => controller.abort(), 35000);
      try {
        setShellRunning(sid, true);
        const data = await requestJson<{ output?: string }>(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: trimmed }),
          signal: controller.signal,
        });
        if (mountedRef.current && data.output) {
          write(data.output);
        }
        // commands like touch, cd, mkdir produce no stdout — that's fine,
        // just show a new prompt (no artificial "(no output)" message)
      } catch (err: any) {
        if (mountedRef.current) write(`\x1b[1;31mError: ${controller.signal.aborted ? "Client request stopped; inspect server state before retrying." : err?.message || "Request failed"}\x1b[0m`);
      } finally {
        clearTimeout(timeout);
        commandBusy.current = false;
        commandController.current = undefined;
        setShellRunning(sid, false);
      }

      if (mountedRef.current) writePrompt();
    },
    [write, writePrompt]
  );

  // Redraw the current input line
  const redrawInput = useCallback(() => {
    const term = terminalRef.current;
    if (!term) return;

    // Move cursor to beginning of input, clear to end of line, rewrite
    const buf = inputBuffer.current;
    const extra = buf.length - cursorPos.current;

    // Move cursor back to after prompt
    if (extra > 0) {
      term.write(`\x1b[${extra}D`);
    }
    term.write("\x1b[0K");
    term.write(buf);
    // Move cursor back to position
    if (extra > 0) {
      term.write(`\x1b[${extra}D`);
    }
  }, []);

  // Create terminal
  const createTerminal = useCallback(() => {
    if (terminalRef.current || !containerRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      cursorStyle: "bar",
      fontSize: 14,
      fontFamily:
        "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
      theme: {
        background: "#09090b",
        foreground: "#d4d4d8",
        cursor: "#a1a1aa",
        selectionBackground: "#6366f155",
        black: "#09090b",
        red: "#ef4444",
        green: "#4ade80",
        yellow: "#facc15",
        blue: "#6366f1",
        magenta: "#a855f7",
        cyan: "#22d3ee",
        white: "#e4e4e7",
        brightBlack: "#52525b",
        brightRed: "#f87171",
        brightGreen: "#86efac",
        brightYellow: "#fde047",
        brightBlue: "#818cf8",
        brightMagenta: "#c084fc",
        brightCyan: "#67e8f9",
        brightWhite: "#f4f4f5",
      },
      allowTransparency: false,
      convertEol: true,
      rows: 10,
      screenReaderMode: true,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    // A one-shot command runner has no tab completion; preserve browser Tab/Shift+Tab navigation.
    term.attachCustomKeyEventHandler(event => event.key !== "Tab");

    terminalRef.current = term;
    fitAddonRef.current = fitAddon;

    try {
      term.open(containerRef.current);
      fitAddon.fit();
      term.textarea?.setAttribute("aria-label", namespace && podName ? `Command input for ${namespace}/${podName}` : "Operator command input");
      term.focus();
    } catch {
      return;
    }

    // Initial fit after first render
    let fitted = false;
    const renderDispose = term.onRender(() => {
      if (!mountedRef.current || fitted) return;
      fitted = true;
      try {
        fitAddon.fit();
      } catch {
        /* swallow */
      }
    });

    // ResizeObserver
    let resizeObserver: ResizeObserver | null = null;
    const roRenderDispose = term.onRender(() => {
      if (resizeObserver || !containerRef.current) return;
      resizeObserver = new ResizeObserver(() => {
        if (!mountedRef.current) return;
        try {
          fitAddon.fit();
        } catch {
          /* swallow */
        }
      });
      resizeObserver.observe(containerRef.current);
      roRenderDispose.dispose();
    });

    // Handle keyboard input
    term.onData((data) => {
      if (!mountedRef.current) return;
      const code = data.charCodeAt(0);
      if (commandBusy.current) {
        if (code === 3) commandController.current?.abort();
        return;
      }

      // Enter
      if (code === 13) {
        const cmd = inputBuffer.current;
        term.write("\r\n");
        executeCommand(cmd);
        return;
      }

      // Backspace
      if (code === 127) {
        if (cursorPos.current > 0) {
          const before = inputBuffer.current.slice(0, cursorPos.current - 1);
          const after = inputBuffer.current.slice(cursorPos.current);
          inputBuffer.current = before + after;
          cursorPos.current--;
          // Move left, clear to end, rewrite, move back
          term.write("\x1b[D");
          term.write("\x1b[0K");
          term.write(after);
          if (after.length > 0) {
            term.write(`\x1b[${after.length}D`);
          }
        }
        return;
      }

      // Ctrl+C — clear buffer
      if (code === 3) {
        term.write("^C\r\n");
        writePrompt();
        return;
      }

      // Ctrl+L — clear screen
      if (code === 12) {
        term.clear();
        writePrompt();
        return;
      }

      // Up arrow (history)
      if (data === "\x1b[A") {
        const hist = history.current;
        if (hist.length === 0) return;
        if (historyIdx.current === -1) {
          historyIdx.current = hist.length - 1;
        } else if (historyIdx.current > 0) {
          historyIdx.current--;
        }
        // Clear current input, write history item
        const oldLen = inputBuffer.current.length;
        if (oldLen > 0) term.write(`\x1b[${oldLen}D`);
        term.write("\x1b[0K");
        inputBuffer.current = hist[historyIdx.current];
        cursorPos.current = inputBuffer.current.length;
        term.write(inputBuffer.current);
        return;
      }

      // Down arrow (history)
      if (data === "\x1b[B") {
        const hist = history.current;
        const oldLen = inputBuffer.current.length;
        if (oldLen > 0) term.write(`\x1b[${oldLen}D`);
        term.write("\x1b[0K");
        if (historyIdx.current === -1 || historyIdx.current >= hist.length - 1) {
          inputBuffer.current = "";
          historyIdx.current = -1;
        } else {
          historyIdx.current++;
          inputBuffer.current = hist[historyIdx.current];
        }
        cursorPos.current = inputBuffer.current.length;
        term.write(inputBuffer.current);
        return;
      }

      // Left arrow
      if (data === "\x1b[D") {
        if (cursorPos.current > 0) {
          cursorPos.current--;
          term.write("\x1b[D");
        }
        return;
      }

      // Right arrow
      if (data === "\x1b[C") {
        if (cursorPos.current < inputBuffer.current.length) {
          cursorPos.current++;
          term.write("\x1b[C");
        }
        return;
      }

      // Home (Ctrl+A)
      if (code === 1) {
        if (cursorPos.current > 0) {
          term.write(`\x1b[${cursorPos.current}D`);
          cursorPos.current = 0;
        }
        return;
      }

      // End (Ctrl+E)
      if (code === 5) {
        const diff = inputBuffer.current.length - cursorPos.current;
        if (diff > 0) {
          term.write(`\x1b[${diff}C`);
          cursorPos.current = inputBuffer.current.length;
        }
        return;
      }

      // Delete (forward delete)
      if (data === "\x1b[3~") {
        if (cursorPos.current < inputBuffer.current.length) {
          const before = inputBuffer.current.slice(0, cursorPos.current);
          const after = inputBuffer.current.slice(cursorPos.current + 1);
          inputBuffer.current = before + after;
          term.write("\x1b[0K");
          term.write(after);
          if (after.length > 0) {
            term.write(`\x1b[${after.length}D`);
          }
        }
        return;
      }

      // Printable characters
      if (data.length === 1 && code >= 32 && code < 127) {
        const before = inputBuffer.current.slice(0, cursorPos.current);
        const after = inputBuffer.current.slice(cursorPos.current);
        inputBuffer.current = before + data + after;
        cursorPos.current++;
        term.write("\x1b[0K");
        term.write(inputBuffer.current.slice(cursorPos.current - 1));
        // Move cursor back to correct position
        const remaining = inputBuffer.current.length - cursorPos.current;
        if (remaining > 0) {
          term.write(`\x1b[${remaining}D`);
        }
      }
    });

    // Welcome banner
    writeWelcomeBanner();
    writePrompt();

    const dispose = () => {
      renderDispose.dispose();
      try {
        roRenderDispose.dispose();
      } catch {
        /* may already be disposed */
      }
      if (resizeObserver) resizeObserver.disconnect();
      term.dispose();
      terminalRef.current = null;
      fitAddonRef.current = null;
    };
    return dispose;
  }, [executeCommand, writePrompt, writeWelcomeBanner, namespace, podName]);

  // Set container ref — defers terminal creation to when open first becomes true
  const setContainerRef = useCallback(
    (el: HTMLDivElement | null) => {
      containerRef.current = el;
    },
    []
  );

  // Initialize terminal when it becomes open
  useEffect(() => {
    let cleanup: (() => void) | undefined;
    let frame: number | undefined;
    if (open && containerRef.current && !terminalRef.current) {
      frame = requestAnimationFrame(() => { cleanup = createTerminal(); });
    }
    return () => { if (frame !== undefined) cancelAnimationFrame(frame); cleanup?.(); };
  }, [open, createTerminal]);

  return (
    <>
      {/* Shell panel — slides up from bottom (no backdrop) */}
      <div
        role="region"
        aria-label={namespace && podName ? `Terminal for ${namespace}/${podName}` : "Operator terminal"}
        className={`relative w-full transition-transform duration-300 ease-out ${
          visible ? "translate-y-0" : "translate-y-full"
        }`}
        style={{ height: `${shellHeight}vh` }}
      >
        {/* Header bar — matches minimized bar design */}
        <div
          role="separator" tabIndex={0} aria-label="Terminal height" aria-orientation="horizontal"
          aria-valuemin={20} aria-valuemax={80} aria-valuenow={shellHeight}
          className="h-2 bg-zinc-800 cursor-ns-resize"
          onMouseDown={startResize}
          onKeyDown={event => {
            const height = event.key === "Home" ? 20 : event.key === "End" ? 80 : event.key === "ArrowUp" ? Math.min(80, shellHeight + 5) : event.key === "ArrowDown" ? Math.max(20, shellHeight - 5) : undefined;
            if (height !== undefined) { event.preventDefault(); setShellHeight(height); }
          }}
        />
        <div
          className="flex items-center min-h-9 px-1.5 bg-zinc-900 rounded-t-md select-none"
        >
          {/* Tab labels — left side, scrollable */}
          <div className="flex items-center gap-1.5 flex-1 min-w-0 overflow-x-auto">
            {(shells && shells.length > 0 ? shells : [{ id: activeShellId ?? "__kubectl__", type: (namespace && podName ? "exec" as const : "kubectl" as const), namespace, podName, state: "maximized" as const }]).map((s, i) => {
              const isActive = s.id === activeShellId || shells === undefined;
              const label = s.type === "kubectl" ? "kubectl" : `${s.namespace}/${s.podName}`;
              return (
                <span
                  key={s.id}
                  className={`flex items-center gap-1.5 text-xs font-medium whitespace-nowrap shrink-0 rounded px-1 py-0.5 transition-colors ${
                    isActive
                      ? "text-zinc-200"
                      : "text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800/50"
                  }`}
                >
                  <button aria-label={`Switch to ${label} Shell`} aria-pressed={isActive} onClick={() => { if (isActive) terminalRef.current?.focus(); else onSwitchTab?.(s.id); }} className="flex min-h-8 items-center gap-1.5 rounded px-1 hover:bg-zinc-800">
                  {i > 0 && <span className="text-zinc-700">|</span>}
                  {s.type === "kubectl" ? (
                    <K8sIcon className={isActive ? "w-3 h-3 shrink-0 text-sky-400" : "w-3 h-3 shrink-0 text-current"} />
                  ) : (
                    <TerminalIcon className={isActive ? "w-3 h-3 shrink-0 text-indigo-400" : "w-3 h-3 shrink-0 text-current"} />
                  )}
                  <span>{label} Shell</span>
                  {s.running && (
                    <Loader2 className="w-2.5 h-2.5 shrink-0 animate-spin text-amber-400" />
                  )}
                  </button>
                  {shells && shells.length > 1 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onCloseTab?.(s.id);
                      }}
                      className="w-8 h-8 rounded-sm flex items-center justify-center text-zinc-300 hover:bg-zinc-700 transition-colors"
                      title={`Close ${label}`}
                      aria-label={`Close ${label}`}
                    >
                      <X className="w-2.5 h-2.5" />
                    </button>
                  )}
                </span>
              );
            })}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-0.5 px-1 shrink-0">
            <button
              onClick={(e) => {
                e.stopPropagation();
                const term = terminalRef.current;
                if (term) {
                  term.reset(); history.current = []; historyIdx.current = -1;
                  writeWelcomeBanner();
                  writePrompt();
                  term.focus();
                }
              }}
              className="w-8 h-8 rounded flex items-center justify-center text-zinc-300 hover:bg-zinc-800 transition-colors"
              title="Clear terminal"
              aria-label="Clear terminal"
            >
              <Trash2 className="w-3 h-3" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onMinimize?.(); }}
              className="w-8 h-8 rounded flex items-center justify-center text-zinc-300 hover:bg-zinc-800 transition-colors"
              title="Minimize"
              aria-label="Minimize terminal"
            >
              <Minimize2 className="w-3 h-3" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onClose(); }}
              className="w-8 h-8 rounded flex items-center justify-center text-zinc-300 hover:bg-zinc-800 transition-colors"
              title="Close shell"
              aria-label="Close shell"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Terminal container — always rendered, hidden when closed */}
        <div className="h-[calc(100%-44px)] bg-zinc-950 border border-zinc-800 overflow-hidden">
          <div ref={setContainerRef} className="w-full h-full" />
        </div>
      </div>
    </>
  );
}
