"use client";

import { useState } from "react";
import { X, Save } from "lucide-react";
import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter";
import yamlLang from "react-syntax-highlighter/dist/esm/languages/prism/yaml";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

SyntaxHighlighter.registerLanguage("yaml", yamlLang);

interface YamlModalProps {
  open: boolean;
  onClose: () => void;
  yaml: string;
  title: string;
  readOnly?: boolean;
  onSave?: (yaml: string) => Promise<void>;
}

export default function YamlModal({
  open,
  onClose,
  yaml,
  title,
  readOnly = true,
  onSave,
}: YamlModalProps) {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(yaml);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const handleSave = async () => {
    if (!onSave) return;
    setSaving(true);
    setError("");
    try {
      await onSave(content);
      setEditing(false);
      onClose();
    } catch (e: any) {
      setError(e?.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="glass-card relative w-full max-w-4xl max-h-[85vh] flex flex-col mx-4">
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <h2 className="text-lg font-semibold text-zinc-100">{title}</h2>
          <div className="flex items-center gap-2">
            {!readOnly && !editing && (
              <button
                onClick={() => {
                  setEditing(true);
                  setContent(yaml);
                }}
                className="px-3 py-1 text-sm rounded-md bg-zinc-700 hover:bg-zinc-600 text-zinc-200"
              >
                Edit
              </button>
            )}
            {editing && (
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1 px-3 py-1 text-sm rounded-md bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {saving ? "Saving..." : "Save"}
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1 rounded-md hover:bg-zinc-700 text-zinc-400"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
        {error && (
          <div className="mx-4 mt-3 px-3 py-2 rounded-md bg-red-900/30 border border-red-800 text-red-300 text-sm">
            {error}
          </div>
        )}
        <div className="flex-1 overflow-auto">
          {editing ? (
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full h-full min-h-[50vh] bg-zinc-900 text-zinc-100 font-mono text-sm p-4 border border-zinc-700 outline-none focus:border-blue-500 resize-none"
              spellCheck={false}
            />
          ) : (
            <div className="overflow-hidden">
              <SyntaxHighlighter
                language="yaml"
                style={oneDark}
                customStyle={{
                  margin: 0,
                  padding: "1rem",
                  fontSize: "0.8125rem",
                  lineHeight: "1.6",
                  borderRadius: 0,
                }}
                showLineNumbers={false}
              >
                {yaml}
              </SyntaxHighlighter>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
