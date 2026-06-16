import { execFile, spawn, ChildProcess } from "child_process";
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
 * Run a command via SSH with sudo, piping the become password securely
 * through stdin (never in argv / process list).
 *
 * Reads ansible_become_password from the Botrus DB and feeds it to
 * sudo -S on the remote host.
 */
async function sshWithSudo(
  host: string,
  kubectlCmd: string,
  timeoutMs: number
): Promise<string | null> {
  let prisma;
  try {
    prisma = (await import("./db")).default;
  } catch {
    return null;
  }

  const pwVar = await prisma.variable.findUnique({
    where: { key: "ansible_become_password" },
  });
  const sudoPass = pwVar?.value;

  const remoteCmd = sudoPass
    ? `sudo -S kubectl --kubeconfig=/etc/kubernetes/admin.conf ${kubectlCmd} 2>/dev/null`
    : `sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf ${kubectlCmd} 2>/dev/null`;

  const sshArgs = [...SSH_OPTS, "-i", SSH_KEY, `brajam@${host}`, remoteCmd];

  return new Promise((resolve) => {
    const child: ChildProcess = spawn("ssh", sshArgs, {
      stdio: ["pipe", "pipe", "pipe"],
    });

    const chunks: Buffer[] = [];
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill();
    }, timeoutMs);

    child.stdout?.on("data", (d: Buffer) => chunks.push(d));

    child.on("close", (code) => {
      clearTimeout(timer);
      if (timedOut) { resolve(null); return; }
      const stdout = Buffer.concat(chunks).toString("utf8").trim();
      if (!stdout || code !== 0) { resolve(null); return; }
      const cleaned = stdout
        .split("\n")
        .filter((l) => !l.startsWith("[sudo]"))
        .join("\n");
      resolve(cleaned || null);
    });

    child.on("error", () => {
      clearTimeout(timer);
      resolve(null);
    });

    // Pipe the password through stdin — never touches argv
    if (sudoPass) {
      child.stdin?.write(sudoPass + "\n");
      child.stdin?.end();
    }
  });
}

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

  // Fallback: SSH-based kubectl with sudo password on stdin (never in argv)
  // (only used when no local kubeconfig is available)
  const stdout = await sshWithSudo(host, `${cmd} -o json`, timeoutMs);
  if (!stdout) return null;
  try { return JSON.parse(stdout); } catch { return null; }
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

/**
 * Execute a raw kubectl command (no -o json). Returns stdout string or null.
 * Prefers local kubectl, falls back to SSH.
 */
export async function kubectlExec(
  cmd: string,
  timeoutMs = 10000
): Promise<string | null> {
  if (HAS_LOCAL_KUBECTL) {
    try {
      const { stdout } = await execFileAsync(
        "kubectl",
        ["--kubeconfig", KUBECONFIG_PATH, ...cmd.split(" ")],
        { timeout: timeoutMs, maxBuffer: 2 * 1024 * 1024 }
      );
      return stdout;
    } catch {
      return null;
    }
  }

  // Fallback: SSH with sudo password on stdin (never in argv)
  const stdout = await sshWithSudo("u1", cmd, timeoutMs);
  return stdout || null;
}
