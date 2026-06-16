import { spawn, ChildProcess } from "child_process";
import { EventEmitter } from "events";
import path from "path";
import prisma from "./db";

export interface AnsibleEvent {
  type: "data" | "role-progress" | "close" | "error";
  data:
    | string
    | { role: string; status: "running" | "success" | "failed" }
    | { exitCode: number | null; fullOutput: string }
    | Error;
}

const ANSIBLE_DIR = path.resolve(process.cwd(), "../ansible-playbook");
const PLAYBOOK_DIR = path.join(ANSIBLE_DIR, "playbooks");
const INVENTORY_PATH = path.join(ANSIBLE_DIR, "inventory/production.ini");

// Regex to parse Ansible TASK lines like:
//   TASK [role_name : task_name] ********************************
//   TASK [kubernetes : Install kubelet] *************************
const TASK_LINE_RE = /^TASK\s+\[([^\]]+)\]/;

// Regex to detect PLAY RECAP lines
const PLAY_RECAP_RE = /^PLAY RECAP/;

// Regex to detect fatal/unreachable in recap
const FAILED_RE = /failed=(\d+)/;
const UNREACHABLE_RE = /unreachable=(\d+)/;

/**
 * Run an Ansible playbook and emit events for output and progress.
 *
 * @param playbookFile - The playbook file name (e.g., "site.yml")
 * @param roles - Optional list of role tags to limit execution
 * @param signal - Optional AbortSignal to cancel the process
 * @returns An EventEmitter that emits:
 *   - "data" (string): raw output line
 *   - "role-progress" ({ role, status }): role execution progress
 *   - "close" ({ exitCode, fullOutput }): process finished
 *   - "error" (Error): process error
 */
export async function runAnsiblePlaybook(
  playbookFile: string,
  roles: string[] = [],
  signal?: AbortSignal
): Promise<EventEmitter> {
  const emitter = new EventEmitter();
  const playbookPath = path.join(PLAYBOOK_DIR, playbookFile);

  // Read sudo password and SSH key from DB if stored
  let becomePassword = "";
  let sshKey = "/home/brajam/.ssh/id_ed25519"; // fallback default
  try {
    const [pwVar, keyVar] = await Promise.all([
      prisma.variable.findUnique({ where: { key: "ansible_become_password" } }),
      prisma.variable.findUnique({ where: { key: "ansible_ssh_private_key_file" } }),
    ]);
    if (pwVar?.value) becomePassword = pwVar.value;
    if (keyVar?.value) sshKey = keyVar.value;
  } catch {
    // DB not available — proceed with defaults
  }

  const args = [
    playbookPath,
    "-i", INVENTORY_PATH,
    "-u", "brajam",
    "--private-key", sshKey,
    "--become",
  ];

  if (roles.length > 0) {
    args.push("--tags", ...roles);
  }

  const proc: ChildProcess = spawn("ansible-playbook", args, {
    cwd: ANSIBLE_DIR,
    shell: false,
    stdio: ["pipe", "pipe", "pipe"],
    env: {
      ...process.env,
      ANSIBLE_FORCE_COLOR: "1",
      PYTHONUNBUFFERED: "1",
      BOTRUS_SECRETS_KEY: process.env.BOTRUS_SECRETS_KEY || "",
      BOTRUS_API_URL: process.env.BOTRUS_API_URL || "http://localhost:4000",
      ANSIBLE_BECOME_PASSWORD: becomePassword,
    },
  });

  let fullOutput = "";
  const knownRoles = new Set<string>();

  // Handle process cancellation
  if (signal) {
    const abortHandler = () => {
      proc.kill("SIGTERM");
      emitter.emit("error", new Error("Process cancelled by user"));
      // Also send data notification
      emitter.emit("data", "\n\n\x1b[33m[ Deployment cancelled by user ]\x1b[0m\n");
      cleanup();
    };
    signal.addEventListener("abort", abortHandler, { once: true });
  }

  function parseLine(line: string): void {
    // Check for TASK lines to track role progress
    const taskMatch = line.match(TASK_LINE_RE);
    if (taskMatch) {
      const taskRef = taskMatch[1].trim(); // e.g. "kubernetes : Install kubelet"
      const roleName = taskRef.split(":")[0].trim();

      if (roleName && !knownRoles.has(roleName)) {
        knownRoles.add(roleName);
        emitter.emit("role-progress", {
          role: roleName,
          status: "running" as const,
        });
      }
    }

    // Check for task completion - look for "ok:" / "changed:" / "failed:" prefixed lines
    const okChangedMatch = line.match(/^(ok|changed|failed|skipped|unreachable):\s*\[/);
    if (okChangedMatch) {
      // Extract hostname from brackets: ok: [hostname] => item={...}
      const hostMatch = line.match(/\[([^\]]+)\]/);
      if (hostMatch) {
        // This indicates progress on a host - we can use the last known role
        const action = okChangedMatch[1];
        if (action === "failed" || action === "unreachable") {
          // Mark last role as failed
          const lastRole = Array.from(knownRoles).pop();
          if (lastRole) {
            emitter.emit("role-progress", {
              role: lastRole,
              status: "failed" as const,
            });
          }
        }
      }
    }
  }

  function handleStdout(data: Buffer): void {
    const text = data.toString();
    fullOutput += text;

    // Parse each line for role progress
    const lines = text.split("\n");
    for (const line of lines) {
      if (line.trim()) {
        parseLine(line);
      }
    }

    emitter.emit("data", text);
  }

  function handleStderr(data: Buffer): void {
    const text = data.toString();
    fullOutput += text;
    emitter.emit("data", text);
  }

  function handleClose(code: number | null): void {
    fullOutput += `\n[Process exited with code ${code}]\n`;

    // Mark all known roles as complete (success or failed based on exit code)
    for (const role of knownRoles) {
      emitter.emit("role-progress", {
        role,
        status: code === 0 ? ("success" as const) : ("failed" as const),
      });
    }

    emitter.emit("close", { exitCode: code, fullOutput });
    cleanup();
  }

  function handleError(err: Error): void {
    fullOutput += `\nERROR: ${err.message}\n`;
    emitter.emit("error", err);
    emitter.emit("close", { exitCode: -1, fullOutput });
    cleanup();
  }

  function cleanup(): void {
    proc.stdout?.removeListener("data", handleStdout);
    proc.stderr?.removeListener("data", handleStderr);
    proc.removeListener("close", handleClose);
    proc.removeListener("error", handleError);
  }

  proc.stdout?.on("data", handleStdout);
  proc.stderr?.on("data", handleStderr);
  proc.on("close", handleClose);
  proc.on("error", handleError);

  return emitter;
}
