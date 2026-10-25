import { deploymentPods, deploymentState, podRestarts } from "./deployment-state";
import { kubectlJSON, kubectlPodList } from "./k8s";
import { ClusterResourceCache, CLUSTER_RESOURCES, type ClusterResource, type ResourceAvailability } from "./resource-cache";

// =============================================================================
// Per-resource cluster snapshots with 10s TTL and bounded failure retention.
// All cluster API routes read from this cache so the front-end's
// 10s polling interval doesn't hammer kubectl with repeated calls.
// =============================================================================

interface VolumeInfo {
  id: string;
  name: string;
  namespace: string;
  status: string;
  capacity: string;
  node: string;
  storageClass: string;
}

interface ClusterInfo {
  nodes: number;
  readyNodes: number;
  pods: number;
  runningPods: number;
  version: string;
  longhornVolumes: number;
  healthyVolumes: number;
}

export interface CachedData {
  availability: Partial<Record<ClusterResource, ResourceAvailability>>;
  rawReplicaSets: any[];
  info: ClusterInfo;
  nodes: any[];
  pods: any[];
  volumes: VolumeInfo[];
  storageClasses: { name: string; provisioner: string; isDefault: boolean }[];
  namespaces: any[];
  services: any[];
  deployments: any[];
  ingresses: any[];
  rawNamespaces: any[];
  rawServices: any[];
  rawDeployments: any[];
  rawIngresses: any[];
  rawPvcs: any[];
  lastFetch: number;
}

const commands: Record<ClusterResource, string[]> = {
  nodes: ["get", "nodes"], pods: ["get", "pods", "-A"], pv: ["get", "pv"], pvc: ["get", "pvc", "-A"],
  longhorn: ["get", "volumes.longhorn.io", "-A"], sc: ["get", "sc"], namespaces: ["get", "namespaces"],
  services: ["get", "services", "-A"], deployments: ["get", "deployments", "-A"], replicasets: ["get", "replicasets", "-A"], ingresses: ["get", "ingress", "-A"],
};
const globals = globalThis as typeof globalThis & { __bortusResources?: ClusterResourceCache };
const resourcesCache = globals.__bortusResources ??= new ClusterResourceCache(resource => resource === "pods" ? kubectlPodList(10000) : kubectlJSON(commands[resource], 10000));

/**
 * Format a duration in milliseconds to a human-readable age string.
 */
function formatAge(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 365) return `${days}d`;
  const years = Math.floor(days / 365);
  return `${years}y`;
}

/**

 * Fetch all cluster data via local kubectl.
 * Requests only needed resources and builds availability-aware projections.
 */
async function fetchAllClusterData(resources: readonly ClusterResource[]): Promise<CachedData> {
  const snapshots = await resourcesCache.read(resources);
  const [nodesResult, podsResult, pvResult, pvcResult, longhornResult, scResult, nsResult, svcResult, deployResult, ingressResult] =
    (["nodes", "pods", "pv", "pvc", "longhorn", "sc", "namespaces", "services", "deployments", "ingresses"] as const).map(resource => snapshots[resource]?.value);
  const availability = Object.fromEntries(Object.entries(snapshots).map(([resource, snapshot]) => [resource, snapshot.availability]));

  const allNodes = nodesResult?.items || [];
  const allPods = podsResult?.items || [];

  // ── Derived info ──
  const readyNodes = allNodes.filter((n: any) =>
    n.status?.conditions?.some(
      (c: any) => c.type === "Ready" && c.status === "True"
    )
  ).length;

  const runningPods = allPods.filter(
    (p: any) => p.status?.phase === "Running"
  ).length;

  const version =
    allNodes[0]?.status?.nodeInfo?.kubeletVersion?.replace(/^v/, "") || "";

  let longhornVolumes = 0;
  let healthyVolumes = 0;
  if (longhornResult?.items) {
    longhornVolumes = longhornResult.items.length;
    healthyVolumes = longhornResult.items.filter(
      (v: any) =>
        v.status?.robustness === "healthy"
    ).length;
  }

  // ── Volume list (PVs + Longhorn) ──
  const volumes: VolumeInfo[] = [];

  if (pvResult?.items) {
    for (const pv of pvResult.items) {
      const ns = pv.spec?.claimRef?.namespace || "-";
      const name = pv.metadata?.name || "unknown";
      volumes.push({
        id: `pv:${ns}/${name}`,
        name,
        namespace: ns,
        status: pv.status?.phase || "Unknown",
        capacity: pv.spec?.capacity?.storage || "unknown",
        node: pv.metadata?.labels?.["kubernetes.io/hostname"] || "-",
        storageClass: pv.spec?.storageClassName || "none",
      });
    }
  }

  if (longhornResult?.items) {
    for (const lv of longhornResult.items) {
      const ns = lv.metadata?.namespace || "-";
      const name = lv.metadata?.name || "unknown";
      volumes.push({
        id: `longhorn:${ns}/${name}`,
        name,
        namespace: ns,
        status: lv.status?.state || lv.status?.robustness || "Unknown",
        capacity: lv.spec?.size || "unknown",
        node: lv.status?.currentNodeID || "-",
        storageClass: "longhorn",
      });
    }
  }

  // ── StorageClass list ──
  const storageClasses = (scResult?.items || []).map((sc: any) => ({
    name: sc.metadata?.name || "unknown",
    provisioner: sc.provisioner || "unknown",
    isDefault:
      sc.metadata?.annotations?.[
        "storageclass.kubernetes.io/is-default-class"
      ] === "true",
  }));

  // ── Namespace list ──
  const now = Date.now();
  const namespaces = (nsResult?.items || []).map((ns: any) => {
    const created = ns.metadata?.creationTimestamp;
    const age = created ? formatAge(now - new Date(created).getTime()) : "-";
    return {
      name: ns.metadata?.name || "unknown",
      status: ns.status?.phase || "Active",
      age,
    };
  });

  // ── Service list ──
  const services = (svcResult?.items || []).map((svc: any) => {
    const ports = (svc.spec?.ports || []).map((p: any) => {
      const nodePort = p.nodePort ? `:${p.nodePort}` : "";
      return `${p.port}${nodePort}/${p.protocol || "TCP"}`;
    }).join(", ");
    const lbIngress = svc.status?.loadBalancer?.ingress;
    const externalIP =
      (lbIngress && lbIngress.length > 0)
        ? lbIngress.map((i: any) => i.ip || i.hostname).join(", ")
        : (svc.spec?.externalIPs || []).join(", ") || "-";
    return {
      name: svc.metadata?.name || "unknown",
      namespace: svc.metadata?.namespace || "default",
      type: svc.spec?.type || "ClusterIP",
      clusterIP: svc.spec?.clusterIP || "-",
      externalIP,
      ports,
      selector: svc.spec?.selector
        ? Object.entries(svc.spec.selector).map(([k, v]) => `${k}=${v}`).join(", ")
        : "-",
    };
  });

  // Deployment ownership uses controller UIDs, never name prefixes or label coincidence.
  const ownershipAvailable = ["pods", "replicasets"].every(resource => snapshots[resource as ClusterResource]?.value !== undefined);
  const deployments = (deployResult?.items || []).map((dep: any) => {
    const created = dep.metadata?.creationTimestamp || null;
    const ownedPods = deploymentPods(dep, allPods, snapshots.replicasets?.value?.items || []);
    return {
      name: dep.metadata?.name || "unknown", namespace: dep.metadata?.namespace || "default",
      ...deploymentState(dep), image: dep.spec?.template?.spec?.containers?.[0]?.image || "-",
      restarts: ownershipAvailable ? ownedPods.reduce((sum, pod) => sum + podRestarts(pod), 0) : null,
      ownershipAvailable, created, age: created ? formatAge(now - new Date(created).getTime()) : "-",
    };
  });

  // ── Ingress list ──
  const ingresses = (ingressResult?.items || []).map((ing: any) => {
    const created = ing.metadata?.creationTimestamp;
    const age = created ? formatAge(now - new Date(created).getTime()) : "-";
    const lbIngress = ing.status?.loadBalancer?.ingress;
    const state = lbIngress && lbIngress.length > 0 ? "Ready" : "Pending";
    // First rule's first backend
    const firstRule = ing.spec?.rules?.[0];
    const firstPath = firstRule?.http?.paths?.[0];
    const target = firstPath?.backend?.service?.name
      ? `${firstPath.backend.service.name}:${firstPath.backend.service.port?.number || firstPath.backend.service.port?.name || ""}`
      : firstRule?.host || "-";
    return {
      name: ing.metadata?.name || "unknown",
      namespace: ing.metadata?.namespace || "default",
      state,
      host: firstRule?.host || "-",
      target,
      age,
    };
  });

  return {
    availability,
    rawReplicaSets: snapshots.replicasets?.value?.items || [],
    info: {
      nodes: allNodes.length,
      readyNodes,
      pods: allPods.length,
      runningPods,
      version,
      longhornVolumes,
      healthyVolumes,
    },
    nodes: allNodes,
    pods: allPods,
    volumes,
    storageClasses,
    namespaces,
    services,
    deployments,
    ingresses,
    rawNamespaces: nsResult?.items || [],
    rawServices: svcResult?.items || [],
    rawDeployments: deployResult?.items || [],
    rawIngresses: ingressResult?.items || [],
    rawPvcs: pvcResult?.items || [],
    lastFetch: Date.now(),
  };
}

/**
 * Get cluster data from cache or fetch fresh from the remote node.
 * Guarantees only one in-flight fetch at a time.
 */
/** Read only requested resources, sharing each resource's cache and in-flight request. */
export async function getCachedClusterData(resources: readonly ClusterResource[] = CLUSTER_RESOURCES): Promise<CachedData> {
  return fetchAllClusterData(resources);
}
/** Resource-only snapshot: no overview counters or unrelated projections are constructed. */
export async function getCachedClusterResource(resource: ClusterResource) {
  return resourcesCache.readResource(resource);
}
export function invalidateCache(): void { resourcesCache.invalidate(); }
export function clusterDiagnostics() { return resourcesCache.diagnostics(); }
