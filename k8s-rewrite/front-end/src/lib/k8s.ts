import { execFile } from "child_process";
import { promisify } from "util";
import { existsSync } from "fs";
import { homedir } from "os";

const execFileAsync = promisify(execFile);

const KUBECONFIG_PATH = `${homedir()}/.kube/config`;
const HAS_LOCAL_KUBECTL = existsSync(KUBECONFIG_PATH);

const SSH_KEY = "/home/brajam/.ssh/id_ed25519";
const SSH_OPTS = [
  "-o", "StrictHostKeyChecking=no",
  "-o", "ConnectTimeout=5",
  "-o", "BatchMode=yes",
];

/**
 * Execute a kubectl command locally (preferred) or via SSH on a remote node.
 * Returns parsed JSON on success, or null if kubectl fails.
 */
export async function kubectlJSON(
  host: string,
  cmd: string,
  timeoutMs = 15000
): Promise<any | null> {
  // Prefer local kubectl if kubeconfig exists
  if (HAS_LOCAL_KUBECTL) {
    try {
      const { stdout } = await execFileAsync(
        "kubectl",
        ["--kubeconfig", KUBECONFIG_PATH, ...cmd.split(" "), "-o", "json"],
        { timeout: timeoutMs, maxBuffer: 2 * 1024 * 1024 }
      );
      if (!stdout.trim()) return null;
      return JSON.parse(stdout);
    } catch {
      return null;
    }
  }

  // Fallback: SSH-based kubectl with sudo password pipe
  // (only used when no local kubeconfig is available)
  try {
    const prisma = (await import("./db")).default;
    const pwVar = await prisma.variable.findUnique({
      where: { key: "ansible_become_password" },
    });
    const sudoPass = pwVar?.value || "";
    const sudoPrefix = sudoPass ? `echo '${sudoPass}' | sudo -S ` : "sudo ";
    const fullCmd = `${sudoPrefix}kubectl --kubeconfig=/etc/kubernetes/admin.conf ${cmd} -o json 2>/dev/null`;
    const args = [...SSH_OPTS, "-i", SSH_KEY, `brajam@${host}`, fullCmd];

    const { stdout } = await execFileAsync("ssh", args, {
      timeout: timeoutMs,
      maxBuffer: 2 * 1024 * 1024,
    });
    if (!stdout.trim()) return null;
    const cleaned = stdout.split("\n").filter(l => !l.startsWith("[sudo]")).join("\n");
    return JSON.parse(cleaned);
  } catch {
    return null;
  }
}

/**
 * Execute a raw SSH command and return stdout as string (or null on failure).
 */
export async function sshExec(
  host: string,
  cmd: string,
  timeoutMs = 10000
): Promise<string | null> {
  const args = [...SSH_OPTS, "-i", SSH_KEY, `brajam@${host}`, cmd];

  try {
    const { stdout } = await execFileAsync("ssh", args, {
      timeout: timeoutMs,
      maxBuffer: 1024 * 1024, // 1MB
    });
    return stdout;
  } catch {
    return null;
  }
}
