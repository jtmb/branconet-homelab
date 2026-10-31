class KubernetesCommandErrorImplementation extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

// Next route bundles share the process-wide kubectl client. Its errors must use
// the same constructor as each route's instanceof gate, including after reload.
const errorGlobals = globalThis as typeof globalThis & {
  __bortusKubernetesCommandError?: typeof KubernetesCommandErrorImplementation;
};
export const KubernetesCommandError = errorGlobals.__bortusKubernetesCommandError ??= KubernetesCommandErrorImplementation;
export type KubernetesCommandError = KubernetesCommandErrorImplementation;

/** Host-shell failures never return captured output or dynamic error text. */
export function operatorCommandFailure(error: unknown): KubernetesCommandError {
  const err = (error || {}) as { code?: string | number; killed?: boolean };
  if (err.code === "ENOENT") return new KubernetesCommandError(503, "Operator shell is unavailable");
  if (err.code === "ERR_CHILD_PROCESS_STDIO_MAXBUFFER") return new KubernetesCommandError(502, "Operator command response exceeds the size limit");
  if (err.killed) return new KubernetesCommandError(504, "Operator command timed out");
  return new KubernetesCommandError(502, "Operator command failed");
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

export const POD_LIST_MAX_BYTES = 8 * 1024 * 1024;
export const POD_LIST_MAX_ITEMS = 10000;

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
  async function execBounded(args: readonly string[], timeoutMs: number, maxBuffer: number): Promise<string> {
    if (!Array.isArray(args) || !args.length || args.some(arg => typeof arg !== "string" || arg.includes("\0")) || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30000)
      throw new KubernetesCommandError(400, "Invalid Kubernetes arguments");
    if (!credentialsAvailable()) throw new KubernetesCommandError(503, "Kubernetes credentials unavailable");
    const deadline = Date.now() + timeoutMs;
    await acquire(timeoutMs);
    try {
      const remaining = deadline - Date.now();
      if (remaining <= 0) throw new KubernetesCommandError(504, "Kubernetes request timed out while queued");
      const { stdout } = await execute([...configArgs(), ...args], { timeout: remaining, maxBuffer });
      if (typeof stdout !== "string" || Buffer.byteLength(stdout, "utf8") > maxBuffer)
        throw new KubernetesCommandError(502, "Cluster response exceeds the size limit");
      return stdout;
    } catch (error) { throw error instanceof KubernetesCommandError ? error : failure(error); }
    finally { release(); }
  }
  const exec = (args: readonly string[], timeoutMs = 10000) => execBounded(args, timeoutMs, 2 * 1024 * 1024);
  return {
    exec,
    /** Trusted complete all-namespace Pod list only; callers cannot select a resource or byte ceiling. */
    async listPods(timeoutMs = 10000): Promise<{ items: any[] }> {
      const deadline = Date.now() + timeoutMs;
      const stdout = await execBounded(["get", "pods", "-A", "-o", "json"], timeoutMs, POD_LIST_MAX_BYTES);
      let value: any;
      try { value = JSON.parse(stdout); }
      catch { throw new KubernetesCommandError(502, "Invalid Kubernetes JSON response"); }
      if (!value || typeof value !== "object" || Array.isArray(value) || !Array.isArray(value.items)
        || value.items.length > POD_LIST_MAX_ITEMS || (value.kind !== undefined && !["PodList", "List"].includes(value.kind))
        || value.items.some((item: any) => !item || typeof item !== "object" || Array.isArray(item) || (item.kind !== undefined && item.kind !== "Pod"))
        || (value.metadata !== undefined && (!value.metadata || typeof value.metadata !== "object" || Array.isArray(value.metadata))))
        throw new KubernetesCommandError(502, "Cluster list exceeds limits or has an invalid shape");
      const metadata = value.metadata;
      if (metadata && ((metadata.continue !== undefined && metadata.continue !== "")
        || (metadata.remainingItemCount !== undefined && metadata.remainingItemCount !== 0)))
        throw new KubernetesCommandError(502, "Incomplete Kubernetes Pod list");
      if (Date.now() >= deadline) throw new KubernetesCommandError(504, "Kubernetes request timed out");
      return value;
    },
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
