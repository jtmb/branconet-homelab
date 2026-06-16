"use client";

import { X } from "lucide-react";

interface LogModalProps {
  open: boolean;
  onClose: () => void;
  logs: string;
  title: string;
}

export default function LogModal({ open, onClose, logs, title }: LogModalProps) {
  if (!open) return null;

  const lines = logs ? logs.split("\n") : [];
  const lineCount = lines.length;
  const padWidth = String(lineCount || 1).length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="glass-card relative w-full max-w-5xl max-h-[85vh] flex flex-col mx-4">
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <h2 className="text-lg font-semibold text-zinc-100">
            {title}
            {lineCount > 0 && (
              <span className="ml-2 text-sm font-normal text-zinc-500">
                ({lineCount.toLocaleString()} line{lineCount !== 1 ? "s" : ""})
              </span>
            )}
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-zinc-700 text-zinc-400"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-auto">
          {lines.length === 0 ? (
            <div className="p-4 text-sm text-zinc-500 font-mono">(no output)</div>
          ) : (
            <div className="font-mono text-sm leading-relaxed">
              {lines.map((line, i) => (
                <div
                  key={i}
                  className={`flex min-h-[1.75rem] ${
                    i % 2 === 0 ? "bg-zinc-900/60" : "bg-zinc-800/30"
                  } hover:bg-blue-500/10 transition-colors`}
                >
                  <span
                    className="flex-shrink-0 text-right select-none text-zinc-600 w-12 px-2 py-0.5 border-r border-zinc-700/50"
                    aria-hidden
                  >
                    {String(i + 1).padStart(padWidth, " ")}
                  </span>
                  <span className="flex-1 px-3 py-0.5 text-zinc-300 whitespace-pre-wrap break-all">
                    {line || " "}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
