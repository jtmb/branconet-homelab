"use client";
import { useState } from "react";
import { Modal } from "@/components/ui/modal";

interface Props {
  open: boolean; onClose: () => void; onConfirm: () => void; title: string; message: string;
  confirmLabel?: string; danger?: boolean; loading?: boolean; confirmName?: string; returnFocus?: () => void; error?: string;
  children?: React.ReactNode; disabled?: boolean;
}
export default function ConfirmDialog({ open, onClose, onConfirm, title, message, confirmLabel = "Confirm", danger = false, loading = false, confirmName, returnFocus, error, children, disabled = false }: Props) {
  const [confirmation, setConfirmation] = useState("");
  if (!open) return null;
  return <Modal open={open} onClose={() => { if (!loading) onClose(); }} title={title} description={message} returnFocus={returnFocus}>
    {error && <p role="alert" className="mb-3 text-red-300">{error}</p>}
    {children}
    {confirmName && <label className="block mb-4 text-sm">Type {confirmName} to confirm
      <input autoComplete="off" value={confirmation} onChange={event => setConfirmation(event.target.value)} className="mt-2 block w-full rounded border border-zinc-700 bg-zinc-950 p-2" />
    </label>}
    <div className="flex justify-end gap-3">
      <button onClick={onClose} disabled={loading} className="rounded bg-zinc-700 px-4 py-2">Cancel</button>
      <button onClick={onConfirm} disabled={disabled || loading || (!!confirmName && confirmation !== confirmName)}
        className={`rounded px-4 py-2 disabled:opacity-50 ${danger ? "bg-red-700" : "bg-indigo-600"}`}>{loading ? "Please wait…" : confirmLabel}</button>
    </div>
  </Modal>;
}
