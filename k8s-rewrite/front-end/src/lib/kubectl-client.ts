export class KubernetesCommandError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

export function validateResourceName(value: string): string {
  if (typeof value !== "string" || value.length > 253 || !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*$/.test(value))
    throw new KubernetesCommandError(400, "Invalid Kubernetes resource name");
  return value;
}
export function validateNamespace(value: string): string {
  if (typeof value !== "string" || value.length > 63 || !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(value))
    throw new KubernetesCommandError(400, "Invalid Kubernetes namespace");
  return value;
}

type Executor = (args: string[], options: { timeout: number; maxBuffer: number }) => Promise<{ stdout: string }>;

function failure(error: unknown): KubernetesCommandError {
  const err = (error || {}) as { code?: string | number; killed?: boolean; stderr?: string };
  if (err.code === "ENOENT") return new KubernetesCommandError(503, "kubectl is unavailable");
  if (err.code === "ERR_CHILD_PROCESS_STDIO_MAXBUFFER") return new KubernetesCommandError(502, "Cluster response exceeds the size limit");
  if (err.killed) return new KubernetesCommandError(504, "Kubernetes request timed out");
  if (/\bForbidden\b/i.test(err.stderr || "")) return new KubernetesCommandError(403, "Kubernetes permission denied");
  if (/\bNotFound\b/i.test(err.stderr || "")) return new KubernetesCommandError(404, "Kubernetes resource not found");
  return new KubernetesCommandError(502, "Kubernetes command failed");
}

export function createKubectlClient(execute: Executor, credentialsAvailable: () => boolean, configArgs: () => string[]) {
  return {
    async exec(args: readonly string[], timeoutMs = 10000): Promise<string> {
      if (!Array.isArray(args) || !args.length || args.some(arg => typeof arg !== "string" || arg.includes("\0")))
        throw new KubernetesCommandError(400, "Invalid Kubernetes arguments");
      if (!credentialsAvailable()) throw new KubernetesCommandError(503, "Kubernetes credentials unavailable");
      try {
        const { stdout } = await execute([...configArgs(), ...args], { timeout: timeoutMs, maxBuffer: 2 * 1024 * 1024 });
        return stdout;
      } catch (error) { throw failure(error); }
    },
  };
}
