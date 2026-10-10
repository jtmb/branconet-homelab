"use client";
import { useState } from "react";
import { requestJson, refetchCluster, useSession } from "@/lib/use-query";
import { resourceBase } from "@/lib/resource-capabilities";

export function DeploymentControls({ namespace, name, desired }: { namespace: string; name: string; desired: number }) {
  const session = useSession();
  const [input, setInput] = useState(String(desired));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const number = Number(input);
  const valid = input.trim() !== "" && Number.isInteger(number) && number >= 0 && number <= 10000 && number !== desired;
  if (!session.canWrite) return <p>{desired}</p>;
  return <form onSubmit={async event => {
    event.preventDefault();
    if (!valid || saving) return;
    setSaving(true); setError("");
    try { await requestJson(resourceBase("deployment", namespace, name) + "/scale", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ replicas: number }) }); refetchCluster(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Scale failed"); }
    finally { setSaving(false); }
  }}>
    <label className="sr-only" htmlFor="desired-replicas">Desired replicas</label>
    <input id="desired-replicas" type="number" min={0} max={10000} step={1} value={input} onChange={event => setInput(event.target.value)} disabled={saving}
      className="mr-2 w-20 rounded border border-zinc-700 bg-zinc-950 p-1" />
    <button disabled={!valid || saving} className="rounded bg-indigo-600 px-2 py-1 disabled:opacity-40">{saving ? "Scaling…" : "Scale"}</button>
    {error && <p role="alert" className="mt-2 text-sm text-red-300">{error}</p>}
  </form>;
}
