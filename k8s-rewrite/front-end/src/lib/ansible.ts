import { spawn } from "node:child_process";
import { EventEmitter } from "node:events";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { ansibleSelection } from "./ansible-selection";
import { ansibleCallbackSource } from "./ansible-callback";
import { observeAnsibleProcess } from "./ansible-progress";

/** Run the fixed local playbook; only allowlisted structured progress is retained. */
export async function runAnsiblePlaybook(
  playbookFile: string,
  roles: string[] = [],
  signal?: AbortSignal
): Promise<EventEmitter> {
  const selected = ansibleSelection(playbookFile, roles);
  const ansibleDir = path.resolve(process.cwd(), "../ansible-playbook");
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-progress-"));
  async function cleanup() {
    if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-progress-")) return;
    await rm(dir, { recursive: true, force: true });
  }
  try {
    await writeFile(path.join(dir, "bortus_progress.py"), ansibleCallbackSource, { mode: 0o600 });
    // Bootstrap inputs stay independent of the cluster. Only nonsecret paths/usernames enter argv.
    const args = [
      path.join(ansibleDir, "playbooks", selected.playbook),
      "-i", path.join(ansibleDir, "inventory", "production.ini"),
      "-u", process.env.ANSIBLE_REMOTE_USER || "brajam",
      "--private-key", process.env.ANSIBLE_PRIVATE_KEY_FILE || "/home/brajam/.ssh/id_ed25519",
      "--become",
    ];
    if (selected.roles.length) args.push("--tags", selected.roles.join(","));
    const proc = spawn("ansible-playbook", args, {
      cwd: ansibleDir, shell: false, stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        ANSIBLE_STDOUT_CALLBACK: "bortus_progress",
        ANSIBLE_CALLBACK_PLUGINS: dir,
        ANSIBLE_CALLBACKS_ENABLED: "bortus_progress",
        ANSIBLE_FORCE_COLOR: "0",
        ANSIBLE_NOCOLOR: "1",
        ANSIBLE_LOG_PATH: process.platform === "win32" ? "NUL" : "/dev/null",
        ANSIBLE_VERBOSITY: "0",
        PYTHONUNBUFFERED: "1",
        BOTRUS_SECRETS_KEY: process.env.BOTRUS_SECRETS_KEY || "",
        BOTRUS_API_URL: process.env.BOTRUS_API_URL || "http://localhost:4000",
        ANSIBLE_BECOME_PASSWORD: process.env.ANSIBLE_BECOME_PASSWORD || "",
      },
    });
    return observeAnsibleProcess(proc, signal, () => { void cleanup().catch(() => {}); });
  } catch {
    await cleanup().catch(() => {});
    throw new Error("Provisioning runner could not start");
  }
}
