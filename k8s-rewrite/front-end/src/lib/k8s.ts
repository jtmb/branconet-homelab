import { execFile } from "child_process";
import { promisify } from "util";
import { existsSync, mkdirSync, writeFileSync } from "fs";
import { homedir } from "os";
import { createKubectlClient } from "./kubectl-client";
import { executeOperatorCommand } from "./operator-command";
export { KubernetesCommandError, validateNamespace, validateResourceName } from "./kubectl-client";

const execFileAsync = promisify(execFile);

export const KUBECONFIG_PATH = process.env.KUBECONFIG || `${homedir()}/.kube/config`;
const kubectlConfigArgs = () => process.env.KUBERNETES_SERVICE_HOST && !process.env.KUBECONFIG ? [] : ["--kubeconfig", KUBECONFIG_PATH];

/** Check at call time whether a local kubeconfig is available. */
export function hasLocalKubectl(): boolean {
  return Boolean(process.env.KUBERNETES_SERVICE_HOST) || existsSync(KUBECONFIG_PATH);
}

const SSH_KEY = "/home/brajam/.ssh/id_ed25519";
const SSH_OPTS = [
  "-o", "StrictHostKeyChecking=no",
  "-o", "ConnectTimeout=5",
  "-o", "BatchMode=yes",
];

/**
 * Execute structured kubectl arguments with verified process outcome and JSON parsing.
 */
export async function kubectlJSON(
  args: readonly string[],
  timeoutMs = 15000
): Promise<any> { return kubectl.json(args, timeoutMs); }

/**
 * Execute a raw SSH command and return stdout as string (or null on failure).
 *
 * BOOTSTRAP-ONLY â€” used exclusively by ensureKubeconfig() to fetch the initial
 * kubeconfig from the master node. Never called from kubectl hot paths.
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
 * Shared bounded process pool for structured kubectl commands.
 */
const globals = globalThis as typeof globalThis & { __bortusKubectl?: ReturnType<typeof createKubectlClient> };
const kubectl = globals.__bortusKubectl ??= createKubectlClient(
  (args, options) => execFileAsync("kubectl", args, options),
  hasLocalKubectl,
  kubectlConfigArgs,
);
export const kubectlExec = kubectl.exec;
export const kubectlPodList = kubectl.listPods;
export const kubectlDiagnostics = kubectl.diagnostics;

// â”€â”€ Operator shell working-directory helper â”€â”€
const SHELL_HOME = "/home/shell";
const RESTRICTED_BASHRC = `${SHELL_HOME}/.restricted_bashrc`;

/** One-time setup: create /home/shell and a restricted bashrc that blocks cd outside it. */
function ensureRestrictedShell() {
  if (!existsSync(SHELL_HOME)) {
    mkdirSync(SHELL_HOME, { recursive: true });
  }
  if (!existsSync(RESTRICTED_BASHRC)) {
    writeFileSync(
      RESTRICTED_BASHRC,
      `# Botrus K8s restricted shell â€” do not edit\n` +
      `# Override cd to prevent escaping /home/shell\n` +
      `cd() {\n` +
      `  local target="\${1:-\$HOME}"\n` +
      `  local real\n` +
      `  real=$(realpath -e "$target" 2>/dev/null || readlink -f "$target" 2>/dev/null || { [[ "$target" = /* ]] && echo "$target" || echo "$(pwd)/$target"; })\n` +
      `  if [[ "\$real" != /home/shell ]] && [[ "\$real" != /home/shell/* ]]; then\n` +
      `    echo "cd: permission denied: outside /home/shell" >&2\n` +
      `    return 1\n` +
      `  fi\n` +
      `  builtin cd "\$target"\n` +
      `}\n` +
      `HOME=/home/shell\n`
    );
  }
}

/**
 * Execute a trusted operator command via bash -c with application-host privileges.
 * The BASH_ENV working-directory helper is not an operating-system sandbox.
 * Only successful stdout is returned; failed output is discarded.
 */
export async function shellExec(
  cmd: string,
  timeoutMs = 30000
): Promise<string> {
  ensureRestrictedShell();
  return executeOperatorCommand(cmd, {
    cwd: SHELL_HOME,
    timeout: timeoutMs,
    maxBuffer: 2 * 1024 * 1024,
    env: {
      ...process.env,
      KUBECONFIG: KUBECONFIG_PATH,
      BASH_ENV: RESTRICTED_BASHRC,
      HOME: SHELL_HOME,
    },
    encoding: "utf8",
  });
}
