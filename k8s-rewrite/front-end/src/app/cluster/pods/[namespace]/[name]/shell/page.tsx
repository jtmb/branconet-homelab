"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";

const ESC = "\u001b";

// Parse ANSI escape codes into HTML spans with Tailwind classes
function ansiToSpans(text: string) {
  const parts: { cls: string; text: string }[] = [];
  let i = 0;
  let currentCls = "";
  let currentText = "";

  while (i < text.length) {
    if (text[i] === ESC && text[i + 1] === "[") {
      // Flush current segment
      if (currentText) {
        parts.push({ cls: currentCls, text: currentText });
        currentText = "";
      }
      // Parse CSI sequence
      const end = text.indexOf("m", i);
      if (end === -1) break;
      const code = text.substring(i + 2, end);
      i = end + 1;
      // Map ANSI codes to Tailwind classes
      if (code === "0") currentCls = "";
      else if (code === "31") currentCls = "text-red-400";
      else if (code === "32") currentCls = "text-green-400";
      else if (code === "33") currentCls = "text-amber-300";
      else if (code === "34") currentCls = "text-blue-400";
      else if (code === "35") currentCls = "text-purple-400";
      else if (code === "36") currentCls = "text-cyan-400";
      else if (code === "37") currentCls = "text-white";
      else if (code === "1") currentCls = currentCls + " font-bold";
    } else {
      currentText += text[i];
      i++;
    }
  }
  if (currentText) parts.push({ cls: currentCls, text: currentText });
  return parts;
}

export default function ShellPage() {
  const router = useRouter();
  const params = useParams();
  const namespace = params.namespace as string;
  const podName = params.name as string;
  const [command, setCommand] = useState("");
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const runCommand = useCallback(
    async (cmd: string) => {
      if (!cmd.trim()) return;
      const newHistory = [...history, cmd];
      setHistory(newHistory);
      setHistoryIdx(newHistory.length);
      setCommand("");
      setLoading(true);
      setOutput((prev) => `${prev}${ESC}[32m${podName}@${namespace}:${ESC}[0m${ESC}[37m~$${ESC}[0m ${cmd}\n`);

      try {
        const res = await fetch(
          `/api/cluster/pods/${namespace}/${podName}/shell`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command: cmd }),
          }
        );
        const data = await res.json();
        if (data.error) {
          setOutput((prev) => `${prev}${ESC}[31mError:${ESC}[0m ${data.error}\n`);
        } else {
          setOutput((prev) => `${prev}${data.output || ""}${data.output ? "" : `${ESC}[31m(no output)${ESC}[0m`}\n`);
        }
      } catch (e: any) {
        setOutput(
          (prev) => `${prev}${ESC}[31mError:${ESC}[0m ${e?.message || "request failed"}\n`
        );
      } finally {
        setLoading(false);
      }
    },
    [history, namespace, podName]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (history.length === 0) return;
      const newIdx = historyIdx <= 0 ? history.length - 1 : historyIdx - 1;
      setHistoryIdx(newIdx);
      setCommand(history[newIdx]);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (history.length === 0) return;
      const newIdx = historyIdx >= history.length - 1 ? 0 : historyIdx + 1;
      setHistoryIdx(newIdx);
      setCommand(history[newIdx]);
    }
  };

  return (
    <div className="mx-auto w-full max-w-[90%]">
      {/* Back button outside terminal frame */}
      <button
        onClick={() => router.back()}
        className="mb-3 p-2 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 inline-flex items-center gap-2 text-sm"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to pod
      </button>

      {/* Terminal frame */}
      <div className="rounded-xl border border-zinc-700/60 overflow-hidden shadow-2xl shadow-black/40">
        {/* Title bar */}
        <div className="flex items-center gap-2 px-4 py-2.5 bg-zinc-900 border-b border-zinc-700/50">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 flex-shrink-0" />
          <span className="w-2.5 h-2.5 rounded-full bg-yellow-500 flex-shrink-0" />
          <span className="w-2.5 h-2.5 rounded-full bg-green-500 flex-shrink-0" />
          <span className="ml-3 text-xs text-zinc-500 font-mono truncate">
            kubectl exec — {namespace}/{podName}
          </span>
          {loading && (
            <Loader2 className="w-3.5 h-3.5 text-amber-400 animate-spin ml-auto" />
          )}
        </div>

        {/* Output area */}
        <div
          ref={outputRef}
          className="bg-zinc-950 h-[62vh] overflow-auto"
          onClick={() => inputRef.current?.focus()}
        >
          {output ? (
            <pre className="text-sm font-mono whitespace-pre-wrap p-4 leading-relaxed min-h-full">
              {ansiToSpans(output).map((part, i) => (
                <span key={i} className={part.cls || "text-zinc-100"}>
                  {part.text}
                </span>
              ))}
            </pre>
          ) : (
            <div className="flex items-center justify-center h-full text-zinc-600 text-sm font-mono">
              Shell ready — type a command to begin
            </div>
          )}
        </div>

        {/* Input bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            runCommand(command);
          }}
          className="flex items-center gap-0 bg-zinc-900 border-t border-zinc-700/50 px-4 py-2.5"
        >
          <span className="text-green-400 font-mono text-sm whitespace-nowrap select-none">
            {podName}@{namespace}:~$
          </span>
          <input
            ref={inputRef}
            type="text"
            value={command}
            onChange={(e) => {
              setCommand(e.target.value);
              setHistoryIdx(-1);
            }}
            onKeyDown={handleKeyDown}
            disabled={loading}
            className="flex-1 bg-transparent text-amber-300 font-mono text-sm ml-2 outline-none placeholder:text-zinc-600 disabled:opacity-50"
            placeholder="kubectl exec command..."
            autoFocus
            spellCheck={false}
          />
        </form>
      </div>
    </div>
  );
}
