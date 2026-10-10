import prisma from "./db";
import { kubectlJSON } from "./k8s";

// =============================================================================
// In-memory cluster data cache with 10s TTL.
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

interface CachedData {
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

let cache: CachedData | null = null;
const TTL_MS = 10_000; // 10 seconds

// Fetch in-progress guard — prevents concurrent fetch storms
let fetchPromise: Promise<CachedData | null> | null = null;

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
 * Runs 10 kubectl queries in parallel, then builds derived info.
 */
async function fetchAllClusterData(): Promise<CachedData | null> {
  const [nodesResult, podsResult, pvResult, pvcResult, longhornResult, scResult, nsResult, svcResult, deployResult, ingressResult] =
    await Promise.all([
      kubectlJSON("get nodes"),
      kubectlJSON("get pods -A"),
      kubectlJSON("get pv"),
      kubectlJSON("get pvc -A"),
      kubectlJSON("get volumes.longhorn.io -A", 8000).catch(() => null),
      kubectlJSON("get sc", 5000).catch(() => null),
      kubectlJSON("get namespaces", 5000).catch(() => null),
      kubectlJSON("get services -A", 5000).catch(() => null),
      kubectlJSON("get deployments -A", 5000).catch(() => null),
      kubectlJSON("get ingress -A", 5000).catch(() => null),
    ]);

  // If even nodes query fails, cluster is unreachable
  if (!nodesResult) return null;

  const allNodes = nodesResult.items || [];
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
        v.status?.state === "attached" || v.status?.robustness === "healthy"
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

  // ── Deployment list ──
  // Pre-compute pod restarts per deployment via pod name prefix matching.
  // Kubernetes names pods as <deployment>-<rs-hash>-<pod-hash>.
  const podRestartsByDeploy = new Map<string, number>();
  for (const pod of allPods) {
    const podName: string = pod.metadata?.name || "";
    const podNs: string = pod.metadata?.namespace || "";
    // Find the deployment whose name is a prefix of the pod name
    const deployItems = deployResult?.items || [];
    for (const dep of deployItems) {
      const depName: string = dep.metadata?.name || "";
      const depNs: string = dep.metadata?.namespace || "default";
      if (podNs === depNs && podName.startsWith(depName + "-")) {
        const restarts = (pod.status?.containerStatuses || []).reduce(
          (sum: number, c: any) => sum + (c.restartCount || 0), 0
        );
        const key = `${depNs}/${depName}`;
        podRestartsByDeploy.set(key, (podRestartsByDeploy.get(key) || 0) + restarts);
        break;
      }
    }
  }

  const deployments = (deployResult?.items || []).map((dep: any) => {
    const created = dep.metadata?.creationTimestamp;
    const age = created ? formatAge(now - new Date(created).getTime()) : "-";
    const ready = dep.status?.readyReplicas ?? 0;
    const desired = dep.status?.replicas ?? 0;
    const available = dep.status?.availableReplicas ?? 0;
    const updated = dep.status?.updatedReplicas ?? 0;
    const depName = dep.metadata?.name || "unknown";
    const depNs = dep.metadata?.namespace || "default";

    // Determine state
    let state = "Progressing";
    if (ready === desired && updated === desired && desired > 0) {
      state = "Ready";
    } else if (updated < desired) {
      state = "Updating";
    }

    // Determine health from conditions
    const conditions = dep.status?.conditions || [];
    const availableCond = conditions.find((c: any) => c.type === "Available");
    let health = "Unknown";
    if (availableCond?.status === "True") {
      health = "Healthy";
    } else if (conditions.some((c: any) => c.type === "ReplicaFailure" && c.status === "True")) {
      health = "Degraded";
    } else if (availableCond?.status === "False") {
      health = "Unhealthy";
    }

    // Primary container image
    const firstContainer = dep.spec?.template?.spec?.containers?.[0];
    const image = firstContainer?.image || "-";

    // Sum pod restarts
    const restarts = podRestartsByDeploy.get(`${depNs}/${depName}`) ?? 0;

    return {
      name: depName,
      namespace: depNs,
      state,
      image,
      ready: `${ready}/${desired}`,
      upToDate: updated,
      available,
      restarts,
      age,
      health,
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
export async function getCachedClusterData(): Promise<CachedData | null> {
  const now = Date.now();

  // Return fresh cache
  if (cache && now - cache.lastFetch < TTL_MS) {
    return cache;
  }

  // If a fetch is already in progress, wait for it
  if (fetchPromise) {
    return fetchPromise;
  }

  // Start a new fetch; other callers will wait on this promise
  fetchPromise = fetchAllClusterData().finally(() => {
    fetchPromise = null;
  });

  const result = await fetchPromise;
  if (result) cache = result;
  else cache = null; // fetch failed, clear stale cache

  return cache;
}

/**
 * Invalidate the cache — call after deployments or manual cluster changes.
 */
export function invalidateCache(): void {
  cache = null;
}
