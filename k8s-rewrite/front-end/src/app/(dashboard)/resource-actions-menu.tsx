"use client";
import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import { RESOURCE_CAPABILITIES, resourceBase, ResourceType } from "@/lib/resource-capabilities";
import { requestJson, refetchCluster, useSession } from "@/lib/use-query";
import { openShell } from "@/lib/shell-manager";
import ConfirmDialog from "./confirm-dialog";
export type { ResourceType } from "@/lib/resource-capabilities";

const YamlModal = dynamic(() => import("./yaml-modal"), { ssr: false });
const LogModal = dynamic(() => import("./log-modal"), { ssr: false });
type Resource = { metadata?: { namespace?: string; name?: string }; name?: string; namespace?: string;
  spec?: { replicas?: number; paused?: boolean; unschedulable?: boolean }; desiredReplicas?: number; replicas?: number; paused?: boolean };
export interface ResourceActionProps { resourceType: ResourceType; resource: Resource; onAction?: () => void; initialOpen?: boolean }
interface Confirmation { title: string; message: string; label: string; name?: string; execute: () => Promise<void> }
export default function ResourceActionsMenu({ resourceType, resource, onAction, initialOpen = false }: ResourceActionProps) {
  const session = useSession();
  const capability = RESOURCE_CAPABILITIES[resourceType];
  const name = resource.metadata?.name ?? resource.name ?? "";
  const namespace = resource.metadata?.namespace ?? resource.namespace ?? "";
  const base = resourceBase(resourceType, namespace, name);
  const trigger = useRef<HTMLButtonElement>(null);
  const pending = useRef<AbortController>();
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [yaml, setYaml] = useState<{ value: string; edit: boolean }>();
  const [logs, setLogs] = useState<string>();
  const [confirmation, setConfirmation] = useState<Confirmation>();
  const returnFocus = () => trigger.current?.focus();
  useEffect(() => () => { pending.current?.abort(); if (timer.current) clearTimeout(timer.current); }, []);
  useEffect(() => { if (!session.canWrite) { setYaml(value => value ? { ...value, edit: false } : undefined); setConfirmation(undefined); } }, [session.canWrite]);
  const notify = (text: string) => {
    setMessage(text); if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(""), 6000);
  };
  const load = async (task: (signal: AbortSignal) => Promise<void>) => {
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    try { await task(controller.signal); }
    catch (error) { if (!controller.signal.aborted) notify(error instanceof Error ? error.message : "Request failed"); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  };
  const showYaml = (edit: boolean) => load(async signal => {
    const data = await requestJson<{ yaml: string }>(base + "/yaml", { signal });
    if (!signal.aborted) setYaml({ value: data.yaml, edit });
  });
  const download = () => load(async signal => {
    const data = await requestJson<{ yaml: string }>(base + "/yaml", { signal });
    if (signal.aborted) return;
    const url = URL.createObjectURL(new Blob([data.yaml], { type: "application/yaml" }));
    const anchor = document.createElement("a"); anchor.href = url;
    anchor.download = `${resourceType}-${namespace ? namespace + "-" : ""}${name}.yaml`;
    anchor.click(); URL.revokeObjectURL(url);
  });
  const changed = () => { refetchCluster(); onAction?.(); };
  const mutate = async (url: string, method: string, body?: unknown) => {
    if (!session.canWrite) throw new Error("A current write role is required.");
    await requestJson(url, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
    changed();
  };
  const action = (actionName: string, body?: unknown) => load(async () => {
    try { await mutate(base + (actionName === "scale" ? "/scale" : "/action"), "POST", body ?? { action: actionName }); notify("Action accepted. Refreshing resource state."); }
    finally { if (resourceType === "node") changed(); }
  });
  const confirm = (title: string, message: string, label: string, execute: () => Promise<void>, exactName?: string) => {
    setMessage(""); setConfirmation({ title, message, label, execute, name: exactName });
  };
  const finishConfirmation = async () => {
    if (!confirmation || busy) return;
    setBusy(true);
    try { await confirmation.execute(); setConfirmation(undefined); notify("Action accepted. Refreshing resource state."); }
    catch (error) { notify(error instanceof Error ? error.message : "Action failed"); }
    finally { setBusy(false); }
  };
  const items: { label: string; run: () => void; danger?: boolean; disabled?: boolean }[] = session.canWrite ? [
    { label: "View YAML", run: () => { void showYaml(false); } },
    { label: "Download YAML", run: () => { void download(); } },
  ] : [];
  if (session.canWrite && capability.logs) items.unshift({ label: "View Logs", run: () => { void load(async signal => {
    const data = await requestJson<{ logs: string }>(base + "/logs?tail=100", { signal });
    if (!signal.aborted) setLogs(data.logs);
  }); } });
  if (session.canWrite) {
    if (capability.yamlEdit) items.push({ label: "Edit YAML", run: () => { void showYaml(true); } });
    if (resourceType === "pod" && session.data?.capabilities?.podExec) items.push({ label: "Execute Shell", run: () => { openShell("exec", namespace, name); } });
    if (resourceType === "deployment") {
      const replicas = resource.spec?.replicas ?? resource.desiredReplicas ?? resource.replicas ?? 1;
      const paused = resource.spec?.paused ?? resource.paused ?? false;
      items.push(
        { label: "Restart", run: () => { void action("restart"); } },
        { label: "Rollback", run: () => confirm("Roll back deployment", "Flux may restore Git desired state after this runtime operation.", "Roll back", () => mutate(base + "/action", "POST", { action: "rollback" })) },
        { label: "Scale Up", disabled: paused || !Number.isInteger(replicas) || replicas >= 10000, run: () => { void action("scale", { replicas: replicas + 1 }); } },
        { label: "Scale Down", disabled: paused || !Number.isInteger(replicas) || replicas <= 0, run: () => { void action("scale", { replicas: replicas - 1 }); } },
        { label: paused ? "Resume" : "Pause", run: () => { void action(paused ? "resume" : "pause"); } },
      );
    }
    if (resourceType === "node") {
      const cordoned = resource.spec?.unschedulable ?? false;
      items.push({ label: cordoned ? "Uncordon" : "Cordon", run: () => { void action(cordoned ? "uncordon" : "cordon"); } },
        { label: "Drain", danger: true, run: () => confirm("Drain node", "Evicts managed pods while respecting disruption budgets. Refuses unmanaged pods and local data. A failure or timeout can leave the node cordoned or partially drained; inspect it before retrying.", "Drain", async () => {
          try { await mutate(base + "/action", "POST", { action: "drain", confirmName: name }); } finally { changed(); }
        }, name) });
    }
    if (capability.delete) items.push({ label: "Delete", danger: true, run: () => confirm(`Delete ${capability.kind}`,
      `Delete ${namespace ? namespace + "/" : ""}${name}? Controllers or Flux may recreate it. Inspect dependent resources before deleting.`, "Delete",
      () => mutate(base + "/delete", "DELETE"), name) });
  }
  return <>
    <DropdownMenu.Root defaultOpen={initialOpen}>
      <DropdownMenu.Trigger asChild><button ref={trigger} disabled={busy} aria-label={`Actions for ${name}`} className="rounded-lg p-2 hover:bg-zinc-800 disabled:opacity-50"><MoreHorizontal className="h-5 w-5" /></button></DropdownMenu.Trigger>
      <DropdownMenu.Portal><DropdownMenu.Content align="end" sideOffset={4} className="z-40 min-w-[180px] rounded-lg border border-zinc-700 bg-zinc-900 p-1 shadow-xl">
        {items.map(item => <DropdownMenu.Item key={item.label} disabled={item.disabled}
          onSelect={item.run} className={`cursor-pointer rounded px-3 py-2 text-sm outline-none focus:bg-zinc-800 data-[disabled]:opacity-40 ${item.danger ? "text-red-300" : "text-zinc-200"}`}>{item.label}</DropdownMenu.Item>)}
      </DropdownMenu.Content></DropdownMenu.Portal>
    </DropdownMenu.Root>
    {(message || busy) && <p role="status" className="fixed bottom-4 right-4 z-[70] max-w-[calc(100vw-2rem)] rounded-lg border border-zinc-700 bg-zinc-900 p-3 text-sm">{busy ? "Working…" : message}</p>}
    {yaml && <YamlModal open onClose={() => setYaml(undefined)} yaml={yaml.value} title={`${capability.kind} YAML: ${namespace ? namespace + "/" : ""}${name}`}
      readOnly={!yaml.edit || !session.canWrite || !capability.yamlEdit} returnFocus={returnFocus}
      onSave={yaml.edit && session.canWrite && capability.yamlEdit ? async value => { await mutate(base + "/yaml", "PUT", { yaml: value }); notify("YAML replaced. Refreshing resource state."); } : undefined} />}
    {logs !== undefined && <LogModal open onClose={() => setLogs(undefined)} logs={logs} title={`Logs: ${namespace}/${name}`} returnFocus={returnFocus} />}
    {confirmation && <ConfirmDialog open onClose={() => { if (!busy) setConfirmation(undefined); }} title={confirmation.title}
      message={confirmation.message} confirmLabel={confirmation.label} confirmName={confirmation.name} error={message} danger loading={busy} onConfirm={finishConfirmation} returnFocus={returnFocus} />}
  </>;
}
