"use client";

import { useRef, useEffect, useCallback, useImperativeHandle, forwardRef } from "react";

export interface DeployLogViewerHandle {
  write(text: string): void;
  writeln(text: string): void;
  clear(): void;
}

interface DeployLogViewerProps {
  className?: string;
  onReady?: (api: DeployLogViewerHandle) => void;
}

/**
 * Simple scrollable log viewer that replaces xterm.js for Ansible output.
 * Exposes the same write / writeln / clear API so deploy-client.tsx doesn't
 * need major refactoring. Strips ANSI escape codes from incoming text.
 */
const DeployLogViewer = forwardRef<DeployLogViewerHandle, DeployLogViewerProps>(
  function DeployLogViewer({ className = "", onReady }, ref) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const idleRef = useRef(true);

    // Auto-scroll helper
    const scrollToBottom = useCallback(() => {
      const el = containerRef.current;
      if (!el) return;
      el.scrollTop = el.scrollHeight;
    }, []);

    // Strip ANSI escape sequences
    const stripAnsi = useCallback((text: string): string => {
      return text.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "");
    }, []);

    // Append raw text nodes (preserves whitespace, no innerHTML risk)
    const appendText = useCallback((raw: string) => {
      const el = containerRef.current;
      if (!el) return;
      const clean = stripAnsi(raw);
      if (!clean) return;
      el.appendChild(document.createTextNode(clean));
    }, [stripAnsi]);

    const write = useCallback(
      (raw: string) => {
        const el = containerRef.current;
        if (!el) return;
        if (idleRef.current) {
          // Replace idle placeholder with real content
          el.textContent = "";
          idleRef.current = false;
        }
        appendText(raw);
        scrollToBottom();
      },
      [appendText, scrollToBottom]
    );

    const writeln = useCallback(
      (raw: string) => {
        const el = containerRef.current;
        if (!el) return;
        if (idleRef.current) {
          el.textContent = "";
          idleRef.current = false;
        }
        appendText(raw + "\n");
        scrollToBottom();
      },
      [appendText, scrollToBottom]
    );

    const clear = useCallback(() => {
      const el = containerRef.current;
      if (!el) return;
      el.textContent = "";
      idleRef.current = true;
      // Restore idle cursor
      const cursor = document.createElement("span");
      cursor.className = "inline-block w-2 h-4 bg-emerald-500 animate-pulse align-middle ml-0.5";
      cursor.setAttribute("aria-hidden", "true");
      el.appendChild(cursor);
    }, []);

    // Expose API
    useImperativeHandle(ref, () => ({ write, writeln, clear }), [write, writeln, clear]);

    // Call onReady once on mount (write / writeln / clear are stable callbacks)
    const onReadyCalledRef = useRef(false);
    useEffect(() => {
      if (!onReadyCalledRef.current && onReady) {
        onReadyCalledRef.current = true;
        onReady({ write, writeln, clear });
      }
    }, [onReady, write, writeln, clear]);

    // MutationObserver for auto-scroll on any DOM change (covers direct appendChild)
    useEffect(() => {
      const el = containerRef.current;
      if (!el) return;
      const observer = new MutationObserver(() => {
        el.scrollTop = el.scrollHeight;
      });
      observer.observe(el, { childList: true, characterData: true, subtree: true });
      return () => observer.disconnect();
    }, []);

    return (
      <div
        ref={containerRef}
        className={`bg-black font-mono text-[13px] leading-relaxed text-zinc-300 p-4 overflow-auto whitespace-pre-wrap break-all ${className}`}
      >
        <span className="inline-block w-2 h-4 bg-emerald-500 animate-pulse align-middle ml-0.5" aria-hidden="true" />
      </div>
    );
  }
);

export default DeployLogViewer;
