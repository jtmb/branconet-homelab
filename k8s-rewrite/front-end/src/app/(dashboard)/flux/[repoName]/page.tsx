"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import ViewportWrapper from "../../viewport-wrapper";
import { useQuery } from "@/lib/use-query";
import type { GitRepoDetail } from "@/lib/flux";
import { FluxMetadataTable, FluxReadNotice, formatFluxTime } from "../detail-ui";

export default function GitRepoDetailPage() {
  const { repoName } = useParams<{ repoName: string }>();
  return <RepositoryDetail key={repoName} name={repoName} />;
}

function RepositoryDetail({ name }: { name: string }) {
  const query = useQuery<GitRepoDetail>(`/api/flux/repos/${encodeURIComponent(name)}/detail`);
  const detail = query.status === 401 || query.status === 404 ? undefined : query.data;
  return <ViewportWrapper><main className="px-3 py-6 sm:px-4 lg:px-6">
    <Link prefetch={false} href="/flux" className="text-indigo-400">Back to Flux</Link>
    <h1 className="page-header-title my-4 break-words">{name}</h1>
    <FluxReadNotice query={query} />
    {query.loading && !detail && <p role="status">Loading repository detail</p>}
    {query.status === 404 && <p>Repository not found in the current read.</p>}
    {detail && <>
      <p className="mb-3">{detail.status}{detail.suspended ? "; suspended" : ""}</p>
      <dl className="mb-4 grid grid-cols-1 gap-3 break-words text-sm sm:grid-cols-2">
        <div><dt className="text-zinc-400">Namespace</dt><dd>{detail.namespace}</dd></div>
        <div><dt className="text-zinc-400">Repository URL</dt><dd>{detail.url.startsWith("https://") ? <a href={detail.url} target="_blank" rel="noopener noreferrer" className="text-indigo-400">{detail.url}</a> : detail.url || "Withheld"}</dd></div>
        <div><dt className="text-zinc-400">Branch / path</dt><dd>{detail.branch} / {detail.path}</dd></div>
        <div><dt className="text-zinc-400">Last sync / revision</dt><dd>{formatFluxTime(detail.lastSync)} / {detail.revision ?? "Unknown"}</dd></div>
        <div><dt className="text-zinc-400">Ready bundles</dt><dd>{detail.bundles.filter(bundle => bundle.ready).length} / {detail.bundles.length}</dd></div>
        <div><dt className="text-zinc-400">Ready resources</dt><dd>{detail.readyResources} / {detail.totalResources}</dd></div>
      </dl>
      <p className="mb-4 text-xs text-zinc-400">Controller messages and annotations are withheld. Readiness is controller metadata, not proof of credential consumption.</p>
      <FluxMetadataTable title="Bundles" rows={detail.bundles} identity={bundle => bundle.name} columns={[
        { label: "Name", value: bundle => bundle.name, render: bundle => <Link prefetch={false} href={`/flux/${encodeURIComponent(name)}/${encodeURIComponent(bundle.name)}`} className="text-indigo-400 underline">{bundle.name}</Link> },
        { label: "State", value: bundle => bundle.status },
        { label: "Resources", kind: "number", value: bundle => bundle.totalResources },
        { label: "Last Sync", kind: "date", value: bundle => bundle.lastSync, render: bundle => formatFluxTime(bundle.lastSync) },
        { label: "Path", value: bundle => bundle.path },
        { label: "Resource Kinds", value: bundle => bundle.resourceCounts.map(item => `${item.count} ${item.kind}`).join(", ") },
      ]} />
      <FluxMetadataTable title="Conditions" rows={detail.conditions} identity={condition => condition.type} columns={[
        { label: "Type", value: condition => condition.type }, { label: "Status", value: condition => condition.status }, { label: "Reason", value: condition => condition.reason },
      ]} />
      <FluxMetadataTable title="Recent Events" rows={detail.events} identity={event => `${event.type}:${event.reason}:${event.lastTimestamp}`} columns={[
        { label: "Type", value: event => event.type }, { label: "Reason", value: event => event.reason },
        { label: "Date", kind: "date", value: event => event.lastTimestamp, render: event => formatFluxTime(event.lastTimestamp) },
      ]} />
      <FluxMetadataTable title="Labels" rows={detail.labels} identity={label => label.key} columns={[{ label: "Key", value: label => label.key }, { label: "Value", value: label => label.value }]} />
    </>}
  </main></ViewportWrapper>;
}
