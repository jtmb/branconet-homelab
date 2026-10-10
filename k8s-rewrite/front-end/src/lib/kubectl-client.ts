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
  if (/\bConflict\b|object has been modified/i.test(err.stderr || "")) return new KubernetesCommandError(409, "Kubernetes resource changed; refresh before retrying");
  if (/\bBadRequest\b|\bInvalid\b/i.test(err.stderr || "")) return new KubernetesCommandError(400, "Kubernetes rejected the request");
  return new KubernetesCommandError(502, "Kubernetes command failed");
}

export function createKubectlClient(execute: Executor, credentialsAvailable: () => boolean, configArgs: () => string[], limits = { concurrent: 4, queued: 64 }) {
  let active = 0;
  const queue: { enter: () => void; timer: ReturnType<typeof setTimeout> }[] = [];
  const acquire = (timeout: number) => new Promise<void>((resolve, reject) => {
    if (active < limits.concurrent) { active++; resolve(); return; }
    if (queue.length >= limits.queued) { reject(new KubernetesCommandError(503, "Cluster command queue is full")); return; }
    const waiter = {
      enter: () => { clearTimeout(waiter.timer); active++; resolve(); },
      timer: setTimeout(() => {
        const index = queue.indexOf(waiter);
        if (index >= 0) queue.splice(index, 1);
        reject(new KubernetesCommandError(504, "Kubernetes request timed out while queued"));
      }, timeout),
    };
    queue.push(waiter);
  });
  const release = () => { active--; queue.shift()?.enter(); };
  async function exec(args: readonly string[], timeoutMs = 10000): Promise<string> {
    if (!Array.isArray(args) || !args.length || args.some(arg => typeof arg !== "string" || arg.includes("\0")) || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30000)
      throw new KubernetesCommandError(400, "Invalid Kubernetes arguments");
    if (!credentialsAvailable()) throw new KubernetesCommandError(503, "Kubernetes credentials unavailable");
    const deadline = Date.now() + timeoutMs;
    await acquire(timeoutMs);
    try {
      const remaining = deadline - Date.now();
      if (remaining <= 0) throw new KubernetesCommandError(504, "Kubernetes request timed out while queued");
      const { stdout } = await execute([...configArgs(), ...args], { timeout: remaining, maxBuffer: 2 * 1024 * 1024 });
      return stdout;
    } catch (error) { throw error instanceof KubernetesCommandError ? error : failure(error); }
    finally { release(); }
  }
  return {
    exec,
    async json(args: readonly string[], timeoutMs = 10000): Promise<any> {
      if (!Array.isArray(args)) throw new KubernetesCommandError(400, "Invalid Kubernetes arguments");
      const stdout = await exec([...args, "-o", "json"], timeoutMs);
      try {
        const value = JSON.parse(stdout);
        if (!value || typeof value !== "object") throw Error();
        return value;
      } catch { throw new KubernetesCommandError(502, "Invalid Kubernetes JSON response"); }
    },
    diagnostics: () => ({ active, queued: queue.length, maxConcurrent: limits.concurrent, maxQueued: limits.queued }),
  };
}
