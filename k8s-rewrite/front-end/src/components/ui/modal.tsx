"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { useRef } from "react";
import { X } from "lucide-react";

export function Modal({ open, onClose, title, description, children, actions, returnFocus }: {
  open: boolean; onClose: () => void; title: string; description?: string; children: React.ReactNode;
  actions?: React.ReactNode; returnFocus?: () => void;
}) {
  const previousFocus = useRef<HTMLElement | null>(null);
  return <Dialog.Root open={open} onOpenChange={value => { if (!value) onClose(); }}>
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70" />
      <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90dvh] w-[calc(100%_-_1rem)] max-w-4xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-zinc-700 bg-zinc-900 shadow-xl"
        onOpenAutoFocus={() => { previousFocus.current = document.activeElement as HTMLElement; }}
        onCloseAutoFocus={event => {
          event.preventDefault();
          if (returnFocus) returnFocus();
          else previousFocus.current?.focus();
        }}>
        <div className="flex shrink-0 items-center gap-2 border-b border-zinc-800 p-4">
          <Dialog.Title className="min-w-0 flex-1 break-words text-lg font-semibold">{title}</Dialog.Title>
          {actions}
          <button onClick={onClose} aria-label="Close dialog" className="rounded-lg p-2 hover:bg-zinc-800"><X className="h-5 w-5" /></button>
        </div>
        <Dialog.Description className={description ? "px-4 pt-3 text-sm text-zinc-400" : "sr-only"}>{description ?? title}</Dialog.Description>
        <div className="min-h-0 overflow-auto p-4">{children}</div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
