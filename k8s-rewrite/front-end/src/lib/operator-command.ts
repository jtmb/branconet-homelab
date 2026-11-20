import { spawn } from "node:child_process";
import { operatorCommandFailure } from "./kubectl-client";

type Options = { cwd?: string; env?: NodeJS.ProcessEnv; encoding: "utf8"; timeout: number; maxBuffer: number };

/** One invocation owns one POSIX group. This is process cleanup, not a sandbox. */
export function executeOperatorCommand(command: string, options: Options): Promise<string> {
  return new Promise((resolve, reject) => {
    const posix = process.platform !== "win32";
    const child = spawn("bash", ["-c", command], { cwd: options.cwd, env: options.env, detached: posix, stdio: ["pipe", "pipe", "pipe"] });
    let stdout: Buffer[] = [];
    let stdoutBytes = 0, stderrBytes = 0;
    let failure: ReturnType<typeof operatorCommandFailure> | undefined;
    let stopping: Promise<void> | undefined;
    const signalGroup = (signal: "SIGTERM" | "SIGKILL") => {
      if (!child.pid) return;
      try { if (posix) process.kill(-child.pid, signal); else child.kill(signal); }
      catch { /* Already absent or unavailable; never expose dynamic errors. */ }
    };
    const stopGroup = () => stopping ??= new Promise<void>(done => {
      signalGroup("SIGTERM");
      setTimeout(() => { signalGroup("SIGKILL"); done(); }, 250);
    });
    const refuse = (error: unknown) => {
      if (failure) return;
      failure = operatorCommandFailure(error);
      stdout = [];
      void stopGroup();
    };
    const deadline = setTimeout(() => refuse({ killed: true }), options.timeout);
    child.stdout.on("data", (chunk: Buffer) => {
      if (failure) return;
      stdoutBytes += chunk.length;
      if (stdoutBytes > options.maxBuffer) refuse({ code: "ERR_CHILD_PROCESS_STDIO_MAXBUFFER" });
      else stdout.push(chunk);
    });
    child.stderr.on("data", (chunk: Buffer) => {
      if (failure) return;
      stderrBytes += chunk.length;
      if (stderrBytes > options.maxBuffer) refuse({ code: "ERR_CHILD_PROCESS_STDIO_MAXBUFFER" });
      // Successful stderr is counted against the same bound, never returned.
    });
    child.once("error", error => { failure ??= operatorCommandFailure(error); stdout = []; });
    child.once("close", (code, signal) => {
      clearTimeout(deadline);
      if (!failure && (code !== 0 || signal)) failure = operatorCommandFailure({ code });
      void (async () => {
        if (stopping) await stopping;
        if (failure) reject(failure); else resolve(Buffer.concat(stdout, stdoutBytes).toString("utf8"));
        stdout = [];
      })();
    });
  });
}
