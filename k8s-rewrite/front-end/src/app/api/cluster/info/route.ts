import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { getCachedClusterData } from "@/lib/cluster-cache";

const ZERO_INFO = {
  nodes: 0,
  readyNodes: 0,
  pods: 0,
  runningPods: 0,
  version: "",
  longhornVolumes: 0,
  healthyVolumes: 0,
};

export async function GET() {
  // Check DB for stale cluster records (even if live cluster is dead)
  const [state, nodeCount, fluxRepos] = await Promise.all([
    prisma.clusterState.findFirst({ where: { deployed: true } }),
    prisma.node.count(),
    prisma.gitRepo.count(),
  ]);
  const hasDbCluster = !!state || nodeCount > 0;

  const data = await getCachedClusterData();
  if (!data) {
    return NextResponse.json({ ...ZERO_INFO, hasDbCluster, fluxRepos });
  }
  return NextResponse.json({ ...data.info, hasDbCluster, fluxRepos });
}