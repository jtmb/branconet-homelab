"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import ViewportWrapper from "../../../viewport-wrapper";
import { useQuery } from "@/lib/use-query";
import type { KustomizationDetail } from "@/lib/flux";
import { FluxMetadataTable, FluxReadNotice, formatFluxTime } from "../../detail-ui";

function resourceLink(kind: string, name: string, namespace: string): string | null {
  const routes: Record<string, string> = { Deployment: "deployments", Service: "services", Ingress: "ingresses", PersistentVolumeClaim: "storage" };
  return routes[kind] ? `/${routes[kind]}/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}` : null;
}

export default function BundleDetailPage() {
  const { repoName, bundleName } = useParams<{ repoName: string; bundleName: string }>();
  return <BundleDetail key={`${repoName}/${bundleName}`} repository={repoName} name={bundleName} />;
}

function BundleDetail({ repository, name }: { repository: string; name: string }) {
  const query = useQuery<KustomizationDetail>(`/api/flux/kustomizations/${encodeURIComponent(name)}`);
  const detail = query.status === 401 || query.status === 404 ? undefined : query.data;
  return <ViewportWrapper><main className="px-3 py-6 sm:px-4 lg:px-6">
    <nav aria-label="Flux breadcrumb" className="flex flex-wrap gap-3 text-sm"><Link prefetch={false} href="/flux" className="text-indigo-400">Flux</Link><Link prefetch={false} href={`/flux/${encodeURIComponent(repository)}`} className="text-indigo-400">{repository}</Link></nav>
    <h1 className="page-header-title my-4 break-words">{name}</h1>
    <FluxReadNotice query={query} />
    {query.loading && !detail && <p role="status">Loading bundle detail</p>}
    {query.status === 404 && <p>Kustomization not found in the current read.</p>}
    {detail && <>
      <p className="mb-3">{detail.status}{detail.suspended ? "; suspended" : ""}</p>
      <dl className="mb-4 grid grid-cols-1 gap-3 break-words text-sm sm:grid-cols-2">
        <div><dt className="text-zinc-400">Source</dt><dd>{detail.sourceRef.kind}/{detail.sourceRef.name}</dd></div>
        <div><dt className="text-zinc-400">Namespace</dt><dd>{detail.namespace}</dd></div>
        <div><dt className="text-zinc-400">Path</dt><dd>{detail.path}</dd></div>
        <div><dt className="text-zinc-400">Last sync / revision</dt><dd>{formatFluxTime(detail.lastSync)} / {detail.revision ?? "Unknown"}</dd></div>
      </dl>
      <p className="mb-4 text-xs text-zinc-400">Inventory lists controller-managed metadata; readiness does not prove credential consumption. Controller messages and annotations are withheld.</p>
      <FluxMetadataTable title="Managed Resources" rows={detail.resources} identity={resource => `${resource.apiGroup}:${resource.kind}:${resource.namespace}:${resource.name}`} columns={[
        { label: "Name", value: resource => resource.name, render: resource => { const link = resourceLink(resource.kind, resource.name, resource.namespace); return link ? <Link prefetch={false} href={link} className="text-indigo-400 underline">{resource.name}</Link> : resource.name; } },
        { label: "Kind", value: resource => resource.kind }, { label: "Namespace", value: resource => resource.namespace }, { label: "API Group", value: resource => resource.apiGroup || "core" },
      ]} />
      <FluxMetadataTable title="Conditions" rows={detail.conditions} identity={condition => condition.type} columns={[
        { label: "Type", value: condition => condition.type }, { label: "Status", value: condition => condition.status }, { label: "Reason", value: condition => condition.reason },
      ]} />
      <FluxMetadataTable title="Recent Events" rows={detail.events} identity={event => `${event.type}:${event.reason}:${event.lastTimestamp}`} columns={[
        { label: "Type", value: event => event.type }, { label: "Reason", value: event => event.reason }, { label: "Date", kind: "date", value: event => event.lastTimestamp, render: event => formatFluxTime(event.lastTimestamp) },
      ]} />
    </>}
  </main></ViewportWrapper>;
}
