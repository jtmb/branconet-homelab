"use client";
import { Modal } from "@/components/ui/modal";
interface Props { open: boolean; onClose: () => void; logs: string; title: string; returnFocus?: () => void }
export default function LogModal({ open, onClose, logs, title, returnFocus }: Props) {
  if (!open) return null;
  return <Modal open={open} onClose={onClose} title={title} returnFocus={returnFocus} description="Bounded log snapshot; refresh to request new output.">
    <pre tabIndex={0} className="overflow-auto whitespace-pre-wrap break-words font-mono text-sm text-zinc-300">{logs || "(no output)"}</pre>
  </Modal>;
}
