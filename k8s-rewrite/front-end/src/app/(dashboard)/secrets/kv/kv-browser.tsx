"use client";
import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useQuery, useSession, refetchKvMetadata } from "@/lib/use-query";
import { MountForm, RegisterForm, RetentionForm } from "./kv-forms";
import { input, button, surface, usable, fresh, QueryState, CursorControls, MetadataTable, type Page, type Mount, type Path, type Capabilities, type Status, type Versions } from "./kv-ui";
const KvWorkbench = dynamic(() => import("@/components/secrets/kv-workbench"), { ssr: false, loading: () => <p role="status">Loading value and version workbench…</p> });
const KvAdministration = dynamic(() => import("@/components/secrets/kv-administration"), { ssr: false, loading: () => <p role="status">Loading administration and audit…</p> });
export default function KvBrowser() {
  const session = useSession();
  const [mountCursors, setMountCursors] = useState<string[]>([]), [pathCursors, setPathCursors] = useState<string[]>([]);
  const [mountId, setMountId] = useState(""), [search, setSearch] = useState(""), [mountSearch, setMountSearch] = useState(""), [mountEditor, setMountEditor] = useState<Mount | "new">(), [registration, setRegistration] = useState<Mount>();
  const [selected, setSelected] = useState<string>(), [message, setMessage] = useState("");
  const [administrationOpen, setAdministrationOpen] = useState(false), [administrationRefresh, setAdministrationRefresh] = useState(0);
  const administrationTrigger = useRef<HTMLButtonElement>(null);
  const closeAdministration = useCallback(() => { setAdministrationOpen(false); administrationTrigger.current?.focus(); }, []);
  const heading = useRef<HTMLHeadingElement | null>(null), searchInput = useRef<HTMLInputElement>(null), trigger = useRef<HTMLButtonElement | null>(null), formTrigger = useRef<HTMLButtonElement | null>(null);
  const mounts = useQuery<Page<Mount>>("/api/kv/mounts" + (mountCursors.length ? "?cursor=" + encodeURIComponent(mountCursors.at(-1)!) : ""));
  const pathParams = new URLSearchParams(); if (mountId) pathParams.set("mountId", mountId); if (pathCursors.length) pathParams.set("cursor", pathCursors.at(-1)!);
  const paths = useQuery<Page<Path>>("/api/kv/paths" + (pathParams.size ? "?" + pathParams : ""));
  const mountData = usable(mounts), pathData = usable(paths);
  useEffect(() => { if (!session.canWrite) setMountEditor(undefined); if (!session.canKvWrite) setRegistration(undefined); }, [session.canWrite, session.canKvWrite]);
  useEffect(() => { if (!session.data?.authenticated || session.error) setAdministrationOpen(false); }, [session.data?.authenticated, session.error]);
  const rows = (pathData?.items ?? []).filter(item => [item.path, item.namespace, item.name].some(text => text.toLowerCase().includes(search.toLowerCase())))
    .map(item => ({ id: item.id, path: item.path, namespace: item.namespace, name: item.name, fieldCount: item.fields.length, retention: item.retention }));
  function closeDetail() { setSelected(undefined); (trigger.current?.isConnected ? trigger.current : searchInput.current)?.focus(); }
  function closeForms() { setMountEditor(undefined); setRegistration(undefined); (formTrigger.current?.isConnected ? formTrigger.current : searchInput.current)?.focus(); }
  return <main className="min-w-0 space-y-6 p-3 sm:p-6"><header className="space-y-2"><h1 className="text-xl font-semibold">KV Secrets</h1>
    <p className="text-sm text-zinc-400">Mounts organize logical paths. Each path maps named fields to exact native Secret keys; values remain in Kubernetes.</p>
    <div className="flex flex-wrap gap-3"><Link href="/secrets" prefetch={false} className={button}>Native objects and aliases</Link><button className={button} onClick={() => { setAdministrationRefresh(value => value + 1); refetchKvMetadata(); }}>Refresh KV metadata</button>
      <button ref={administrationTrigger} className={button} disabled={!session.data?.authenticated || !fresh(session)} aria-expanded={administrationOpen} aria-controls="kv-administration-panel" onClick={() => { if (administrationOpen) closeAdministration(); else setAdministrationOpen(true); }}>Administration and audit</button></div></header>
    {administrationOpen && <section id="kv-administration-panel"><KvAdministration initialOpen selectedPathId={selected ?? null} refreshKey={administrationRefresh} onClose={closeAdministration} onMetadataChange={refetchKvMetadata} /></section>}
    {message && <p role="status" className="text-emerald-300">{message}</p>}
    <section aria-labelledby="kv-mounts" className={surface}><div className="flex flex-wrap items-center gap-3"><h2 id="kv-mounts" className="font-semibold">Mounts</h2>
      {session.canWrite && <button className={button} onClick={event => { formTrigger.current = event.currentTarget; setRegistration(undefined); setMountEditor("new"); }}>Create mount</button>}</div>
      <QueryState query={mounts} label="mounts" retry={mounts.refetch} />
      <label className="block max-w-md text-sm">Search mounts in this API page<input className={input} value={mountSearch} onChange={event => setMountSearch(event.target.value)} /></label>
      {mountData && <><MetadataTable label="KV mounts" rows={mountData.items.filter(item => [item.name, ...item.namespaces].some(text => text.toLowerCase().includes(mountSearch.toLowerCase()))).map(item => ({ id: item.id, name: item.name, namespaces: item.namespaces.join(", "), revision: item.revision }))}
        columns={[{ key: "name", label: "Mount" }, { key: "namespaces", label: "Namespaces" }, { key: "revision", label: "Revision", sort: "number" }]}
        actions={row => { const item = mountData.items.find(mount => mount.id === row.id)!; return <div className="flex flex-wrap gap-2"><button className={button} onClick={() => { setMountId(item.id); setPathCursors([]); setSelected(undefined); setSearch(""); }}>Browse {item.name}</button>
          {session.canWrite && <button className={button} disabled={!fresh(mounts)} onClick={event => { formTrigger.current = event.currentTarget; setRegistration(undefined); setMountEditor(item); }}>Edit {item.name}</button>}
          {session.canKvWrite && <button className={button} disabled={!fresh(mounts)} onClick={event => { formTrigger.current = event.currentTarget; setMountEditor(undefined); setRegistration(item); }}>Register path in {item.name}</button>}</div>; }} />
        {!mountData.items.some(item => [item.name, ...item.namespaces].some(text => text.toLowerCase().includes(mountSearch.toLowerCase()))) && !mounts.error && <p>{mountSearch ? "No matching permitted mounts in this API page." : "No permitted mounts in this API page."}</p>}
        <CursorControls label="mounts" cursors={mountCursors} next={mountData.nextCursor} disabled={mounts.refreshing || !!mounts.error} move={cursors => { setMountCursors(cursors); setMountSearch(""); }} /></>}
    </section>
    {session.canWrite && mountEditor && <MountForm key={typeof mountEditor === "string" ? mountEditor : mountEditor.id} original={mountEditor === "new" ? undefined : mountEditor} close={closeForms} saved={text => { setMessage(text); closeForms(); refetchKvMetadata(); }} />}
    {session.canKvWrite && registration && <RegisterForm key={registration.id} mount={registration} close={closeForms} saved={() => { setMessage("Path metadata registered. Native values were not changed; initialization/adoption remains separate."); closeForms(); refetchKvMetadata(); }} />}
    <section aria-labelledby="kv-paths" className={surface}><div className="flex flex-wrap items-center gap-3"><h2 id="kv-paths" className="font-semibold">Paths {mountId && "in selected mount"}</h2>
      {mountId && <button className={button} onClick={() => { setMountId(""); setPathCursors([]); setSelected(undefined); }}>Show all permitted paths</button>}</div>
      <label className="block max-w-md text-sm">Search paths in this API page<input ref={searchInput} className={input} value={search} onChange={event => setSearch(event.target.value)} /></label>
      <QueryState query={paths} label="paths" retry={paths.refetch} />
      {pathData && <><MetadataTable label="KV paths" rows={rows} columns={[{ key: "path", label: "Logical path" }, { key: "namespace", label: "Namespace" }, { key: "name", label: "Secret" }, { key: "fieldCount", label: "Fields", sort: "number" }, { key: "retention", label: "Retention", sort: "number" }]}
        actions={row => <button className={button} aria-label={`Open KV path ${row.path}`} onClick={event => { trigger.current = event.currentTarget; setSelected(row.id); heading.current?.focus(); }}>Open path</button>} />
        {!rows.length && !paths.error && <p>{search ? "No matching permitted paths in this API page." : "No permitted paths in this API page."}</p>}
        <CursorControls label="paths" cursors={pathCursors} next={pathData.nextCursor} disabled={paths.refreshing || !!paths.error} move={cursors => { setPathCursors(cursors); setSearch(""); }} /></>}
    </section>
    {selected && <PathDetail key={selected} id={selected} heading={heading} close={closeDetail} />}
  </main>;
}
function PathDetail({ id, heading, close }: { id: string; heading: MutableRefObject<HTMLHeadingElement | null>; close: () => void }) {
  const session = useSession(), pathQuery = useQuery<Path>("/api/kv/paths/" + id), capabilities = useQuery<Capabilities>("/api/kv/paths/" + id + "/capabilities");
  const status = useQuery<Status>("/api/kv/paths/" + id + "/status"), versions = useQuery<Versions>("/api/kv/paths/" + id + "/versions");
  const permitted = capabilities.status !== 401 && capabilities.status !== 403;
  const path = permitted ? usable(pathQuery) : undefined, caps = usable(capabilities), state = permitted ? usable(status) : undefined, history = permitted ? usable(versions) : undefined;
  const canUpdate = session.canKvWrite && fresh(pathQuery) && fresh(capabilities) && caps?.revision === path?.revision && caps?.permissions.update;
  const [workbenchOpen, setWorkbenchOpen] = useState(false), workbenchTrigger = useRef<HTMLButtonElement>(null);
  const freshCapabilities = fresh(capabilities) && caps?.pathId === id && caps.revision === path?.revision ? caps : null;
  const focusHeading = useCallback((element: HTMLHeadingElement | null) => { heading.current = element; element?.focus(); }, [heading]);
  return <section className={surface}><div className="flex flex-wrap items-center gap-3"><h2 ref={focusHeading} tabIndex={-1} className="break-all font-semibold">KV path {path?.path ?? id}</h2><button className={button} onClick={close}>Close path</button></div>
    <QueryState query={pathQuery} label="path metadata" retry={pathQuery.refetch} /><QueryState query={capabilities} label="path capabilities" retry={capabilities.refetch} />
    {path && <><p className="break-all">Native target: {path.namespace}/{path.name} · metadata revision {path.revision} · retention {path.retention}</p>
      <button ref={workbenchTrigger} className={button} disabled={!fresh(pathQuery) || !freshCapabilities} onClick={() => setWorkbenchOpen(true)}>Values and versions</button>
      <MetadataTable label="KV field mappings" rows={path.fields.map(item => ({ id: item.field, field: item.field, key: item.key }))} columns={[{ key: "field", label: "Logical field" }, { key: "key", label: "Exact native key" }]} />
      {session.canKvWrite && caps?.permissions.update && <RetentionForm path={path} editable={!!canUpdate} />}</>}
    {caps && <><p className="text-sm text-zinc-400">Allowed actions: {Object.entries(caps.permissions).filter(([, allowed]) => allowed).map(([action]) => action).join(", ") || "none"}.</p>
      <p className="text-sm text-amber-300">Native value mutations {caps.nativeMutationEnabled ? "enabled by operator assertion" : "disabled"}. External admission/RBAC verification is still required.</p></>}
    <QueryState query={status} label="native status" retry={status.refetch} />{state && <p>Native {state.adopted ? "adopted" : "unadopted"} · head {state.head} · {state.tombstone ? "tombstoned" : "not tombstoned"} · resourceVersion {state.resourceVersion}</p>}
    <QueryState query={versions} label="version metadata" retry={versions.refetch} />{history && <><MetadataTable label="KV version metadata" rows={history.items.map(item => ({ id: String(item.version), version: item.version, createdAt: item.createdAt, tombstone: item.tombstone ? "Yes" : "No" }))} columns={[{ key: "version", label: "Version", sort: "number" }, { key: "createdAt", label: "Created" }, { key: "tombstone", label: "Tombstone" }]} />
      {!history.items.length && !versions.error && <p>No committed versions in this native snapshot.</p>}</>}
    <p className="text-sm text-zinc-400">This view shows metadata. Opening it does not reveal values or initialize a path.</p>
    {workbenchOpen && path && <KvWorkbench path={path} capabilities={freshCapabilities} onClose={() => setWorkbenchOpen(false)} onMetadataRefresh={refetchKvMetadata} returnFocus={() => (workbenchTrigger.current?.isConnected ? workbenchTrigger.current : heading.current)?.focus()} />}
  </section>;
}
