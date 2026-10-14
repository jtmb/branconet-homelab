import { compareValues, type SortKind } from "./table-sort";

type LegacyCollection = "pods" | "deployments" | "nodes" | "storage" | "storageClasses" | "services" | "ingresses" | "namespaces";
const kinds: Partial<Record<LegacyCollection, Readonly<Record<string, SortKind>>>> = {
  pods: { restarts: "number", ready: "count", created: "date" },
  deployments: { ready: "count", upToDate: "number", available: "number", restarts: "number", age: "date" },
  nodes: { cpu: "number", mem: "number", pods: "number", age: "age" },
  storage: { capacity: "quantity" },
  ingresses: { age: "age" },
};

/** Sort the existing legacy rows without changing their identities or caller filters. */
export function sortLegacyClusterRows<T extends object>(rows: readonly T[], collection: LegacyCollection, key: string, direction: "asc" | "desc"): T[] {
  const field = collection === "nodes" && key === "mem" ? "memory"
    : collection === "deployments" && key === "age" ? "created" : key;
  const kind = kinds[collection]?.[key] ?? "text";
  const identity = collection === "nodes" ? "hostname" : "name";
  return [...rows].sort((a, b) => compareValues(Reflect.get(a, field), Reflect.get(b, field), kind, direction)
    || compareValues(Reflect.get(a, identity), Reflect.get(b, identity))
    || compareValues(Reflect.get(a, "namespace"), Reflect.get(b, "namespace")));
}
