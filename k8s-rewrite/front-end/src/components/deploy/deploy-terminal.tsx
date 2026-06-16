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

  // Create the terminal instance and open it in the container.
  // Called from setContainerRef after React commits the DOM node.
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
        foreground: "#e4e4e7",
        cursor: "#e4e4e7",
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
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    terminalRef.current = term;
    fitAddonRef.current = fitAddon;

    // Open xterm into the DOM. By now the container ref is attached and
    // the browser has laid out the element, so dimensions are available.
    try {
      term.open(containerRef.current);
    } catch {
      // Container may have been removed between the guard and open
      return;
    }

    // Use onRender for the initial fit — xterm 5.x renderer initializes
    // asynchronously and calling fit() before the first render can crash
    // with "Cannot read properties of undefined (reading 'dimensions')".
    let fitted = false;
    const renderDispose = term.onRender(() => {
      if (!mountedRef.current || fitted) return;
      fitted = true;
      try { fitAddon.fit(); } catch { /* swallow */ }
    });

    if (onReady) onReady(term);

    // ResizeObserver keeps the terminal fitted when the parent layout changes.
    // Only start observing after the renderer has computed initial dimensions.
    let resizeObserver: ResizeObserver | null = null;
    const startResizeObserver = () => {
      if (resizeObserver || !containerRef.current) return;
      resizeObserver = new ResizeObserver(() => {
        if (!mountedRef.current) return;
        try { fitAddon.fit(); } catch { /* swallow */ }
      });
      resizeObserver.observe(containerRef.current);
    };
    // Hook resize observer to the first render as well, but with a short
    // delay to ensure dimensions exist before ResizeObserver's initial flush.
    const roRenderDispose = term.onRender(() => {
      startResizeObserver();
      roRenderDispose.dispose();
    });

    // Cleanup
    const dispose = () => {
      renderDispose.dispose();
      try { roRenderDispose.dispose(); } catch { /* may already be disposed */ }
      if (resizeObserver) resizeObserver.disconnect();
      term.dispose();
      terminalRef.current = null;
      fitAddonRef.current = null;
    };
    return dispose;
  }, [onReady]);

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
      className={`bg-zinc-950 overflow-hidden ${className}`}
      style={{ minHeight: "300px" }}
    />
  );
}
