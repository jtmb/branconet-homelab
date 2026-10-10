"use client";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useQuery, useSession } from "@/lib/use-query";
import { useMutation } from "@/lib/use-mutation";
import { ResourceTable } from "@/components/cluster/resource-list";
import dynamic from "next/dynamic";
const ConfirmDialog = dynamic(() => import("../confirm-dialog"), { ssr: false });
type Summary = {
  namespace: string;
  name: string;
  keys: string[];
  type: string;
  immutable: boolean;
  resourceVersion: string;
};
type Ref = { alias: string; namespace: string; name: string; key: string };
type Target = { namespace: string; name: string; key: string; resourceVersion: string };
const blank: Target = { namespace: "", name: "", key: "", resourceVersion: "" };
const input =
  "bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm w-full";
const button =
  "rounded-lg bg-indigo-500/10 border border-indigo-500/20 px-3 py-2 text-sm text-indigo-300 disabled:opacity-40";
const secretColumns = [{ key: "namespace", label: "Namespace" }, { key: "name", label: "Secret" }, { key: "type", label: "Type" },
  { key: "keyCount", label: "Key count", sort: "number" as const }, { key: "immutableDisplay", label: "Immutable" }];
const keyColumns = [{ key: "name", label: "Key" }];
export default function SecretsEditor() {
  const session = useSession();
  const canWrite = session.canWrite;
  const reveal = useRef({ allowed: canWrite, epoch: 0, mounted: false });
  if (reveal.current.allowed !== canWrite) { reveal.current.allowed = canWrite; reveal.current.epoch++; }
  useEffect(() => { const state = reveal.current; state.mounted = true; return () => { state.mounted = false; state.epoch++; }; }, []);
  const [aliasPages, setAliasPages] = useState<string[]>([]);
  const aliasCursor = aliasPages.at(-1);
  const secretQuery = useQuery<{ secrets: Summary[] }>("/api/secrets");
  const aliasQuery = useQuery<{ references: Ref[]; nextCursor: string | null }>(
    `/api/secret-references${aliasCursor ? `?cursor=${encodeURIComponent(aliasCursor)}` : ""}`,
  );
  const secrets = secretQuery.data?.secrets ?? [], refs = aliasQuery.data?.references ?? [];
  const refetchSecrets = secretQuery.refetch, refetchAliases = aliasQuery.refetch;
  const [search, setSearch] = useState(""), [keySearch, setKeySearch] = useState("");
  const [keyList, setKeyList] = useState<Pick<Summary, "namespace" | "name">>();
  const keyHeading = useRef<HTMLHeadingElement>(null), editorHeading = useRef<HTMLHeadingElement>(null), objectSearch = useRef<HTMLInputElement>(null);
  const keyTrigger = useRef<HTMLButtonElement | null>(null);
  const keyListId = keyList ? JSON.stringify([keyList.namespace, keyList.name]) : "";
  useEffect(() => { if (keyListId) keyHeading.current?.focus(); }, [keyListId]);
  const keySecret = keyList && secrets.find(secret => secret.namespace === keyList.namespace && secret.name === keyList.name);
  const secretRows = useMemo(() => (secretQuery.data?.secrets ?? []).filter(secret => [secret.namespace, secret.name, secret.type].some(text => text.toLowerCase().includes(search.toLowerCase())))
    .map(secret => ({ id: JSON.stringify([secret.namespace, secret.name]), namespace: secret.namespace, name: secret.name, type: secret.type,
      keyCount: secret.keys.length, immutableDisplay: secret.immutable ? "Yes" : "No" })), [secretQuery.data, search]);
  const keyRows = useMemo(() => (keySecret?.keys ?? []).filter(key => key.toLowerCase().includes(keySearch.toLowerCase())).map(key => ({ id: key, name: key })), [keySecret, keySearch]);
  const [target, setTarget] = useState<Target>(blank);
  const [value, setValue] = useState(""),
    [mode, setMode] = useState("create"),
    [alias, setAlias] = useState("");
  const [entered, setEntered] = useState(false), [emptyIntent, setEmptyIntent] = useState(false);
  const [deleting, setDeleting] = useState<{ kind: "key"; target: Target } | { kind: "alias"; alias: string }>();
  const [message, setMessage] = useState("");
  const mutation = useMutation(), busy = mutation.busy;
  const canSave = !!target.namespace && !!target.name && !!target.key && (mode === "create" || !!target.resourceVersion)
    && (emptyIntent || entered && value !== "");
  useEffect(() => { if (!canWrite) { setValue(""); setEntered(false); setEmptyIntent(false); setDeleting(undefined); setAlias(""); setTarget(blank); } }, [canWrite]);
  const refresh = useCallback(() => {
    refetchSecrets();
    refetchAliases();
  }, [refetchSecrets, refetchAliases]);
  function clearValue() {
    reveal.current.epoch++;
    setValue(""); setEntered(false); setEmptyIntent(false);
  }
  function perform<T>(url: string, init: RequestInit, success: (result: T) => void) {
    if (!reveal.current.allowed || busy) return;
    const epoch = reveal.current.epoch;
    setMessage("");
    void mutation.mutate<T>(url, init, result => {
      if (!reveal.current.mounted || !reveal.current.allowed) return;
      if (init.method && init.method !== "GET") refresh();
      if (epoch !== reveal.current.epoch) { setMessage("Request finished. Refresh and select the target to check its current state."); return; }
      success(result);
    });
  }
  function select(secret: Summary, key: string) {
    setTarget({
      namespace: secret.namespace,
      name: secret.name,
      key,
      resourceVersion: secret.resourceVersion,
    });
    setMode("update");
    clearValue(); setAlias(""); mutation.clear(); setMessage("");
    editorHeading.current?.focus();
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!canWrite || !canSave) return;
    perform<{ secret: Summary }>("/api/secrets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...target, value: emptyIntent ? "" : value, mode }),
      }, result => {
      setTarget((current) => ({
        ...current,
        resourceVersion: result.secret.resourceVersion,
      }));
      setMode("update");
      clearValue();
      setMessage("Native key saved.");
    });
  }
  return (
    <div className="min-w-0 p-3 sm:p-6 space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Kubernetes Secrets</h1>
        <p className="text-sm text-zinc-400">
          Values are read and saved directly in Kubernetes. Open the key list for a Secret, then select a key to edit.
        </p>
      </header>
      {message && (
        <p
          role="status"
          className="border border-zinc-800 rounded-lg p-3 text-sm text-amber-300"
        >
          {message}
        </p>
      )}
      <button
        className={button}
        disabled={busy}
        onClick={refresh}
      >
        Refresh
      </button>
      {mutation.error && <p role="alert" className="text-sm text-red-300">{mutation.error} Refresh metadata and select the target before an explicit retry; the draft has not been retried.</p>}
      {!canWrite && (
        <p className="text-sm text-zinc-400">
          Readonly and scoped users can view metadata. Flat value access requires engine administration.
        </p>
      )}
      {secretQuery.error && <p role="alert" className="text-sm text-amber-300">Secret metadata unavailable: {secretQuery.error}{secretQuery.data && " Previously loaded metadata is shown."}</p>}
      <section aria-labelledby="secret-objects-heading" className="min-w-0 space-y-3">
        <h2 id="secret-objects-heading" className="font-semibold">Secret objects</h2>
        <label className="block max-w-md text-sm">Search Secrets<input ref={objectSearch} className={input} value={search} onChange={event => setSearch(event.target.value)} /></label>
        {!secrets.length ? <p role="status" className="text-sm text-zinc-400">{secretQuery.loading ? "Loading Secret metadata…" : secretQuery.error ? "Secret metadata could not be loaded." : "No Secrets in the configured scope."}</p>
          : <ResourceTable label="Secret objects" rows={secretRows} columns={secretColumns} resetKey={search} renderActions={row => <button type="button" className={button}
            aria-label={`View keys for ${row.namespace}/${row.name}`} onClick={event => { keyTrigger.current = event.currentTarget; setKeyList({ namespace: row.namespace!, name: row.name! }); setKeySearch(""); keyHeading.current?.focus(); }}>View keys</button>} />}
      </section>
      {keyList && <section aria-labelledby="secret-keys-heading" className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center gap-3"><h2 ref={keyHeading} tabIndex={-1} id="secret-keys-heading" className="break-all font-semibold">Keys in {keyList.namespace}/{keyList.name}</h2>
          <button type="button" className={button} onClick={() => { setKeyList(undefined); setKeySearch(""); (keyTrigger.current?.isConnected ? keyTrigger.current : objectSearch.current)?.focus(); }}>Close key list</button></div>
        {keySecret ? <>
          <label className="block max-w-md text-sm">Search keys<input className={input} value={keySearch} onChange={event => setKeySearch(event.target.value)} /></label>
          <ResourceTable key={keyListId} label="Secret keys" rows={keyRows} columns={keyColumns} resetKey={keySearch} renderActions={row => <button type="button" className={button}
            disabled={!canWrite || busy || keySecret.immutable} aria-label={`Select key ${row.name} in ${keyList.namespace}/${keyList.name}`} onClick={() => select(keySecret, row.name!)}>Select key</button>} />
          {keySecret.immutable && <p className="text-sm text-zinc-400">This Secret is immutable; its keys cannot be edited here.</p>}
        </> : <p role="status" className="text-sm text-zinc-400">This Secret is absent from the loaded metadata snapshot. Refresh to check its current state.</p>}
      </section>}
      {canWrite && (
        <section className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 space-y-4">
          <h2 ref={editorHeading} tabIndex={-1} className="font-semibold">Edit a Secret key</h2>
          <form onSubmit={save} className="space-y-3">
            <div className="grid gap-3 md:grid-cols-3">
              {(["namespace", "name", "key"] as const).map((field) => (
                <label className="text-sm text-zinc-400" key={field}>
                  {field === "name" ? "Secret name" : field}
                  <input
                    className={input}
                    required
                    disabled={busy}
                    value={target[field]}
                    onChange={(e) => {
                      setTarget({
                        ...target,
                        [field]: e.target.value,
                        resourceVersion: "",
                      });
                      clearValue(); setAlias("");
                      setMode("create");
                    }}
                  />
                </label>
              ))}
            </div>
            <label className="block text-sm text-zinc-400">
              Action
              <select
                className={input}
                value={mode}
                disabled={busy}
                onChange={(e) => { setMode(e.target.value); clearValue(); }}
              >
                <option value="create">Create new key (refuse existing)</option>
                <option value="update">Update selected key</option>
              </select>
            </label>
            <label className="block text-sm text-zinc-400">
              Value
              <textarea
                className={`${input} min-h-24`}
                autoComplete="off"
                spellCheck={false}
                disabled={busy || emptyIntent}
                value={value}
                onChange={(e) => { setValue(e.target.value); setEntered(true); setEmptyIntent(false); }}
              />
            </label>
            <p className="text-xs text-zinc-500">
              Selection and reveal do not prepare a replacement. Enter a new value or explicitly choose an empty value. Updates use the selected version; conflicts require review and an explicit retry.
            </p>
            <label className="flex items-start gap-2 text-sm text-zinc-400">
              <input type="checkbox" checked={emptyIntent} disabled={busy} onChange={e => { clearValue(); setEmptyIntent(e.target.checked); }} />
              Intentionally save an empty value
            </label>
            <div className="flex flex-wrap gap-3">
              <button
                className={button}
                disabled={
                  busy || !canSave
                }
              >
                Save key
              </button>
              <button
                type="button"
                className={button}
                disabled={busy || !target.resourceVersion}
                onClick={() =>
                  perform<{ value: string; resourceVersion: string }>(
                      `/api/secrets?${new URLSearchParams(target)}`,
                    { method: "GET" }, result => {
                    setValue(result.value);
                    setEntered(false); setEmptyIntent(false);
                    setTarget((current) => ({
                      ...current,
                      resourceVersion: result.resourceVersion,
                    }));
                  })
                }
              >
                Reveal current value
              </button>
              <button
                type="button"
                className={button}
                onClick={() => { clearValue(); setMessage("Display and draft cleared." + (busy ? " The current request may still finish; inspect its outcome." : "")); }}
              >
                Clear display and draft
              </button>
              <button
                type="button"
                className={`${button} text-red-300`}
                disabled={busy || !target.resourceVersion}
                onClick={() =>
                  { clearValue(); mutation.clear(); setDeleting({ kind: "key", target: { ...target } }); }
                }
              >
                Delete selected key
              </button>
            </div>
          </form>
          <form
            className="space-y-3 border-t border-zinc-800 pt-4"
            onSubmit={(event) => {
              event.preventDefault();
              perform("/api/secret-references", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    alias,
                    namespace: target.namespace,
                    name: target.name,
                    key: target.key,
                  }),
                }, () => {
                setAlias("");
                setMessage("Lookup alias registered.");
              });
            }}
          >
            <label className="text-sm text-zinc-400">
              Alias for this namespace / Secret / key
              <input
                required
                disabled={busy}
                className={input}
                value={alias}
                onChange={(e) => setAlias(e.target.value)}
              />
            </label>
            <button className={button} disabled={busy || !target.key}>
              Register alias
            </button>
          </form>
        </section>
      )}
      <section>
        <h2 className="font-semibold mb-2">Lookup aliases</h2>
        {aliasQuery.error && <p role="alert" className="text-sm text-amber-300">Alias metadata unavailable: {aliasQuery.error}{aliasQuery.data && " Previously loaded aliases are shown."}</p>}
        <nav aria-label="Alias pages" className="flex flex-wrap items-center gap-3 mb-3">
          <button type="button" className={button} disabled={busy || aliasPages.length === 0 || aliasQuery.refreshing} onClick={() => setAliasPages(pages => pages.slice(0, -1))}>Previous aliases</button>
          <p role="status" className="text-sm text-zinc-400">Page {aliasPages.length + 1} · {refs.length} aliases{aliasQuery.refreshing && " · Loading…"}</p>
          <button type="button" className={button} disabled={busy || !aliasQuery.data?.nextCursor || !!aliasQuery.error || aliasQuery.refreshing} onClick={() => { const cursor = aliasQuery.data?.nextCursor; if (cursor) setAliasPages(pages => [...pages, cursor]); }}>Next aliases</button>
        </nav>
        {!refs.length && <p className="text-sm text-zinc-400">{aliasQuery.loading ? "Loading alias metadata…" : aliasQuery.error ? "Alias metadata could not be loaded." : "No aliases on this page."}</p>}
        <ul className="space-y-1 text-sm text-zinc-400">
          {refs.map((ref) => (
            <li key={ref.alias}>
              {ref.alias} → {ref.namespace} / {ref.name} / {ref.key}
              {canWrite && (
                <button
                  className="ml-3 text-red-300"
                  disabled={busy}
                  onClick={() => { clearValue(); mutation.clear(); setDeleting({ kind: "alias", alias: ref.alias }); }}
                >
                  Remove DB alias
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>
      {deleting && canWrite && <ConfirmDialog key={deleting.kind === "key" ? JSON.stringify(deleting.target) : deleting.alias} open danger loading={busy} error={mutation.error}
        title={deleting.kind === "key" ? "Delete selected Secret key" : "Remove DB alias"}
        message={deleting.kind === "key" ? "Delete only this key using its selected resourceVersion. The Secret object and unrelated keys are retained." : "Remove only the SQLite reference. Native values are retained; file references require operator changes."}
        confirmName={deleting.kind === "key" ? `${deleting.target.namespace}/${deleting.target.name}/${deleting.target.key}` : deleting.alias}
        confirmLabel={deleting.kind === "key" ? "Delete key" : "Remove alias"}
        onClose={() => { if (!busy) { setDeleting(undefined); mutation.clear(); } }}
        onConfirm={() => {
          if (deleting.kind === "key") perform("/api/secrets", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify(deleting.target) }, () => {
            setDeleting(undefined); clearValue(); setTarget(current => ({ ...current, resourceVersion: "" })); setMode("create"); setMessage("Key deleted; object retained.");
          });
          else perform(`/api/secret-references?alias=${encodeURIComponent(deleting.alias)}`, { method: "DELETE" }, () => {
            setDeleting(undefined); setMessage("DB reference removed. File references must be edited by the operator.");
          });
        }} />}
    </div>
  );
}
