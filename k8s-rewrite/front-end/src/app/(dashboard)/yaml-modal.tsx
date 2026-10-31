"use client";
import { useEffect, useRef, useState } from "react";
import { Modal } from "@/components/ui/modal";

interface YamlModalProps {
  open: boolean; onClose: () => void; yaml: string; title: string; readOnly?: boolean;
  onSave?: (yaml: string) => Promise<void>; returnFocus?: () => void;
}
export default function YamlModal({ open, onClose, yaml, title, readOnly = true, onSave, returnFocus }: YamlModalProps) {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(yaml);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [discard, setDiscard] = useState(false);
  const generation = useRef(0);
  const identity = useRef({ open, yaml, title, readOnly });
  if (identity.current.open !== open || identity.current.yaml !== yaml || identity.current.title !== title || identity.current.readOnly !== readOnly)
    identity.current = { open, yaml, title, readOnly };
  useEffect(() => {
    const owner = ++generation.current;
    setEditing(false); setContent(yaml); setSaving(false); setError(""); setDiscard(false);
    return () => { generation.current = owner + 1; };
  }, [open, yaml, title, readOnly]);
  const canEdit = !readOnly && !!onSave;
  const editable = canEdit && editing;
  const dirty = editable && content !== yaml;
  const close = () => { if (saving) return; if (dirty) setDiscard(true); else onClose(); };
  if (!open) return null;
  const save = async () => {
    if (!canEdit || !onSave || !dirty || saving) return;
    const owner = generation.current;
    const rendered = identity.current;
    const owns = () => generation.current === owner && identity.current === rendered;
    setSaving(true); setError("");
    try { await onSave(content); if (owns()) onClose(); }
    catch (failure) { if (owns()) setError(failure instanceof Error ? failure.message : "Save failed"); }
    finally { if (owns()) setSaving(false); }
  };
  return <Modal open={open} onClose={close} title={title} returnFocus={returnFocus}
    description={canEdit ? "Replacement requires the displayed resourceVersion. Refresh after a conflict." : "Read-only YAML."}
    actions={<>{canEdit && !editing && <button onClick={() => setEditing(true)} className="rounded bg-zinc-700 px-3 py-1">Edit</button>}
      {editable && <button onClick={save} disabled={saving || !dirty} className="rounded bg-indigo-600 px-3 py-1 disabled:opacity-50">{saving ? "Saving…" : "Save"}</button>}</>}>
    {error && <p role="alert" className="mb-3 text-red-300">{error}</p>}
    {discard && <div role="alert" className="mb-3 rounded border border-amber-700 p-3 text-sm">
      <p>Discard unsaved YAML changes?</p>
      <button onClick={() => setDiscard(false)} className="mr-4 underline">Keep editing</button>
      <button onClick={onClose} className="underline text-red-300">Discard changes</button>
    </div>}
    {editable ? <textarea aria-label="YAML content" value={content} onChange={e => setContent(e.target.value)} disabled={saving}
      className="min-h-[50dvh] w-full resize-y rounded border border-zinc-700 bg-zinc-950 p-3 font-mono text-sm" spellCheck={false} />
      : <pre tabIndex={0} className="overflow-auto whitespace-pre font-mono text-sm">{yaml}</pre>}
  </Modal>;
}
