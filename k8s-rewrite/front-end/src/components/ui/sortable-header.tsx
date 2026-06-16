"use client";

import { useState } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";

export type SortDir = "asc" | "desc";

export function useSort<K extends string>(defaultKey: K) {
  const [sortKey, setSortKeyRaw] = useState<K>(defaultKey);
  const [sortDir, setSortDirRaw] = useState<SortDir>("asc");
  // Use module-level workaround; we need import in the component
  return {
    sortKey,
    sortDir,
    toggle(key: K) {
      setSortKeyRaw((prev) => {
        if (prev === key) {
          setSortDirRaw((d) => (d === "asc" ? "desc" : "asc"));
          return prev;
        }
        setSortDirRaw("asc");
        return key;
      });
    },
  };
}

export function SortIcon({
  active,
  dir,
}: {
  active: boolean;
  dir: SortDir;
}) {
  if (!active) return <ArrowUpDown className="w-3 h-3 text-zinc-600" />;
  return dir === "asc" ? (
    <ArrowUp className="w-3 h-3 text-indigo-400" />
  ) : (
    <ArrowDown className="w-3 h-3 text-indigo-400" />
  );
}

export function SortHeader({
  label,
  active,
  dir,
  onClick,
}: {
  label: string;
  active: boolean;
  dir: SortDir;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1 text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors group"
    >
      {label}
      <SortIcon active={active} dir={dir} />
    </button>
  );
}
