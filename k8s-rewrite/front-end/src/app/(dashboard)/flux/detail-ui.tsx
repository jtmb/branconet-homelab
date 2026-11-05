"use client";

import { useMemo, useState, type ReactNode } from "react";
import { SortHeader } from "@/components/ui/sortable-header";
import { compareValues, type SortKind } from "@/lib/table-sort";
import type { QuerySnapshot } from "@/lib/query-store";

export function formatFluxTime(value: string | null) {
  const date = new Date(value ?? "");
  return Number.isFinite(date.getTime()) ? date.toLocaleString() : "Unknown";
}

export function FluxReadNotice({ query }: { query: QuerySnapshot & { refetch: () => void } }) {
  if (!query.error && !query.stale) return null;
  return <p role="alert" className="mb-4 rounded border border-amber-800 p-3 text-amber-200">
    {query.error ?? "Flux metadata is stale."} {query.data && query.status !== 401 && query.status !== 404 ? "Showing the last successful snapshot." : "Detail unavailable."}
    <button onClick={query.refetch} className="ml-3 rounded bg-zinc-800 px-3 py-2">Retry</button>
  </p>;
}

interface Column<T> { label: string; kind?: SortKind; value: (row: T) => string | number | null; render?: (row: T) => ReactNode }
/** Only server-projected public metadata belongs in these searchable, bounded tables. */
export function FluxMetadataTable<T>({ title, rows, columns, identity }: { title: string; rows: readonly T[]; columns: Column<T>[]; identity: (row: T) => string }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState({ index: 0, direction: "asc" as "asc" | "desc" });
  const result = useMemo(() => {
    const query = search.trim().toLowerCase();
    const column = columns[sort.index] ?? columns[0];
    return rows.filter(row => !query || columns.some(item => String(item.value(row) ?? "").toLowerCase().includes(query)))
      .map((row, index) => ({ row, index }))
      .sort((left, right) => compareValues(column.value(left.row), column.value(right.row), column.kind, sort.direction)
        || identity(left.row).localeCompare(identity(right.row), undefined, { numeric: true }) || left.index - right.index);
  }, [rows, columns, identity, search, sort]);
  const pages = Math.max(1, Math.ceil(result.length / 100));
  const currentPage = Math.min(page, pages - 1);
  return <section aria-label={title} className="mb-6 rounded-xl border border-zinc-800">
    <h2 className="p-4 text-base font-semibold">{title} ({rows.length})</h2>
    <label className="mx-4 mb-4 block max-w-md text-sm">Search {title}
      <input type="search" value={search} onChange={event => { setSearch(event.target.value); setPage(0); }} className="mt-1 block w-full rounded border border-zinc-700 bg-zinc-950 p-2" />
    </label>
    <div className="overflow-x-auto" tabIndex={0} aria-label={`${title} table scroll area`}>
      <table className="w-full min-w-[32rem] text-sm">
        <caption className="sr-only">{title}; at most 100 rows per page</caption>
        <thead><tr>{columns.map((column, index) => <th key={column.label} scope="col" className="border-b border-zinc-800 p-3 text-left" aria-sort={sort.index === index ? sort.direction === "asc" ? "ascending" : "descending" : "none"}>
          <SortHeader label={column.label} active={sort.index === index} dir={sort.direction} onClick={() => { setSort({ index, direction: sort.index === index && sort.direction === "asc" ? "desc" : "asc" }); setPage(0); }} />
        </th>)}</tr></thead>
        <tbody>{result.slice(currentPage * 100, (currentPage + 1) * 100).map(({ row, index }) => <tr key={`${identity(row)}:${index}`} className="border-b border-zinc-800">
          {columns.map(column => <td key={column.label} className="max-w-md break-words p-3">{column.render ? column.render(row) : column.value(row) ?? "Unknown"}</td>)}
        </tr>)}</tbody>
      </table>
    </div>
    {!result.length && <p className="p-4">{rows.length ? "No matches." : "No entries in this successful snapshot."}</p>}
    <nav aria-label={`${title} pages`} className="flex flex-wrap items-center gap-3 p-3 text-sm">
      <button className="rounded bg-zinc-800 px-3 py-2 disabled:opacity-50" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Previous</button>
      <span>Page {currentPage + 1} of {pages}; {result.length} matches</span>
      <button className="rounded bg-zinc-800 px-3 py-2 disabled:opacity-50" disabled={currentPage + 1 >= pages} onClick={() => setPage(currentPage + 1)}>Next</button>
    </nav>
  </section>;
}
