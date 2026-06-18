"use client";

import { useState } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";

export type SortDir = "asc" | "desc";

export function useSort<K extends string>(defaultKey: K) {
  const [sortKey, setSortKeyRaw] = useState<string>(defaultKey);
  const [sortDir, setSortDirRaw] = useState<SortDir>("asc");
  return {
    sortKey,
    sortDir,
    toggle(key: string) {
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
  className = "",
  iconFirst = false,
}: {
  label: string;
  active: boolean;
  dir: SortDir;
  onClick: () => void;
  className?: string;
  iconFirst?: boolean;
}) {
  const icon = <SortIcon active={active} dir={dir} />;
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1 text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors group ${className}`}
    >
      {iconFirst ? icon : label}
      {iconFirst ? label : icon}
    </button>
  );
}

export function SortHeaderRight({
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
      className="text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors group text-right w-full pl-4 relative"
    >
      {label}
      <span className="absolute left-0 top-1/2 -translate-y-1/2">
        <SortIcon active={active} dir={dir} />
      </span>
    </button>
  );
}
