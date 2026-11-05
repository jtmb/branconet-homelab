import type { KvRotation } from "@prisma/client";
import { KvError } from "./kv-contract";
import { validateTarget } from "./cluster-secrets";

export const ROTATION_MARKER = "bortus.io/rotation-id";
export type ConsumerMetadata = { uid: string; resourceVersion: string; rotationId?: string };
export interface RotationConsumerTransport {
  inspect(row: KvRotation): Promise<ConsumerMetadata>;
  reload(row: KvRotation, expected: ConsumerMetadata): Promise<ConsumerMetadata>;
}
type JsonCommand = (args: readonly string[], timeoutMs?: number) => Promise<any>;

/** Structured kubectl with UID/RV JSON Patch conditions; command arguments contain no credential values. */
export class KubectlRotationConsumer implements RotationConsumerTransport {
  constructor(readonly json: JsonCommand) {}
  private args(row: KvRotation) {
    if (!["Deployment", "StatefulSet", "DaemonSet"].includes(row.consumerKind)) throw new KvError(400, "Unsupported rotation consumer");
    validateTarget({ namespace: row.consumerNamespace, name: row.consumerName, key: "consumer" });
    return [row.consumerKind.toLowerCase(), row.consumerName, "-n", row.consumerNamespace];
  }
  private metadata(row: KvRotation, object: any): ConsumerMetadata {
    if (object?.apiVersion !== "apps/v1" || object.kind !== row.consumerKind || object.metadata?.namespace !== row.consumerNamespace || object.metadata?.name !== row.consumerName ||
      typeof object.metadata.uid !== "string" || !object.metadata.uid || object.metadata.uid.length > 128 || typeof object.metadata.resourceVersion !== "string" || !object.metadata.resourceVersion || object.metadata.resourceVersion.length > 128 ||
      !object.spec?.template?.spec) throw new KvError(409, "Consumer identity or template changed; refresh before reload");
    const rotationId = object.spec.template.metadata?.annotations?.[ROTATION_MARKER];
    return { uid: object.metadata.uid, resourceVersion: object.metadata.resourceVersion, ...(typeof rotationId === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(rotationId) ? { rotationId } : {}) };
  }
  async inspect(row: KvRotation) {
    try { return this.metadata(row, await this.json(["get", ...this.args(row)], 8000)); }
    catch (error) { if (error instanceof KvError) throw error; throw new KvError(503, "Named consumer metadata unavailable"); }
  }
  async reload(row: KvRotation, expected: ConsumerMetadata) {
    try {
      const args = this.args(row), object = await this.json(["get", ...args], 8000), current = this.metadata(row, object);
      if (current.uid !== expected.uid || current.resourceVersion !== expected.resourceVersion) throw new KvError(409, "Consumer changed; reload was not requested");
      if (current.rotationId === row.id) return current;
      const patch: Record<string, unknown>[] = [{ op: "test", path: "/metadata/uid", value: expected.uid }, { op: "test", path: "/metadata/resourceVersion", value: expected.resourceVersion }];
      if (!object.spec.template.metadata) patch.push({ op: "add", path: "/spec/template/metadata", value: {} });
      if (!object.spec.template.metadata?.annotations) patch.push({ op: "add", path: "/spec/template/metadata/annotations", value: {} });
      patch.push({ op: "add", path: "/spec/template/metadata/annotations/bortus.io~1rotation-id", value: row.id });
      return this.metadata(row, await this.json(["patch", ...args, "--type=json", "-p", JSON.stringify(patch)], 8000));
    } catch (error) { if (error instanceof KvError) throw error; throw new KvError(503, "Consumer reload outcome unavailable; inspect rotation before retrying"); }
  }
}
