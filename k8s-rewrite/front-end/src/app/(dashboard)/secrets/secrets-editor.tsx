"use client";
import { useCallback, useEffect, useState, type FormEvent } from "react";
type Summary = {
  namespace: string;
  name: string;
  keys: string[];
  type: string;
  immutable: boolean;
  resourceVersion: string;
};
type Ref = { alias: string; namespace: string; name: string; key: string };
const input =
  "bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm w-full";
const button =
  "rounded-lg bg-indigo-500/10 border border-indigo-500/20 px-3 py-2 text-sm text-indigo-300 disabled:opacity-40";
async function api(url: string, init?: RequestInit) {
  const response = await fetch(url, { ...init, cache: "no-store" });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed");
  return result;
}
export default function SecretsEditor({ canWrite }: { canWrite: boolean }) {
  const [secrets, setSecrets] = useState<Summary[]>([]),
    [refs, setRefs] = useState<Ref[]>([]);
  const [target, setTarget] = useState({
    namespace: "",
    name: "",
    key: "",
    resourceVersion: "",
  });
  const [value, setValue] = useState(""),
    [mode, setMode] = useState("create"),
    [alias, setAlias] = useState("");
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    const [a, b] = await Promise.all([
      api("/api/secrets"),
      api("/api/secret-references"),
    ]);
    setSecrets(a.secrets);
    setRefs(b.references);
  }, []);
  useEffect(() => {
    refresh().catch((error) => setMessage(error.message));
  }, [refresh]);
  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await action();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  function select(secret: Summary, key: string) {
    setTarget({
      namespace: secret.namespace,
      name: secret.name,
      key,
      resourceVersion: secret.resourceVersion,
    });
    setMode("update");
    setValue("");
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    await perform(async () => {
      const result = await api("/api/secrets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...target, value, mode }),
      });
      setTarget((current) => ({
        ...current,
        resourceVersion: result.secret.resourceVersion,
      }));
      setMode("update");
      setValue("");
      setMessage("Native key saved.");
      await refresh();
    });
  }
  return (
    <div className="p-6 space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Kubernetes Secrets</h1>
        <p className="text-sm text-zinc-400">
          Values are read and saved directly in Kubernetes. Select a key to
          edit.
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
        onClick={() => perform(refresh)}
      >
        Refresh
      </button>
      {!canWrite && (
        <p className="text-sm text-zinc-400">
          Readonly users can view metadata. Value access requires write
          permission.
        </p>
      )}
      <div className="overflow-x-auto border border-zinc-800 rounded-lg">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-zinc-400">
              <th className="p-3">Namespace / Secret</th>
              <th>Type</th>
              <th>Keys</th>
            </tr>
          </thead>
          <tbody>
            {secrets.map((secret) => (
              <tr
                className="border-t border-zinc-800 hover:bg-zinc-800/30"
                key={`${secret.namespace}/${secret.name}`}
              >
                <td className="p-3">
                  {secret.namespace} / {secret.name}
                  {secret.immutable && " (immutable)"}
                </td>
                <td>{secret.type}</td>
                <td>
                  {secret.keys.map((key) => (
                    <button
                      className="text-indigo-300 mr-3 py-2"
                      key={key}
                      disabled={!canWrite || busy || secret.immutable}
                      onClick={() => select(secret, key)}
                    >
                      {key}
                    </button>
                  ))}
                </td>
              </tr>
            ))}
            {!secrets.length && (
              <tr>
                <td className="p-3 text-zinc-500" colSpan={3}>
                  No Secrets loaded. Check scope and API connection.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {canWrite && (
        <section className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 space-y-4">
          <h2 className="font-semibold">Edit a Secret key</h2>
          <form onSubmit={save} className="space-y-3">
            <div className="grid gap-3 md:grid-cols-3">
              {(["namespace", "name", "key"] as const).map((field) => (
                <label className="text-sm text-zinc-400" key={field}>
                  {field === "name" ? "Secret name" : field}
                  <input
                    className={input}
                    required
                    value={target[field]}
                    onChange={(e) => {
                      setTarget({
                        ...target,
                        [field]: e.target.value,
                        resourceVersion: "",
                      });
                      setValue("");
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
                onChange={(e) => setMode(e.target.value)}
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
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </label>
            <p className="text-xs text-zinc-500">
              Empty values are allowed. Updates need a selected key and its
              current version.
            </p>
            <div className="flex flex-wrap gap-3">
              <button
                className={button}
                disabled={
                  busy || (mode === "update" && !target.resourceVersion)
                }
              >
                Save key
              </button>
              <button
                type="button"
                className={button}
                disabled={busy || !target.resourceVersion}
                onClick={() =>
                  perform(async () => {
                    const result = await api(
                      `/api/secrets?${new URLSearchParams(target)}`,
                    );
                    setValue(result.value);
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
                onClick={() => setValue("")}
              >
                Clear value
              </button>
              <button
                type="button"
                className={`${button} text-red-300`}
                disabled={busy || !target.resourceVersion}
                onClick={() =>
                  perform(async () => {
                    await api("/api/secrets", {
                      method: "DELETE",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(target),
                    });
                    setValue("");
                    setTarget((current) => ({
                      ...current,
                      resourceVersion: "",
                    }));
                    setMode("create");
                    setMessage("Key deleted; object retained.");
                    await refresh();
                  })
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
              perform(async () => {
                await api("/api/secret-references", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    alias,
                    namespace: target.namespace,
                    name: target.name,
                    key: target.key,
                  }),
                });
                setAlias("");
                setMessage("Lookup alias registered.");
                await refresh();
              });
            }}
          >
            <label className="text-sm text-zinc-400">
              Alias for this namespace / Secret / key
              <input
                required
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
        <ul className="space-y-1 text-sm text-zinc-400">
          {refs.map((ref) => (
            <li key={ref.alias}>
              {ref.alias} → {ref.namespace} / {ref.name} / {ref.key}
              {canWrite && (
                <button
                  className="ml-3 text-red-300"
                  disabled={busy}
                  onClick={() =>
                    perform(async () => {
                      await api(
                        `/api/secret-references?alias=${encodeURIComponent(ref.alias)}`,
                        { method: "DELETE" },
                      );
                      setMessage(
                        "DB reference removed. File references must be edited by the operator.",
                      );
                      await refresh();
                    })
                  }
                >
                  Remove DB alias
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
