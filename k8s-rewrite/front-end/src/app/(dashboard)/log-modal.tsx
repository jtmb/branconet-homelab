"use client";
import { Modal } from "@/components/ui/modal";
interface Props { open: boolean; onClose: () => void; logs?: string; title: string; returnFocus?: () => void;
  containers: string[]; container: string; onContainerChange: (container: string) => void; loading: boolean; error?: string }
export default function LogModal({ open, onClose, logs, title, returnFocus, containers, container, onContainerChange, loading, error }: Props) {
  if (!open) return null;
  return <Modal open={open} onClose={onClose} title={title} returnFocus={returnFocus} description="Bounded log snapshot for the selected container.">
    <label className="mb-3 block text-sm">Container
      <select value={container} onChange={event => onContainerChange(event.target.value)} disabled={containers.length === 0}
        className="mt-1 block w-full rounded border border-zinc-700 bg-zinc-950 p-2">
        <option value="" disabled>{containers.length ? "Choose a container…" : "No containers available"}</option>
        {containers.map(name => <option key={name} value={name}>{name}</option>)}
      </select>
    </label>
    <button type="button" disabled={!container || loading} onClick={() => onContainerChange(container)}
      className="mb-3 rounded border border-zinc-700 px-3 py-2 disabled:opacity-50">Refresh logs</button>
    {loading && <p role="status">Loading log snapshot…</p>}
    {error && <p role="alert" className="mb-3 text-red-300">{error} Refresh logs to retry after checking the container state.</p>}
    {!loading && !error && logs === undefined && <p>{containers.length ? "Select a container to request its logs." : "Refresh the Pod metadata to check its containers."}</p>}
    {logs !== undefined && <pre tabIndex={0} className="overflow-auto whitespace-pre-wrap break-words font-mono text-sm text-zinc-300">{logs || "(no output)"}</pre>}
  </Modal>;
}
