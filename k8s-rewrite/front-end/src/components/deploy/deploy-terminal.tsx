"use client";

import { useRef, useCallback, useEffect } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "@xterm/addon-fit";
import "xterm/css/xterm.css";

interface DeployTerminalProps {
  /** Optional className for the container div */
  className?: string;
  /** Called when the terminal is ready to receive writes */
  onReady?: (terminal: Terminal) => void;
}

/**
 * xterm.js terminal component with FitAddon.
 * Matches the dark theme design system (bg-zinc-950, green-400 text).
 * Uses a deferred mount strategy to avoid xterm.js viewport/renderer
 * initialization issues in React strict mode.
 */
export default function DeployTerminal({ className = "", onReady }: DeployTerminalProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const mountedRef = useRef(false);

  // Track mount state so async callbacks (rAF, ResizeObserver) don't touch a disposed terminal
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const fitTerminal = useCallback(() => {
    if (!mountedRef.current || !terminalRef.current || !fitAddonRef.current) return;
    try {
      fitAddonRef.current.fit();
    } catch {
      // Ignore fit errors (terminal may not be mounted yet)
    }
  }, []);

  // Defer terminal creation to next microtask to ensure container is laid out
  const createTerminal = useCallback(() => {
    if (terminalRef.current || !containerRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      cursorStyle: "block",
      fontSize: 13,
      fontFamily:
        "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
      theme: {
        background: "#09090b",
        foreground: "#4ade80",
        cursor: "#4ade80",
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
      rows: 24,
      cols: 80,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    term.open(containerRef.current);

    terminalRef.current = term;
    fitAddonRef.current = fitAddon;

    // Fit on next animation frame
    requestAnimationFrame(() => {
      if (!mountedRef.current) return;
      try {
        fitAddon.fit();
      } catch {
        // Renderer may not be ready
      }
    });

    if (onReady) {
      onReady(term);
    }

    // Handle resize
    const resizeObserver = new ResizeObserver(() => {
      fitTerminal();
    });
    resizeObserver.observe(containerRef.current);

    // Store cleanup
    const dispose = () => {
      resizeObserver.disconnect();
      term.dispose();
      terminalRef.current = null;
      fitAddonRef.current = null;
    };
    return dispose;
  }, [fitTerminal, onReady]);

  // Ref to hold cleanup function
  const disposeRef = useRef<(() => void) | null>(null);

  // Use callback ref pattern to defer terminal creation
  const setContainerRef = useCallback((node: HTMLDivElement | null) => {
    if (node) {
      containerRef.current = node;
      // Schedule terminal creation after React has committed the DOM
      setTimeout(() => {
        if (containerRef.current === node && !terminalRef.current) {
          disposeRef.current = createTerminal() ?? null;
        }
      }, 0);
    } else {
      if (disposeRef.current) {
        disposeRef.current();
        disposeRef.current = null;
      }
      containerRef.current = null;
    }
  }, [createTerminal]);

  return (
    <div
      ref={setContainerRef}
      className={`bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden ${className}`}
      style={{ minHeight: "300px" }}
    />
  );
}
