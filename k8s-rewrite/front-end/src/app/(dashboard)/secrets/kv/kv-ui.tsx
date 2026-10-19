"use client";
import { useMemo, type ReactNode } from "react";
import type { QuerySnapshot } from "@/lib/query-store";
import { SortHeader, useSort } from "@/components/ui/sortable-header";
import { compareValues, type SortKind } from "@/lib/table-sort";
export type Page<T> = { items: T[]; nextCursor: string | null };
export type Mount = { id: string; name: string; namespaces: string[]; revision: number };
export type Path = { id: string; mountId: string; path: string; namespace: string; name: string; fields: { field: string; key: string }[]; retention: number; revision: number };
export type Capabilities = { pathId: string; revision: number; permissions: Record<string, boolean>; nativeMutationEnabled: boolean; initializationAllowed: boolean; guardVerification: string };
export type Status = { adopted: boolean; uid: string; resourceVersion: string; head: number; tombstone: boolean; versions: number };
export type Versions = { items: { version: number; name: string; uid: string; createdAt: string; tombstone: boolean }[]; head: number; uid: string; resourceVersion: string };
export const input = "mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm";
export const button = "rounded-lg border border-indigo-500/20 bg-indigo-500/10 px-3 py-2 text-sm text-indigo-300 disabled:opacity-40";
export const surface = "min-w-0 space-y-3 rounded-lg border border-zinc-800 p-4";
export function usable<T>(query: QuerySnapshot<T>) { return query.status === 401 || query.status === 403 ? undefined : query.data; }
export function fresh(query: QuerySnapshot) { return !!query.data && !query.error && !query.stale && Date.now() - query.updatedAt < 15000; }
export function QueryState({ query, label, retry }: { query: QuerySnapshot; label: string; retry: () => void }) {
  return <>{query.loading && <p role="status">Loading {label}…</p>}{!query.loading && query.refreshing && <p role="status">Refreshing {label}…</p>}{query.error && <p role="alert" className="text-amber-300">{label} unavailable: {query.error}{!!usable(query) && " Previously loaded metadata is shown."} <button className={button} onClick={retry}>Retry {label}</button></p>}</>;
}
export function CursorControls({ label, cursors, next, disabled, move }: { label: string; cursors: string[]; next?: string | null; disabled: boolean; move: (cursors: string[]) => void }) {
  return <nav aria-label={`${label} API pages`} className="flex flex-wrap items-center gap-3 text-sm"><span>API page {cursors.length + 1} · up to 100 records · sort/search this page</span>
    <button className={button} disabled={disabled || !cursors.length} onClick={() => move(cursors.slice(0, -1))}>Previous {label} page</button>
    <button className={button} disabled={disabled || !next} onClick={() => { if (next) move([...cursors, next]); }}>Next {label} page</button></nav>;
}
type Row = Record<string, string | number> & { id: string };
export function MetadataTable({ label, rows, columns, actions }: { label: string; rows: Row[]; columns: { key: string; label: string; sort?: SortKind }[]; actions?: (row: Row) => ReactNode }) {
  const { sortKey, sortDir, toggle } = useSort(columns[0].key);
  const column = columns.find(item => item.key === sortKey);
  const sorted = useMemo(() => [...rows].sort((a, b) => compareValues(a[sortKey], b[sortKey], column?.sort, sortDir) || a.id.localeCompare(b.id)), [rows, sortKey, sortDir, column?.sort]);
  return <div className="overflow-x-auto rounded-lg border border-zinc-800"><table aria-label={label} className="w-full text-sm"><thead><tr>
    {columns.map(item => <th key={item.key} aria-sort={sortKey === item.key ? sortDir === "asc" ? "ascending" : "descending" : "none"} className="whitespace-nowrap px-3 py-3 text-left"><SortHeader label={item.label} active={sortKey === item.key} dir={sortDir} onClick={() => toggle(item.key)} /></th>)}
    {actions && <th className="relative px-3"><span className="sr-only">Actions</span></th>}</tr></thead><tbody>{sorted.slice(0, 100).map(row => <tr key={row.id} className="border-t border-zinc-800">
      {columns.map(item => <td key={item.key} className="max-w-md break-all px-3 py-2">{row[item.key]}</td>)}{actions && <td className="px-3 py-2">{actions(row)}</td>}</tr>)}</tbody></table></div>;
}
