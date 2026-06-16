import { NextResponse } from "next/server";
import { getCachedClusterData } from "@/lib/cluster-cache";

export async function GET() {
  const data = await getCachedClusterData();
  if (!data) {
    return NextResponse.json({ deployments: [] });
  }
  return NextResponse.json({ deployments: data.deployments });
}
