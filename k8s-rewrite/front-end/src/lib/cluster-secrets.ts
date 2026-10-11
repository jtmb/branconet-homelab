import type { V1ObjectMeta, V1Secret } from "@kubernetes/client-node";

export class SecretError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export interface SecretTarget {
  namespace: string;
  name: string;
  key: string;
}
export const SECRET_LIST_MAX_ITEMS = 10000;
export const SECRET_LIST_MAX_BYTES = 32 * 1024 * 1024;
export const SECRET_LIST_MAX_CONCURRENCY = 4;
export class SecretListBudget {
  items = 0;
  bytes = 0;
  private failure?: SecretError;
  private cancellation = new AbortController();
  private cleanups = new Set<() => void>();
  readonly signal = this.cancellation.signal;
  constructor(readonly deadline = Date.now() + 15000) {}
  onFinish(cleanup: () => void) { this.check(); this.cleanups.add(cleanup); }
  finish() {
    const cleanups = [...this.cleanups]; this.cleanups.clear();
    for (const cleanup of cleanups) cleanup();
  }
  fail(error: unknown) {
    this.failure ??= secretFailure(error);
    this.cancellation.abort(this.failure);
    this.finish();
  }
  check() {
    if (!this.failure && Date.now() >= this.deadline) this.fail(new SecretError(503, "Kubernetes Secret list timed out"));
    if (this.failure) throw this.failure;
  }
  remainingBytes() { this.check(); return SECRET_LIST_MAX_BYTES - this.bytes; }
  consumeBytes(bytes: number) {
    if (!Number.isSafeInteger(bytes) || bytes < 0) this.fail(new SecretError(503, "Kubernetes Secret list exceeds the aggregate byte limit"));
    else this.bytes += bytes; // Include delivered late chunks after cancellation; never buffer them.
    if (this.bytes > SECRET_LIST_MAX_BYTES) this.fail(new SecretError(503, "Kubernetes Secret list exceeds the aggregate byte limit"));
    this.check();
  }
  consumeItems(count: number) {
    this.check();
    if (!Number.isSafeInteger(count) || count < 0) this.fail(new SecretError(503, "Kubernetes Secret list exceeds the aggregate item limit"));
    else this.items += count;
    if (this.items > SECRET_LIST_MAX_ITEMS) this.fail(new SecretError(503, "Kubernetes Secret list exceeds the aggregate item limit"));
    this.check();
  }
}
export type SecretListOptions = { budget?: SecretListBudget; visit?: (secret: V1Secret) => void };
export interface NativeSecretSummary { metadata: V1ObjectMeta; type: string; immutable: boolean; keys: string[] }
export type SecretSummaryListOptions = { budget?: SecretListBudget; visit?: (summary: NativeSecretSummary) => void };
export interface SecretTransport {
  read(namespace: string, name: string): Promise<V1Secret>;
  list(namespace: string, options?: SecretListOptions): Promise<V1Secret[]>;
  listSummaries?(namespace: string, options?: SecretSummaryListOptions): Promise<NativeSecretSummary[]>;
  create(namespace: string, body: V1Secret): Promise<V1Secret>;
  replace(namespace: string, name: string, body: V1Secret): Promise<V1Secret>;
}
export type FlatSecretGuard = (action: "read" | "create" | "update" | "delete", target: SecretTarget, secret?: V1Secret) => Promise<void>;
const dnsLabel = /^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$/;
const dnsName = /^[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?$/;
export function validateTarget(target: SecretTarget): SecretTarget {
  if (
    !target ||
    typeof target.namespace !== "string" ||
    target.namespace.length > 63 ||
    !dnsLabel.test(target.namespace) ||
    typeof target.name !== "string" ||
    target.name.length > 253 ||
    !dnsName.test(target.name) ||
    target.name
      .split(".")
      .some((label) => label.length > 63 || !dnsLabel.test(label)) ||
    typeof target.key !== "string" ||
    target.key.length > 253 ||
    !/^[-._a-zA-Z0-9]+$/.test(target.key)
  ) {
    throw new SecretError(
      400,
      "Explicit namespace, Secret name and data key are required",
    );
  }
  return target;
}
// Kubernetes exception bodies can contain submitted values. Only fixed messages leave this boundary.
export function secretFailure(error: unknown): SecretError {
  if (error instanceof SecretError) return error;
  const code = Number(
    (error as { code?: number; statusCode?: number })?.code ||
      (error as { statusCode?: number })?.statusCode,
  );
  if (code === 404)
    return new SecretError(404, "Kubernetes Secret or key not found");
  if (code === 409)
    return new SecretError(
      409,
      "Secret changed or already exists; refresh before retrying",
    );
  if (code === 401 || code === 403)
    return new SecretError(
      503,
      "Kubernetes credentials or Secret RBAC denied access",
    );
  if (code === 422 || code === 400)
    return new SecretError(400, "Kubernetes rejected the Secret change");
  return new SecretError(
    503,
    "Kubernetes Secrets unavailable; no database fallback is permitted",
  );
}
export function secretSummary(secret: V1Secret) {
  return {
    namespace: secret.metadata?.namespace,
    name: secret.metadata?.name,
    resourceVersion: secret.metadata?.resourceVersion,
    type: secret.type || "Opaque",
    immutable: secret.immutable === true,
    keys: Object.keys(secret.data || {}).sort(),
  };
}
export class SecretStore {
  constructor(
    private transport: SecretTransport,
    private namespaces: string[],
    private guard?: FlatSecretGuard,
    private listConcurrency = 1,
  ) {}
  private check(target: SecretTarget) {
    validateTarget(target);
    if (!this.namespaces.includes(target.namespace))
      throw new SecretError(
        403,
        "Namespace is outside the configured Secret scope",
      );
  }
  async list(namespace?: string) {
    const scopes = namespace ? [namespace] : this.namespaces;
    for (const scope of scopes)
      this.check({ namespace: scope, name: "scope", key: "scope" });
    try {
      if (!Number.isSafeInteger(this.listConcurrency) || this.listConcurrency < 1 || this.listConcurrency > SECRET_LIST_MAX_CONCURRENCY)
        throw new SecretError(503, "Invalid Kubernetes Secret list concurrency");
      const budget = new SecretListBudget(), summaries: ReturnType<typeof secretSummary>[][] = scopes.map(() => []);
      let next = 0;
      const worker = async () => {
        try {
          while (next < scopes.length) {
            budget.check(); const index = next++, scope = scopes[index];
            if (this.transport.listSummaries) {
              const project = (summary: NativeSecretSummary) => { budget.check(); summaries[index].push({ namespace: summary.metadata.namespace, name: summary.metadata.name,
                resourceVersion: summary.metadata.resourceVersion, type: summary.type, immutable: summary.immutable, keys: summary.keys }); };
              const metadata = await this.transport.listSummaries(scope, { budget, visit: project });
              for (const summary of metadata) { budget.consumeBytes(Buffer.byteLength(JSON.stringify(summary))); budget.consumeItems(1); project(summary); }
              continue;
            }
            const full = await this.transport.list(scope, { budget, visit: secret => { budget.check(); summaries[index].push(secretSummary(secret)); } });
            // Compatibility transports may return full records instead of visiting pages.
            for (const secret of full) {
              budget.consumeBytes(Buffer.byteLength(JSON.stringify(secret))); budget.consumeItems(1);
              summaries[index].push(secretSummary(secret));
            }
          }
        } catch (error) { budget.fail(error); }
      };
      // Workers settle before returning an error, so no owned request/queue entry is left behind.
      try {
        await Promise.all(Array.from({ length: Math.min(this.listConcurrency, scopes.length) }, worker));
        budget.check(); return summaries.flat();
      } finally { budget.finish(); }
    } catch (error) {
      throw secretFailure(error);
    }
  }
  async read(target: SecretTarget) {
    this.check(target);
    try {
      const secret = await this.transport.read(target.namespace, target.name);
      await this.guard?.("read", target, secret);
      if (!Object.hasOwn(secret.data || {}, target.key))
        throw new SecretError(404, "Kubernetes Secret key not found");
      const bytes = Buffer.from(secret.data![target.key], "base64");
      const value = bytes.toString("utf8");
      if (!Buffer.from(value).equals(bytes))
        throw new SecretError(
          400,
          "Binary Secret keys cannot be edited through the text API",
        );
      return { ...secretSummary(secret), key: target.key, value };
    } catch (error) {
      throw secretFailure(error);
    }
  }
  async write(
    target: SecretTarget,
    value: string,
    mode: "create" | "update",
    resourceVersion?: string,
    type = "Opaque",
  ) {
    this.check(target);
    if (
      typeof value !== "string" ||
      Buffer.byteLength(value) > 1024 * 1024 ||
      !["create", "update"].includes(mode)
    ) {
      throw new SecretError(
        400,
        "A UTF-8 value up to 1 MiB and create/update mode are required",
      );
    }
    if (mode === "update" && !resourceVersion)
      throw new SecretError(428, "resourceVersion is required for updates");
    try {
      let secret: V1Secret;
      try {
        secret = await this.transport.read(target.namespace, target.name);
      } catch (error) {
        if (secretFailure(error).status !== 404 || mode !== "create")
          throw error;
        await this.guard?.("create", target);
        return secretSummary(
          await this.transport.create(target.namespace, {
            apiVersion: "v1",
            kind: "Secret",
            type,
            metadata: { namespace: target.namespace, name: target.name },
            data: { [target.key]: Buffer.from(value).toString("base64") },
          }),
        );
      }
      await this.guard?.(mode, target, secret);
      if (secret.immutable) throw new SecretError(409, "Secret is immutable");
      const exists = Object.hasOwn(secret.data || {}, target.key);
      if (mode === "create" && exists)
        throw new SecretError(
          409,
          "Secret key already exists; use update with resourceVersion",
        );
      if (mode === "update" && !exists)
        throw new SecretError(404, "Secret key not found; use create");
      if (
        resourceVersion &&
        secret.metadata?.resourceVersion !== resourceVersion
      )
        throw new SecretError(409, "Secret changed; refresh before retrying");
      if (!secret.metadata?.resourceVersion)
        throw new SecretError(503, "Kubernetes did not supply resourceVersion");
      // PUT is an atomic compare-and-swap using the fetched version; never retry automatically.
      const body = {
        ...secret,
        data: {
          ...secret.data,
          [target.key]: Buffer.from(value).toString("base64"),
        },
      };
      delete body.stringData;
      return secretSummary(
        await this.transport.replace(target.namespace, target.name, body),
      );
    } catch (error) {
      throw secretFailure(error);
    }
  }
  async deleteKey(target: SecretTarget, resourceVersion: string) {
    this.check(target);
    if (!resourceVersion)
      throw new SecretError(428, "resourceVersion is required for deletion");
    try {
      const secret = await this.transport.read(target.namespace, target.name);
      await this.guard?.("delete", target, secret);
      if (secret.immutable) throw new SecretError(409, "Secret is immutable");
      if (secret.metadata?.resourceVersion !== resourceVersion)
        throw new SecretError(409, "Secret changed; refresh before retrying");
      if (!Object.hasOwn(secret.data || {}, target.key))
        throw new SecretError(404, "Secret key not found");
      const body = { ...secret, data: { ...secret.data } };
      delete body.data[target.key];
      delete body.stringData;
      // Last-key deletion retains the object, type, labels, annotations and owner references.
      return secretSummary(
        await this.transport.replace(target.namespace, target.name, body),
      );
    } catch (error) {
      throw secretFailure(error);
    }
  }
}
