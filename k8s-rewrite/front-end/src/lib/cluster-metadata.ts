// Resource JSON is metadata. Raw YAML and logs have a separate operator gate.
// Workload templates can otherwise expose credentials through env/args or
// value-bearing annotations even when the resource itself is not a Secret.
const pick = (object: Record<string, unknown> | undefined, keys: readonly string[]) => Object.fromEntries(keys.filter(key => object && Object.hasOwn(object, key)).map(key => [key, object![key]]));
export function publicClusterMetadata(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(publicClusterMetadata);
  if (!value || typeof value !== "object") return value;
  const object = value as Record<string, unknown>;
  const result = Object.create(null) as Record<string, unknown>;
  for (const [key, child] of Object.entries(object)) {
    if (key === "metadata") {
      result.metadata = publicClusterMetadata(pick(child as Record<string, unknown>, ["name", "namespace", "uid", "resourceVersion", "creationTimestamp", "generation", "deletionTimestamp", "labels", "ownerReferences"]));
    } else if (["annotations", "managedFields", "env", "envFrom", "command", "args", "data", "stringData", "binaryData", "volumeAttributes"].includes(key)) {
      continue;
    } else if (key === "message" && (Object.hasOwn(object, "reason") || Object.hasOwn(object, "type") || Object.hasOwn(object, "exitCode"))) {
      continue;
    } else result[key] = publicClusterMetadata(child);
  }
  return result;
}
