import { EventEmitter } from "node:events";
import { type ChildProcess } from "node:child_process";
import { ANSIBLE_ROLES, type AnsibleRole } from "./ansible-selection";

const PREFIX = "BORTUS_PROGRESS_V1 ";
const LINE_BYTES = 160;

/** Accept exact fixed protocol records; arbitrary stdout/stderr is never rendered. */
export function observeAnsibleProcess(proc: ChildProcess, signal?: AbortSignal, onClose: () => void = () => {}) {
  const emitter = new EventEmitter();
  const roles = new Map<AnsibleRole, "running" | "failed">();
  let line: number[] = [], discarded = false, warned = false, started = false;
  let completed: "success" | "failed" | undefined, cancelled = false, ended = false, output = "";
  function write(text: string) { output += text; emitter.emit("data", text); }
  function withheld() { if (!warned) { warned = true; write("[Raw runner output withheld]\n"); } }
  function accept(text: string) {
    if (text === PREFIX + "start" && !started) { started = true; write("[Provisioning started]\n"); return; }
    if (started && !completed && (text === PREFIX + "complete:success" || text === PREFIX + "complete:failed")) {
      completed = text.endsWith(":success") ? "success" : "failed"; return;
    }
    if (started && !completed) for (const role of ANSIBLE_ROLES) for (const status of ["running", "failed"] as const) {
      if (text !== PREFIX + "role:" + role + ":" + status) continue;
      const previous = roles.get(role);
      if (previous === "failed" || previous === status) return;
      roles.set(role, status); write(`[Role ${role}: ${status}]\n`); emitter.emit("role-progress", { role, status }); return;
    }
    if (text) withheld();
  }
  function stdout(chunk: Buffer) {
    for (const byte of chunk) {
      if (byte === 10) {
        if (line.at(-1) === 13) line.pop();
        if (discarded) withheld(); else accept(Buffer.from(line).toString("ascii")); line = []; discarded = false;
      }
      else if (!discarded) { if (line.length >= LINE_BYTES || byte !== 13 && byte < 32 || byte > 126) { line = []; discarded = true; } else line.push(byte); }
    }
  }
  function stderr(chunk: Buffer) { if (chunk.length) withheld(); }
  function finish(code: number | null, failedToStart = false) {
    if (ended) return; ended = true;
    if (line.length || discarded) withheld(); line = [];
    const success = !cancelled && !failedToStart && code === 0 && started && completed === "success" && ![...roles.values()].includes("failed");
    if (failedToStart) write("[Provisioning runner could not start]\n");
    else if (cancelled) write("[Provisioning cancelled; inspect partial effects]\n");
    else if (!started || !completed) write("[Supported progress unavailable; inspect the operator runner]\n");
    for (const [role, status] of roles) {
      const finalStatus = status === "failed" || !success ? "failed" : "success";
      if (status !== finalStatus) { write(`[Role ${role}: ${finalStatus}]\n`); emitter.emit("role-progress", { role, status: finalStatus }); }
    }
    write(success ? "[Provisioning completed]\n" : "[Provisioning failed]\n");
    proc.stdout?.removeListener("data", stdout); proc.stderr?.removeListener("data", stderr);
    proc.removeListener("close", close); proc.removeListener("error", error); signal?.removeEventListener("abort", abort);
    emitter.emit("close", { exitCode: success ? 0 : code === null || code === 0 ? -1 : code, fullOutput: output });
    onClose();
  }
  function close(code: number | null) { finish(code); }
  function error() { finish(-1, true); }
  function abort() { if (ended || cancelled) return; cancelled = true; proc.kill("SIGTERM"); }
  proc.stdout?.on("data", stdout); proc.stderr?.on("data", stderr); proc.on("close", close); proc.on("error", error);
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) abort();
  return emitter;
}
