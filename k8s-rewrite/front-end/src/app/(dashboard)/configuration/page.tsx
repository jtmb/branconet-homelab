"use client";
import { useEffect, useState, type FormEvent } from "react";
type Variable = { id: string; key: string; value: string; category: string };
export default function ConfigurationPage() {
  const [vars, setVars] = useState<Variable[]>([]),
    [canWrite, setCanWrite] = useState(false),
    [message, setMessage] = useState("");
  const [form, setForm] = useState({ key: "", value: "", category: "general" });
  async function refresh() {
    const r = await fetch("/api/vars", { cache: "no-store" });
    if (!r.ok) throw new Error("Configuration unavailable");
    setVars(await r.json());
  }
  useEffect(() => {
    refresh().catch((e) => setMessage(e.message));
    fetch("/api/auth/session")
      .then((r) => r.json())
      .then((s) => setCanWrite(s.role === "write"));
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    const r = await fetch("/api/vars", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...form, encrypted: false }),
    });
    const result = await r.json();
    setMessage(r.ok ? "Configuration saved." : result.error);
    if (r.ok) {
      setForm({ key: "", value: "", category: "general" });
      await refresh();
    }
  }
  return (
    <div className="p-6 space-y-5">
      <h1 className="text-xl font-semibold">Nonsecret configuration</h1>
      <p className="text-sm text-zinc-400">
        Versions, network and inventory settings. Manage credentials under
        Secrets.
      </p>
      {message && (
        <p role="status" className="text-amber-300 text-sm">
          {message}
        </p>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-zinc-400">
            <th>Key</th>
            <th>Category</th>
            <th>Value</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {vars.map((v) => (
            <tr className="border-b border-zinc-800" key={v.id}>
              <td className="py-3">{v.key}</td>
              <td>{v.category}</td>
              <td className="break-all">{v.value}</td>
              <td>
                {canWrite && (
                  <>
                    <button
                      className="text-indigo-300 mr-3"
                      onClick={() =>
                        setForm({
                          key: v.key,
                          value: v.value,
                          category: v.category,
                        })
                      }
                    >
                      Edit
                    </button>
                    <button
                      className="text-red-300"
                      onClick={async () => {
                        const r = await fetch(`/api/vars/${v.id}`, {
                          method: "DELETE",
                        });
                        setMessage(
                          r.ok ? "Configuration removed." : "Delete failed",
                        );
                        await refresh();
                      }}
                    >
                      Delete
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {canWrite && (
        <form
          className="space-y-3 border border-zinc-800 rounded-lg p-4"
          onSubmit={save}
        >
          <h2>Add or edit nonsecret configuration</h2>
          {(["key", "category", "value"] as const).map((field) => (
            <label className="block text-sm text-zinc-400" key={field}>
              {field}
              <input
                required={field !== "value"}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2"
                value={form[field]}
                onChange={(e) => setForm({ ...form, [field]: e.target.value })}
              />
            </label>
          ))}
          <button className="text-indigo-300">Save configuration</button>
        </form>
      )}
    </div>
  );
}
