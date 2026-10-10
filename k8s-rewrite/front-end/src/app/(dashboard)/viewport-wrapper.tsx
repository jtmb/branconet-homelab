"use client";

import { useState, useEffect } from "react";

export type ViewMode = "comfortable" | "full";

const STORAGE_KEY = "k8s-view-mode";
const DEFAULT: ViewMode = "comfortable";

const MAX_W: Record<ViewMode, string> = {
  comfortable: "max-w-[90%]",
  full: "max-w-full",
};

function readMode(): ViewMode {
  if (typeof window === "undefined") return DEFAULT;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "comfortable" || stored === "full") return stored;
  return DEFAULT;
}

export default function ViewportWrapper({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<ViewMode>(DEFAULT);

  useEffect(() => {
    setMode(readMode());
    function onChanged() {
      setMode(readMode());
    }
    window.addEventListener("k8s-viewport-changed", onChanged);
    window.addEventListener("storage", onChanged);
    return () => {
      window.removeEventListener("k8s-viewport-changed", onChanged);
      window.removeEventListener("storage", onChanged);
    };
  }, []);

  return <div className={`mx-auto w-full ${MAX_W[mode]}`}>{children}</div>;
}

/** Write mode from settings — call then dispatch event so wrapper re-renders */
export function setViewMode(mode: ViewMode) {
  localStorage.setItem(STORAGE_KEY, mode);
  window.dispatchEvent(new CustomEvent("k8s-viewport-changed"));
}
