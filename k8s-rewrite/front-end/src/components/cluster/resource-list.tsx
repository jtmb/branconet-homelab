"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { useQuery } from "@/lib/use-query";
import { compareValues, elapsedAge, SortKind } from "@/lib/table-sort";
import { SortHeader, useSort } from "@/components/ui/sortable-header";
import { QueryStatus } from "@/components/ui/query-status";
import ViewportWrapper from "@/app/(dashboard)/viewport-wrapper";
import ResourceActionsMenu from "@/app/(dashboard)/resource-actions-trigger";
import { ResourceType } from "@/lib/resource-capabilities";

type Row = Record<string, unknown> & { name?: string; namespace?: string };
interface Column { key: string; label: string; sort?: SortKind }
const columns: Record<string, Column[]> = {
  pods: [{ key: "status", label: "Status" }, { key: "name", label: "Name" }, { key: "namespace", label: "Namespace" }, { key: "image", label: "Image" }, { key: "ready", label: "Ready", sort: "count" }, { key: "restarts", label: "Restarts", sort: "number" }, { key: "ip", label: "IP" }, { key: "node", label: "Node" }, { key: "created", label: "Age", sort: "date" }],
  deployments: [{ key: "state", label: "State" }, { key: "name", label: "Name" }, { key: "namespace", label: "Namespace" }, { key: "image", label: "Image" }, { key: "ready", label: "Ready", sort: "count" }, { key: "upToDate", label: "Up to date", sort: "number" }, { key: "available", label: "Available", sort: "number" }, { key: "restarts", label: "Restarts", sort: "number" }, { key: "created", label: "Age", sort: "date" }, { key: "health", label: "Health" }],
  namespaces: [{ key: "name", label: "Name" }, { key: "status", label: "Status" }, { key: "age", label: "Age", sort: "age" }],
  services: [{ key: "name", label: "Name" }, { key: "namespace", label: "Namespace" }, { key: "type", label: "Type" }, { key: "clusterIP", label: "Cluster IP" }, { key: "externalIP", label: "External IP" }, { key: "ports", label: "Ports" }, { key: "selector", label: "Selector" }],
  ingresses: [{ key: "state", label: "State" }, { key: "name", label: "Name" }, { key: "namespace", label: "Namespace" }, { key: "host", label: "Host" }, { key: "target", label: "Target" }, { key: "age", label: "Age", sort: "age" }],
  volumes: [{ key: "name", label: "Name" }, { key: "namespace", label: "Namespace" }, { key: "status", label: "Status" }, { key: "capacity", label: "Capacity", sort: "quantity" }, { key: "node", label: "Node" }, { key: "storageClass", label: "Storage class" }],
};
const config: Record<string, { title: string; route: string; type?: ResourceType }> = {
  pods: { title: "Pods", route: "/pods", type: "pod" }, deployments: { title: "Deployments", route: "/deployments", type: "deployment" },
  namespaces: { title: "Namespaces", route: "/name-spaces", type: "namespace" }, services: { title: "Services", route: "/services", type: "service" },
  ingresses: { title: "Ingresses", route: "/ingresses", type: "ingress" }, volumes: { title: "Storage", route: "/storage" },
};
interface Result { [key: string]: unknown; availability?: { state?: string }; storageClasses?: Row[] }
export default function ResourceList({ collection }: { collection: keyof typeof columns }) {
  const settings = config[collection];
  const [search, setSearch] = useState("");
  const [type, setType] = useState("all");
  const [kind, setKind] = useState("pv");
  const [namespace, setNamespace] = useState("");
  const [selector, setSelector] = useState("");
  const [filters, setFilters] = useState({ namespace: "", selector: "" });
  const queryParams = new URLSearchParams();
  if (type !== "all") queryParams.set("type", type);
  if (collection === "volumes") queryParams.set("kind", kind);
  if (collection === "pods") {
    if (filters.namespace) queryParams.set("namespace", filters.namespace);
    if (filters.selector) queryParams.set("labelSelector", filters.selector);
  }
  const query = useQuery<Result>(`/api/cluster/${collection}${queryParams.size ? "?" + queryParams : ""}`);
  const rows = Array.isArray(query.data?.[collection]) ? query.data![collection] as Row[] : [];
  const filtered = useMemo(() => rows.filter(row => Object.values(row).some(value => typeof value === "string" && value.toLowerCase().includes(search.toLowerCase()))), [rows, search]);
  const resourceType = collection === "volumes" && kind === "pvc" ? "pvc" : settings.type;
  const detail = (row: Row) => resourceType ? settings.route + (resourceType === "namespace" ? "" : "/" + encodeURIComponent(row.namespace ?? "")) + "/" + encodeURIComponent(row.name ?? "") : undefined;
  return <ViewportWrapper><main className="min-w-0 px-3 py-6 sm:px-4 lg:px-6">
    <h1 className="mb-4 text-2xl font-semibold">{settings.title}</h1>
    <div className="mb-4 flex flex-wrap items-end gap-3">
      <label className="text-sm">Search<input value={search} onChange={e => setSearch(e.target.value)} className="mt-1 block rounded border border-zinc-700 bg-zinc-900 p-2" /></label>
      {(collection === "pods" || collection === "volumes") && <label className="text-sm">Type<select value={type} onChange={e => setType(e.target.value)} className="mt-1 block rounded border border-zinc-700 bg-zinc-900 p-2">
        {(collection === "pods" ? ["all", "app", "system"] : ["all", "local", "nfs", "samba", "longhorn"]).map(item => <option key={item}>{item}</option>)}</select></label>}
      {collection === "volumes" && <label className="text-sm">Resource<select value={kind} onChange={e => setKind(e.target.value)} className="mt-1 block rounded border border-zinc-700 bg-zinc-900 p-2"><option value="pv">Persistent volumes</option><option value="pvc">Claims</option></select></label>}
    </div>
    {collection === "pods" && <form className="mb-4 flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); setFilters({ namespace: namespace.trim(), selector: selector.trim() }); }}>
      <label className="text-sm">Namespace<input value={namespace} onChange={e => setNamespace(e.target.value)} placeholder="All namespaces" className="mt-1 block rounded border border-zinc-700 bg-zinc-900 p-2" /></label>
      <label className="text-sm">Label selector<input value={selector} onChange={e => setSelector(e.target.value)} placeholder="app=web,tier in (front,api)" className="mt-1 block rounded border border-zinc-700 bg-zinc-900 p-2" /></label>
      <button className="rounded bg-indigo-600 px-3 py-2">Apply filters</button>
    </form>}
    <QueryStatus query={query} />
    {query.loading ? <p role="status" className="flex items-center gap-2"><Loader2 className="h-5 w-5 animate-spin" />Loading resources…</p>
      : !query.data ? <p className="text-zinc-400">Resource data is unavailable.</p>
      : <ResourceTable rows={filtered} columns={columns[collection]} detail={detail} type={resourceType} resetKey={search + type + kind + JSON.stringify(filters)} />}
    {collection === "volumes" && query.data?.storageClasses && <section className="mt-6"><h2 className="mb-3 text-lg">Storage classes</h2><ResourceTable rows={query.data.storageClasses}
      columns={[{ key: "name", label: "Name" }, { key: "provisioner", label: "Provisioner" }, { key: "isDefault", label: "Default" }]} resetKey="" /></section>}
    {collection === "deployments" && <p className="mt-4 text-sm text-zinc-400">Pod ownership follows controller UIDs. Unavailable ownership data is shown as —. Flux may restore Git desired state after runtime operations.</p>}
  </main></ViewportWrapper>;
}
export function ResourceTable({ rows, columns: fields, detail, type, resetKey, renderActions }: {
  rows: Row[]; columns: Column[]; detail?: (row: Row) => string | undefined; type?: ResourceType; resetKey: string; renderActions?: (row: Row) => React.ReactNode;
}) {
  const { sortKey, sortDir, toggle } = useSort(fields[0]?.key ?? "name");
  const [paging, setPaging] = useState({ page: 1, key: "" });
  const key = resetKey + sortKey + sortDir;
  const totalPages = Math.max(1, Math.ceil(rows.length / 100));
  const page = Math.min(paging.key === key ? paging.page : 1, totalPages);
  const column = fields.find(field => field.key === sortKey);
  const sorted = useMemo(() => [...rows].sort((a, b) => compareValues(a[sortKey], b[sortKey], column?.sort, sortDir)
    || compareValues(a.name, b.name) || compareValues(a.namespace, b.namespace)), [rows, sortKey, sortDir, column?.sort]);
  if (!rows.length) return <p className="rounded-lg border border-zinc-800 p-6 text-zinc-400">No matching resources in this snapshot.</p>;
  return <>
    <div className="overflow-x-auto rounded-lg border border-zinc-800"><table className="w-full text-sm"><thead><tr>
      {fields.map(field => <th key={field.key} aria-sort={sortKey === field.key ? sortDir === "asc" ? "ascending" : "descending" : "none"} className="whitespace-nowrap border-b border-zinc-800 px-3 py-3 text-left">
        <SortHeader label={field.label} active={sortKey === field.key} dir={sortDir} onClick={() => toggle(field.key)} /></th>)}
      {(type || renderActions) && <th className="relative px-3 text-left"><span className="sr-only">Actions</span></th>}
    </tr></thead><tbody>{sorted.slice((page - 1) * 100, page * 100).map((row, index) => <tr key={String(row.id ?? `${row.namespace}/${row.name}/${index}`)} className="border-b border-zinc-800 hover:bg-zinc-900">
      {fields.map(field => {
        const href = field.key === "name" || field.key === "hostname" ? detail?.(row) : undefined;
        const value = field.key === "created" ? elapsedAge(row[field.key]) : row[field.key] === null || row[field.key] === undefined ? "—" : String(row[field.key]);
        return <td key={field.key} className="max-w-[280px] truncate whitespace-nowrap px-3 py-3" title={value}>{href ? <Link href={href} prefetch={false} className="text-indigo-300 hover:underline">{value}</Link> : value}</td>;
      })}
      {(type || renderActions) && <td className="px-2">{type ? <ResourceActionsMenu resourceType={type} resource={row} /> : renderActions?.(row)}</td>}
    </tr>)}</tbody></table></div>
    <nav aria-label="Table pagination" className="mt-3 flex flex-wrap items-center gap-3 text-sm">
      <span>{rows.length} resources · Page {page} of {totalPages}</span>
      <button disabled={page <= 1} onClick={() => setPaging({ key, page: page - 1 })} className="rounded bg-zinc-800 px-3 py-1 disabled:opacity-40">Previous</button>
      <button disabled={page >= totalPages} onClick={() => setPaging({ key, page: page + 1 })} className="rounded bg-zinc-800 px-3 py-1 disabled:opacity-40">Next</button>
    </nav>
  </>;
}
