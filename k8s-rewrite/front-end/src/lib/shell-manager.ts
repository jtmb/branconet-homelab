"use client";

/**
 * Multi-instance shell manager.
 *
 * Manages multiple simultaneous shells (kubectl + pod exec).
 * Only ONE shell can be maximized at a time — opening a new shell
 * auto-minimizes the current one. Minimized shells stack as tabs.
 *
 * Usage:
 *   import { openShell, closeShell, getShells, useShells } from "@/lib/shell-manager";
 *
 *   openShell("kubectl");                      // open kubectl shell
 *   openShell("exec", "nginx-hello", "pod-1"); // open pod exec shell
 *   closeShell("__kubectl__");                 // close specific shell
 */

export type ShellType = "kubectl" | "exec";
export type ShellState = "maximized" | "minimized";

export interface ShellInstance {
  id: string;
  type: ShellType;
  namespace?: string;
  podName?: string;
  state: ShellState;
  /** Transient — true while a command is executing. Not persisted. */
  running?: boolean;
}

type Listener = () => void;

const shells = new Map<string, ShellInstance>();
let listeners: Listener[] = [];
const STORAGE_KEY = "botrus-shells";

function saveToStorage(): void {
  try {
    // Strip transient fields before persisting
    const clean = getShells().map(({ running: _, ...rest }) => rest);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(clean));
  } catch { /* quota or disabled */ }
}

function loadFromStorage(): void {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as ShellInstance[];
    for (const s of parsed) {
      // Ensure running is false on restore
      shells.set(s.id, { ...s, running: false });
    }
  } catch { /* corrupt or unavailable */ }
}

// Restore persisted shells on module init
loadFromStorage();

function notify() {
  saveToStorage();
  for (const fn of listeners) fn();
}

/** Read-only snapshot of all shells */
export function getShells(): ShellInstance[] {
  return Array.from(shells.values());
}

/** Currently maximized shell, or null */
export function getMaximized(): ShellInstance | null {
  for (const s of shells.values()) {
    if (s.state === "maximized") return s;
  }
  return null;
}

/**
 * Open (or re-open) a shell.
 * - Creates the shell if it doesn't exist
 * - Sets it to maximized
 * - Minimizes any other maximized shell
 * - Returns the shell id
 */
export function openShell(
  type: ShellType,
  namespace?: string,
  podName?: string
): string {
  const id = type === "kubectl" ? "__kubectl__" : `exec:${namespace}:${podName}`;

  // Minimize all currently maximized shells
  for (const [key, s] of shells) {
    if (s.state === "maximized") {
      shells.set(key, { ...s, state: "minimized" });
    }
  }

  const existing = shells.get(id);
  if (existing) {
    shells.set(id, { ...existing, state: "maximized" });
  } else {
    shells.set(id, { id, type, namespace, podName, state: "maximized" });
  }

  notify();
  return id;
}

/** Close a shell. If another shell exists, auto-maximizes the first one. */
export function closeShell(id: string): void {
  shells.delete(id);

  // Auto-maximize the first remaining shell
  const remaining = Array.from(shells.values());
  if (remaining.length > 0) {
    shells.set(remaining[0].id, { ...remaining[0], state: "maximized" });
  }

  notify();
}

/** Minimize a shell without closing it */
export function minimizeShell(id: string): void {
  const s = shells.get(id);
  if (s) {
    shells.set(id, { ...s, state: "minimized" });
    notify();
  }
}

/**
 * Maximize a shell — minimizes all others first.
 * If the shell doesn't exist, does nothing (tabs can only restore existing shells).
 */
export function maximizeShell(id: string): void {
  // Minimize all others
  for (const [key, s] of shells) {
    if (s.state === "maximized") {
      shells.set(key, { ...s, state: "minimized" });
    }
  }

  const s = shells.get(id);
  if (s) {
    shells.set(id, { ...s, state: "maximized" });
  }

  notify();
}

/** Subscribe to shell state changes. Returns unsubscribe function. */
export function subscribe(fn: Listener): () => void {
  listeners.push(fn);
  return () => {
    listeners = listeners.filter((l) => l !== fn);
  };
}

/** Set the running flag on a shell — triggers UI re-render. */
export function setShellRunning(id: string, running: boolean): void {
  const s = shells.get(id);
  if (s) {
    shells.set(id, { ...s, running });
    notify();
  }
}

/** React hook — returns shells array + maximized shell, re-renders on changes */
export { useShells } from "./use-shells";
