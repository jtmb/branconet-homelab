import type { Consumer, ImageReport, Inventory } from "./system-report-types";

interface Owner { kind?: string; name?: string; uid?: string; controller?: boolean }
interface Metadata { name?: string; namespace?: string; uid?: string; labels?: Record<string, string>; ownerReferences?: Owner[] }
interface ContainerStatus { name?: string; image?: string; imageID?: string; state?: { running?: object } }
interface Pod {
  metadata?: Metadata; spec?: { containers?: { name?: string; image?: string }[]; initContainers?: { name?: string; image?: string }[]; ephemeralContainers?: { name?: string; image?: string }[] };
  status?: { containerStatuses?: ContainerStatus[]; initContainerStatuses?: ContainerStatus[]; ephemeralContainerStatuses?: ContainerStatus[] };
}
interface Service { metadata?: Metadata; spec?: { selector?: Record<string, string> } }
interface ReplicaSet { metadata?: Metadata }
export interface InventorySnapshot {
  pods: Pod[] | undefined; services: Service[] | undefined; replicasets: ReplicaSet[] | undefined;
  sampledAt: string | null; stale: boolean;
}
const controller = (meta?: Metadata) => meta?.ownerReferences?.find(owner => owner.controller === true);

/** Runtime pullable digest only. Opaque CRI/config IDs cannot establish a registry manifest identity. */
export function runtimeImage(imageID: string | undefined): { digest: string; reference: string } | null {
  if (!imageID || imageID.length > 512) return null;
  const reference = imageID.replace(/^docker-pullable:\/\//, "");
  const match = /^([a-z0-9][a-z0-9._:/-]*)@(sha256:[a-f0-9]{64})$/.exec(reference);
  if (!match || match[1].includes("..") || match[1].includes("://")) return null;
  return { digest: match[2], reference };
}

export function workloadInventory(snapshot: InventorySnapshot): Inventory {
  const warnings: string[] = [];
  if (!snapshot.pods) warnings.push("Pod inventory unavailable. Coverage is unknown; no clean-cluster claim is possible.");
  if (!snapshot.services) warnings.push("Service mapping unavailable.");
  if (!snapshot.replicasets) warnings.push("Deployment ownership unavailable; direct controllers are shown.");
  if (snapshot.stale) warnings.push("Cluster inventory is stale. Refresh before acting on these consumers.");
  const images = new Map<string, ImageReport>();
  const replicaOwners = new Map((snapshot.replicasets ?? []).map(rs => [rs.metadata?.uid, rs.metadata]));
  let runningContainers = 0;
  for (const pod of snapshot.pods ?? []) {
    const namespace = pod.metadata?.namespace ?? "default", podName = pod.metadata?.name ?? "Unknown Pod";
    const owner = controller(pod.metadata);
    const replica = owner?.kind === "ReplicaSet" && owner.uid ? replicaOwners.get(owner.uid) : undefined;
    const parent = replica?.namespace === namespace ? controller(replica) : undefined;
    const workload = parent?.kind === "Deployment" ? `Deployment/${parent.name}` : owner ? `${owner.kind}/${owner.name}` : `Pod/${podName}`;
    const services = snapshot.services?.filter(service => {
      const selector = service.spec?.selector;
      return service.metadata?.namespace === namespace && selector && Object.keys(selector).length > 0 &&
        Object.entries(selector).every(([key, value]) => pod.metadata?.labels?.[key] === value);
    }).map(service => service.metadata?.name ?? "Unknown Service") ?? null;
    const groups = [
      ["container", pod.status?.containerStatuses, pod.spec?.containers],
      ["init", pod.status?.initContainerStatuses, pod.spec?.initContainers],
      ["ephemeral", pod.status?.ephemeralContainerStatuses, pod.spec?.ephemeralContainers],
    ] as const;
    for (const [kind, statuses, specifications] of groups) for (const status of statuses ?? []) {
      if (!status.state?.running) continue;
      runningContainers++;
      const identity = runtimeImage(status.imageID);
      const alias = specifications?.find(c => c.name === status.name)?.image ?? status.image ?? "Unknown image";
      const key = identity?.digest ?? `unknown:${namespace}/${podName}/${kind}/${status.name}`;
      const consumer: Consumer = { cluster: "Connected cluster", namespace, pod: podName, container: status.name ?? "Unknown container", kind, workload, services };
      let image = images.get(key);
      if (!image) {
        image = { key, digest: identity?.digest ?? null, reference: identity?.reference ?? null, aliases: [], consumers: [],
          state: identity ? "unscanned" : "unsupported", findings: [],
          ...(!identity ? { message: "Runtime registry digest unavailable. A mutable tag or opaque local image ID cannot prove the running image." } : {}) };
        images.set(key, image);
      }
      if (!image.aliases.includes(alias)) image.aliases.push(alias);
      image.consumers.push(consumer);
    }
  }
  return { images: [...images.values()], sampledAt: snapshot.sampledAt, warnings,
    available: snapshot.pods !== undefined, stale: snapshot.stale, runningContainers };
}
