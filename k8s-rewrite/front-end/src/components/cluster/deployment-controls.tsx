"use client";
import { useEffect, useRef, useState } from "react";
import { requestJson, refetchCluster, useSession } from "@/lib/use-query";
import { resourceBase } from "@/lib/resource-capabilities";

export function DeploymentControls({ namespace, name, desired }: { namespace: string; name: string; desired: number }) {
  const session = useSession();
  const pending = useRef<AbortController>();
  const allowed = useRef(session.canWrite);
  allowed.current = session.canWrite;
  const target = resourceBase("deployment", namespace, name);
  const identity = useRef(target);
  identity.current = target;
  const [input, setInput] = useState(String(desired));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    pending.current?.abort(); pending.current = undefined;
    setSaving(false); setError(""); setInput(String(desired));
  }, [session.canWrite, namespace, name, desired]);
  useEffect(() => {
    allowed.current = session.canWrite;
    return () => { allowed.current = false; pending.current?.abort(); };
  }, [session.canWrite, namespace, name]);
  const number = Number(input);
  const valid = input.trim() !== "" && Number.isInteger(number) && number >= 0 && number <= 10000 && number !== desired;
  if (!session.canWrite) return <p>{desired}</p>;
  return <form onSubmit={async event => {
    event.preventDefault();
    if (!allowed.current || identity.current !== target || !valid || saving || pending.current) return;
    const controller = new AbortController(); pending.current = controller;
    const owns = () => allowed.current && identity.current === target && !controller.signal.aborted && pending.current === controller;
    setSaving(true); setError("");
    try { await requestJson(target + "/scale", { signal: controller.signal, method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ replicas: number }) }); if (owns()) refetchCluster(); }
    catch (failure) { if (owns()) setError(failure instanceof Error ? failure.message : "Scale failed"); }
    finally { if (owns()) { pending.current = undefined; setSaving(false); } }
  }}>
    <label className="sr-only" htmlFor="desired-replicas">Desired replicas</label>
    <input id="desired-replicas" type="number" min={0} max={10000} step={1} value={input} onChange={event => setInput(event.target.value)} disabled={saving}
      className="mr-2 w-20 rounded border border-zinc-700 bg-zinc-950 p-1" />
    <button disabled={!valid || saving} className="rounded bg-indigo-600 px-2 py-1 disabled:opacity-40">{saving ? "Scaling…" : "Scale"}</button>
    {error && <p role="alert" className="mt-2 text-sm text-red-300">{error}</p>}
  </form>;
}
