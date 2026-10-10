"use client";

import { useRef, useEffect, useCallback, useState } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "@xterm/addon-fit";
import { X, Trash2, Minimize2, Loader2, Terminal as TerminalIcon } from "lucide-react";
import "xterm/css/xterm.css";
import { K8sIcon } from "@/components/icons/k8s-icon";
import type { ShellInstance } from "@/lib/shell-manager";
import { setShellRunning } from "@/lib/shell-manager";

interface KubectlShellProps {
  open: boolean;
  onClose: () => void;
  /** Called when the user clicks the minimize button or backdrop */
  onMinimize?: () => void;
  /** When provided, all commands are prefixed with `exec <podName> -n <namespace> -- ` */
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

  // Build contextual welcome banner
  const writeWelcomeBanner = useCallback(() => {
    const term = terminalRef.current;
    if (!term) return;
    const titleText = namespace && podName
      ? `kubectl exec — ${namespace}/${podName}`
      : "kubectl Shell — Botrus K8s";
    const hintText = namespace && podName
      ? "Type commands to run inside the pod"
      : "Working directory: /home/shell";
    const exampleText = namespace && podName
      ? "e.g. ls -la, cat /etc/hosts, ps aux"
      : "e.g. ls, kubectl get pods -A, cat file.txt";

    // Content width inside the box: ║___<content>║
    // Box is 44 chars wide (╔ + 42×═ + ╗), so content = 44 - 1(║) - 3(margin) - 1(║) = 39
    const BOX_W = 39;

    /** Visual display width — accounts for East Asian double-width characters */
    const visualWidth = (s: string): number => {
      let w = 0;
      for (const ch of s) {
        const cp = ch.codePointAt(0) ?? 0;
        // East Asian Wide & Fullwidth ranges (CJK, box drawing, etc.)
        // Arrows (0x2190-0x21FF) are Ambiguous but xterm.js renders them single-width here.
        if (
          (cp >= 0x2500 && cp <= 0x257F) || // box drawing (╔═║ etc.)
          (cp >= 0x2E80 && cp <= 0x9FFF) || // CJK Radicals through CJK Unified
          (cp >= 0xFF01 && cp <= 0xFFE6)    // Fullwidth forms
        ) {
          w += 2;
        } else {
          w += 1;
        }
      }
      return w;
    };

    const padBox = (s: string): string => {
      // Strip ANSI for visual width calculation
      const plain = s.replace(/\x1b\[[0-9;]*m/g, "");
      const vw = visualWidth(plain);
      if (vw > BOX_W) {
        // Truncate — walk chars keeping count until BOX_W - 1, then append …
        let acc = 0;
        let i = 0;
        for (const ch of plain) {
          acc += visualWidth(ch);
          i++;
          if (acc >= BOX_W - 1) break;
        }
        return plain.slice(0, i) + "…";
      }
      return s + " ".repeat(BOX_W - vw);
    };

    const shortcutsLine = padBox("clear  ctrl+c  ctrl+l  ↑↓ history");

    term.writeln("\x1b[1;36m╔══════════════════════════════════════════╗\x1b[0m");
    term.writeln(`\x1b[1;36m║\x1b[0m   \x1b[1;33m${padBox(titleText)}\x1b[1;36m║\x1b[0m`);
    term.writeln(`\x1b[1;36m║\x1b[0m   ${padBox(hintText)}\x1b[1;36m║\x1b[0m`);
    term.writeln(`\x1b[1;36m║\x1b[0m   \x1b[2m${padBox(exampleText)}\x1b[1;36m║\x1b[0m`);
    term.writeln(`\x1b[1;36m║\x1b[0m   \x1b[2m${shortcutsLine}\x1b[0m\x1b[1;36m║\x1b[0m`);
    term.writeln("\x1b[1;36m╚══════════════════════════════════════════╝\x1b[0m");
  }, [namespace, podName]);

  // Send command to API
  const executeCommand = useCallback(
    async (cmd: string) => {
      const term = terminalRef.current;
      if (!term) return;

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

      // Track running state with minimum display time so the spinner is always visible
      const MIN_SPIN_MS = 400;

      // When pod context is set, wrap commands with kubectl exec
      const ctx = podCtxRef.current;
      const apiCommand =
        ctx.namespace && ctx.podName
          ? `kubectl exec ${ctx.podName} -n ${ctx.namespace} -- ${trimmed}`
          : trimmed;

      const startMs = Date.now();
      const sid = shellIdRef.current;
      try {
        setShellRunning(sid, true);
        const res = await fetch("/api/cluster/kubectl", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: apiCommand }),
        });

        const data = await res.json();
        if (data.error) {
          write(`\x1b[1;31m${data.error}\x1b[0m`);
        } else if (data.output) {
          write(data.output);
        }
        // commands like touch, cd, mkdir produce no stdout — that's fine,
        // just show a new prompt (no artificial "(no output)" message)
      } catch (err: any) {
        write(`\x1b[1;31mError: ${err?.message || "Request failed"}\x1b[0m`);
      } finally {
        // Ensure spinner is visible for at least MIN_SPIN_MS
        const elapsed = Date.now() - startMs;
        if (elapsed < MIN_SPIN_MS) {
          await new Promise((r) => setTimeout(r, MIN_SPIN_MS - elapsed));
        }
        setShellRunning(sid, false);
      }

      writePrompt();
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
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    terminalRef.current = term;
    fitAddonRef.current = fitAddon;

    try {
      term.open(containerRef.current);
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
  }, [executeCommand, write, writePrompt, writeWelcomeBanner]);

  // Set container ref — defers terminal creation to when open first becomes true
  const setContainerRef = useCallback(
    (el: HTMLDivElement | null) => {
      containerRef.current = el;
    },
    []
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (containerRef.current && (containerRef.current as any).__termCleanup) {
        (containerRef.current as any).__termCleanup();
      }
    };
  }, []);

  // Initialize terminal when it becomes open
  useEffect(() => {
    if (open && containerRef.current && !terminalRef.current) {
      requestAnimationFrame(() => {
        const cleanup = createTerminal();
        if (cleanup && containerRef.current) {
          (containerRef.current as any).__termCleanup = cleanup;
        }
      });
    }
  }, [open, createTerminal]);

  return (
    <>
      {/* Shell panel — slides up from bottom (no backdrop) */}
      <div
        className={`absolute bottom-0 left-0 right-0 z-50 transition-transform duration-300 ease-out ${
          visible ? "translate-y-0" : "translate-y-full"
        }`}
        style={{ height: `${shellHeight}vh` }}
      >
        {/* Header bar — matches minimized bar design */}
        <div
          className="flex items-center h-6 px-1.5 bg-zinc-900 rounded-t-md cursor-ns-resize select-none"
          onMouseDown={startResize}
        >
          {/* Tab labels — left side, scrollable */}
          <div className="flex items-center gap-1.5 flex-1 min-w-0 overflow-x-auto">
            {(shells && shells.length > 0 ? shells : [{ id: activeShellId ?? "__kubectl__", type: (namespace && podName ? "exec" as const : "kubectl" as const), namespace, podName, state: "maximized" as const }]).map((s, i) => {
              const isActive = s.id === activeShellId || shells === undefined;
              const label = s.type === "kubectl" ? "kubectl" : `${s.namespace}/${s.podName}`;
              return (
                <span
                  key={s.id}
                  className={`flex items-center gap-1.5 text-[11px] font-medium whitespace-nowrap shrink-0 cursor-pointer rounded px-1 py-0.5 transition-colors ${
                    isActive
                      ? "text-zinc-200"
                      : "text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800/50"
                  }`}
                  onClick={isActive ? undefined : () => onSwitchTab?.(s.id)}
                  title={isActive ? undefined : `Switch to ${label}`}
                >
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
                  {shells && shells.length > 1 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onCloseTab?.(s.id);
                      }}
                      className="w-3.5 h-3.5 rounded-sm flex items-center justify-center text-zinc-600 hover:text-zinc-200 hover:bg-zinc-700 transition-colors"
                      title={`Close ${label}`}
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
                  term.clear();
                  writeWelcomeBanner();
                  writePrompt();
                }
              }}
              className="w-5 h-5 rounded flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
              title="Clear terminal"
            >
              <Trash2 className="w-3 h-3" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onMinimize?.(); }}
              className="w-5 h-5 rounded flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
              title="Minimize"
            >
              <Minimize2 className="w-3 h-3" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onClose(); }}
              className="w-5 h-5 rounded flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
              title="Close shell"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Terminal container — always rendered, hidden when closed */}
        <div className="h-[calc(100%-24px)] bg-zinc-950 border border-zinc-800 rounded-b-xl overflow-hidden">
          <div ref={setContainerRef} className="w-full h-full" />
        </div>
      </div>
    </>
  );
}
