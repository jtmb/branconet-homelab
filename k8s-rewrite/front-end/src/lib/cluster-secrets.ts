import type { V1Secret } from "@kubernetes/client-node";

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
export class SecretListBudget {
  items = 0;
  bytes = 0;
  constructor(readonly deadline = Date.now() + 15000) {}
  check() { if (Date.now() >= this.deadline) throw new SecretError(503, "Kubernetes Secret list timed out"); }
  remainingBytes() { this.check(); return SECRET_LIST_MAX_BYTES - this.bytes; }
  consumeBytes(bytes: number) {
    this.check(); this.bytes += bytes;
    if (!Number.isSafeInteger(bytes) || bytes < 0 || this.bytes > SECRET_LIST_MAX_BYTES) throw new SecretError(503, "Kubernetes Secret list exceeds the aggregate byte limit");
  }
  consumeItems(count: number) {
    this.check(); this.items += count;
    if (!Number.isSafeInteger(count) || count < 0 || this.items > SECRET_LIST_MAX_ITEMS) throw new SecretError(503, "Kubernetes Secret list exceeds the aggregate item limit");
  }
}
export type SecretListOptions = { budget?: SecretListBudget; visit?: (secret: V1Secret) => void };
export interface SecretTransport {
  read(namespace: string, name: string): Promise<V1Secret>;
  list(namespace: string, options?: SecretListOptions): Promise<V1Secret[]>;
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
      const budget = new SecretListBudget(), summaries: ReturnType<typeof secretSummary>[] = [];
      for (const scope of scopes) {
        budget.check();
        const full = await this.transport.list(scope, { budget, visit: secret => { summaries.push(secretSummary(secret)); } });
        // Compatibility transports may return full records instead of visiting pages.
        for (const secret of full) {
          budget.consumeBytes(Buffer.byteLength(JSON.stringify(secret))); budget.consumeItems(1);
          summaries.push(secretSummary(secret));
        }
      }
      budget.check(); return summaries;
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
