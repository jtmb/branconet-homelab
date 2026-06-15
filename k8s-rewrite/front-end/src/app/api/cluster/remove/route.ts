import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { invalidateCache } from "@/lib/cluster-cache";

export async function DELETE() {
  try {
    // Clean all cluster-related tables in a transaction
    await prisma.$transaction([
      prisma.volume.deleteMany(),
      prisma.persistentVolumeClaim.deleteMany(),
      prisma.service.deleteMany(),
      prisma.pod.deleteMany(),
      prisma.deployment.deleteMany(),
      prisma.node.deleteMany(),
      prisma.clusterState.deleteMany(),
    ]);

    // Invalidate the in-memory cluster data cache so next poll gets zeros
    invalidateCache();

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("Failed to remove cluster from DB:", err);
    return NextResponse.json(
      { success: false, error: "Failed to remove cluster" },
      { status: 500 }
    );
  }
}
