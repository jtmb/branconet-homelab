import prisma from "./db";
import { kubectlJSON } from "./k8s";

// =============================================================================
// In-memory cluster data cache with 10s TTL.
// All 4 cluster API routes read from this cache so the front-end's
// 10s polling interval doesn't hammer the VM with SSH connections.
// =============================================================================

interface VolumeInfo {
  name: string;
  namespace: string;
  status: string;
  capacity: string;
  node: string;
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
  lastFetch: number;
}

let cache: CachedData | null = null;
const TTL_MS = 10_000; // 10 seconds

// Fetch in-progress guard — prevents concurrent SSH storms
let fetchPromise: Promise<CachedData | null> | null = null;

/**
 * Resolve the master node's IP from the database.
 */
async function getMasterHost(): Promise<string | null> {
  const master = await prisma.node.findFirst({
    where: { role: "master" },
  });
  return master?.ipAddress || null;
}

/**
 * Fetch all cluster data from the remote node via SSH+kubectl.
 * Runs 4 kubectl queries in parallel, then builds derived info.
 */
async function fetchAllClusterData(host: string): Promise<CachedData | null> {
  const [nodesResult, podsResult, pvResult, pvcResult, longhornResult] =
    await Promise.all([
      kubectlJSON(host, "get nodes"),
      kubectlJSON(host, "get pods -A"),
      kubectlJSON(host, "get pv"),
      kubectlJSON(host, "get pvc -A"),
      kubectlJSON(host, "get volumes.longhorn.io -A", 8000).catch(() => null),
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
      volumes.push({
        name: pv.metadata?.name || "unknown",
        namespace: pv.spec?.claimRef?.namespace || "-",
        status: pv.status?.phase || "Unknown",
        capacity: pv.spec?.capacity?.storage || "unknown",
        node: pv.metadata?.labels?.["kubernetes.io/hostname"] || "-",
      });
    }
  }

  if (longhornResult?.items) {
    for (const lv of longhornResult.items) {
      volumes.push({
        name: lv.metadata?.name || "unknown",
        namespace: lv.metadata?.namespace || "-",
        status: lv.status?.state || lv.status?.robustness || "Unknown",
        capacity: lv.spec?.size || "unknown",
        node: lv.status?.currentNodeID || "-",
      });
    }
  }

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

  const host = await getMasterHost();
  if (!host) {
    cache = null;
    return null;
  }

  // Start a new fetch; other callers will wait on this promise
  fetchPromise = fetchAllClusterData(host).finally(() => {
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
