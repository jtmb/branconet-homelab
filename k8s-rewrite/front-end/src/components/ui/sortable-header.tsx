"use client";

import { useState } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";

export type SortDir = "asc" | "desc";

export function useSort<K extends string>(defaultKey: K) {
  const [sort, setSort] = useState<{ key: string; dir: SortDir }>({ key: defaultKey, dir: "asc" });
  return {
    sortKey: sort.key,
    sortDir: sort.dir,
    toggle(key: string) {
      setSort(previous => ({ key, dir: previous.key === key && previous.dir === "asc" ? "desc" : "asc" }));
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
  if (!active) return <ArrowUpDown aria-hidden="true" focusable="false" className="w-3 h-3 text-zinc-600" />;
  return dir === "asc" ? (
    <ArrowUp aria-hidden="true" focusable="false" className="w-3 h-3 text-indigo-400" />
  ) : (
    <ArrowDown aria-hidden="true" focusable="false" className="w-3 h-3 text-indigo-400" />
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
      aria-label={`Sort by ${label}${active ? `, currently ${dir === "asc" ? "ascending" : "descending"}` : ""}`}
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
      aria-label={`Sort by ${label}${active ? `, currently ${dir === "asc" ? "ascending" : "descending"}` : ""}`}
      className="text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors group text-right w-full pl-4 relative"
    >
      {label}
      <span className="absolute left-0 top-1/2 -translate-y-1/2">
        <SortIcon active={active} dir={dir} />
      </span>
    </button>
  );
}
