"use client";
import { useState, type FormEvent } from "react";
import dynamic from "next/dynamic";
import { useMutation } from "@/lib/use-mutation";
import { refetchKvMetadata } from "@/lib/use-query";
import { input, button, surface, type Mount, type Path } from "./kv-ui";
const ConfirmDialog = dynamic(() => import("../../confirm-dialog"), { ssr: false });
export function MountForm({ original, close, saved }: { original?: Mount; close: () => void; saved: (text: string) => void }) {
  const mutation = useMutation(), [name, setName] = useState(original?.name ?? ""), [scopes, setScopes] = useState(original?.namespaces.join(", ") ?? ""), [remove, setRemove] = useState(false);
  const namespaces = scopes.split(/[\s,]+/).filter(Boolean);
  const valid = /^[a-z][a-z0-9-]{0,62}$/.test(name) && namespaces.length > 0 && namespaces.length <= 128 && new Set(namespaces).size === namespaces.length && namespaces.every(value => /^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$/.test(value) && value.length <= 63);
  const dirty = !original || name !== original.name || JSON.stringify(namespaces) !== JSON.stringify(original.namespaces);
  async function submit(event: FormEvent) { event.preventDefault(); if (!valid || !dirty) return; await mutation.mutate("/api/kv/mounts" + (original ? "/" + original.id : ""), { method: original ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, namespaces, ...(original ? { revision: original.revision } : {}) }) }, () => saved(original ? "Mount metadata updated." : "Mount created.")); }
  return <section className={surface}><h2 className="font-semibold">{original ? "Edit mount " + original.name : "Create mount"}</h2><p className="text-sm text-zinc-400">Enter explicit namespace scopes within the operator allowlist. This form changes metadata only.{original && " Editing revision " + original.revision + "."}</p>
    {mutation.error && !remove && <p role="alert" className="text-red-300">{mutation.error}</p>}<form className="space-y-3" onSubmit={submit}>
      <label className="block">Mount name<input className={input} value={name} onChange={event => setName(event.target.value)} disabled={mutation.busy} maxLength={63} autoFocus /></label>
      <label className="block">Allowed namespaces, separated by commas<input className={input} value={scopes} onChange={event => setScopes(event.target.value)} disabled={mutation.busy} /></label>
      <div className="flex flex-wrap gap-3"><button className={button} disabled={mutation.busy || !valid || !dirty}>Save mount</button><button type="button" className={button} disabled={mutation.busy} onClick={close}>Cancel mount edit</button>
        {original && <button type="button" className={button} disabled={mutation.busy} onClick={() => { mutation.clear(); setRemove(true); }}>Delete mount</button>}</div></form>
    {original && remove && <ConfirmDialog open title="Delete mount" message="Delete this mount's metadata and scoped policies. The server refuses removal while paths or operation history remain. Native values are retained." confirmName={original.name} confirmLabel="Delete mount" danger loading={mutation.busy} error={mutation.error} onClose={() => { setRemove(false); mutation.clear(); }}
      onConfirm={() => void mutation.mutate("/api/kv/mounts/" + original.id, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision: original.revision }) }, () => saved("Mount metadata deleted; native values retained."))} />}
  </section>;
}
export function RegisterForm({ mount, close, saved }: { mount: Mount; close: () => void; saved: () => void }) {
  const mutation = useMutation(), [path, setPath] = useState(""), [namespace, setNamespace] = useState(""), [name, setName] = useState(""), [retention, setRetention] = useState("");
  const [fields, setFields] = useState([{ field: "", key: "" }]);
  const validPath = path.length > 0 && path.length <= 512 && path.normalize("NFC") === path && !/[%\\\x00-\x20\x7f]/.test(path) && path.split("/").length <= 32 && path.split("/").every(segment => !!segment && segment !== "." && segment !== ".." && segment.length <= 128);
  const valid = validPath && !!namespace && /^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(name) && name.length <= 253 && fields.every(item => /^[A-Za-z0-9._-]{1,253}$/.test(item.field) && /^[A-Za-z0-9._-]{1,253}$/.test(item.key)) && new Set(fields.map(item => item.field)).size === fields.length && new Set(fields.map(item => item.key)).size === fields.length && (!retention || /^[1-9][0-9]*$/.test(retention) && Number(retention) <= 100);
  async function submit(event: FormEvent) { event.preventDefault(); if (!valid) return; await mutation.mutate("/api/kv/paths", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mountId: mount.id, path, namespace, name, fields, ...(retention ? { retention: Number(retention) } : {}) }) }, saved); }
  return <section className={surface}><h2 className="font-semibold">Register path in {mount.name}</h2><p className="text-sm text-zinc-400">Register metadata intent only. Native creation/adoption requires a separate administrator action and guarded mode. Specify every field/key mapping. Omitted retention uses the operator default; the server checks create policy and mount scope.</p>
    {mutation.error && <p role="alert" className="text-red-300">{mutation.error}</p>}<form className="space-y-3" onSubmit={submit}>
      <label className="block">Logical path<input className={input} value={path} onChange={event => setPath(event.target.value)} disabled={mutation.busy} maxLength={512} autoFocus /></label>
      <div className="grid gap-3 md:grid-cols-3"><label>Native namespace<select className={input} value={namespace} onChange={event => setNamespace(event.target.value)} disabled={mutation.busy}><option value="">Choose namespace</option>{mount.namespaces.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Native Secret name<input className={input} value={name} onChange={event => setName(event.target.value)} disabled={mutation.busy} maxLength={253} /></label>
        <label>Retention (optional)<input className={input} value={retention} onChange={event => setRetention(event.target.value)} disabled={mutation.busy} inputMode="numeric" /></label></div>
      <fieldset className="space-y-3"><legend>Field mappings ({fields.length}/64)</legend>{fields.map((item, index) => <div key={index} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]"><label>Field {index + 1}<input className={input} value={item.field} disabled={mutation.busy} onChange={event => setFields(previous => previous.map((value, row) => row === index ? { ...value, field: event.target.value } : value))} /></label>
        <label>Native key {index + 1}<input className={input} value={item.key} disabled={mutation.busy} onChange={event => setFields(previous => previous.map((value, row) => row === index ? { ...value, key: event.target.value } : value))} /></label>
        <button type="button" className={button} aria-label={`Remove field mapping ${index + 1}`} disabled={mutation.busy || fields.length === 1} onClick={() => setFields(previous => previous.filter((_, row) => row !== index))}>Remove</button></div>)}</fieldset>
      <div className="flex flex-wrap gap-3"><button type="button" className={button} disabled={mutation.busy || fields.length === 64} onClick={() => setFields(previous => [...previous, { field: "", key: "" }])}>Add field mapping</button><button className={button} disabled={mutation.busy || !valid}>Register metadata</button><button type="button" className={button} disabled={mutation.busy} onClick={close}>Cancel registration</button></div></form>
  </section>;
}
export function RetentionForm({ path, editable }: { path: Path; editable: boolean }) {
  const mutation = useMutation(), [snapshot, setSnapshot] = useState(path), [retention, setRetention] = useState(String(path.retention)), [saved, setSaved] = useState(false);
  const stale = snapshot.revision !== path.revision;
  const valid = editable && !stale && /^[1-9][0-9]*$/.test(retention) && Number(retention) <= 100 && Number(retention) !== snapshot.retention;
  return <form className="space-y-2" onSubmit={event => { event.preventDefault(); if (valid) void mutation.mutate<Path>("/api/kv/paths/" + path.id, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision: snapshot.revision, retention: Number(retention) }) }, data => { setSnapshot(data); setRetention(String(data.retention)); setSaved(true); refetchKvMetadata(); }); }}>
    <label className="block max-w-xs">Path retention<input className={input} value={retention} disabled={mutation.busy} onChange={event => { setRetention(event.target.value); setSaved(false); }} inputMode="numeric" /></label>
    {stale && <p role="alert" className="text-amber-300">Metadata revision changed. Reload retention to discard this draft and use the new revision. <button type="button" className={button} disabled={mutation.busy || !editable} onClick={() => { setSnapshot(path); setRetention(String(path.retention)); mutation.clear(); setSaved(false); }}>Reload retention</button></p>}
    <button className={button} disabled={!valid || mutation.busy}>Save retention</button>{saved && <p role="status">Retention metadata saved.</p>}{mutation.error && <p role="alert" className="text-red-300">{mutation.error}</p>}
  </form>;
}
