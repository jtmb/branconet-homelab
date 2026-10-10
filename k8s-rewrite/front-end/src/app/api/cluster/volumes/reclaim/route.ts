import { NextRequest, NextResponse } from "next/server";
import { kubectlExec } from "@/lib/k8s";
import { requireWrite } from "@/lib/permissions";

interface PVInfo {
  name: string;
  reclaimPolicy: string;
  status: string;
  storageClass: string;
  capacity: string;
  claimRef: string;
  age: string;
}

/**
 * GET /api/cluster/volumes/reclaim
 * List all PVs with their reclaim policies
 */
export async function GET() {
  try {
    const output = await kubectlExec(
      "get pv -o custom-columns=NAME:.metadata.name,RECLAIM:.spec.persistentVolumeReclaimPolicy,STATUS:.status.phase,STORAGECLASS:.spec.storageClassName,CAPACITY:.spec.capacity.storage,CLAIM:.spec.claimRef.name,AGE:.metadata.creationTimestamp --no-headers",
      8000,
    );

    if (!output || !output.trim()) {
      return NextResponse.json({ volumes: [] });
    }

    const volumes: PVInfo[] = output
      .trim()
      .split("\n")
      .map((line) => {
        const parts = line.trim().split(/\s+/);
        return {
          name: parts[0] || "",
          reclaimPolicy: parts[1] || "Retain",
          status: parts[2] || "Unknown",
          storageClass: parts[3] || "none",
          capacity: parts[4] || "",
          claimRef: parts[5] || "",
          age: parts.slice(6).join(" ") || "",
        };
      })
      .filter((v) => v.name);

    return NextResponse.json({ volumes });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

/**
 * PATCH /api/cluster/volumes/reclaim
 * Change reclaim policy of one or more PVs
 * Body: { volumes: [{ name: string, policy: "Retain" | "Delete" | "Recycle" }] }
 */
export async function PATCH(request: NextRequest) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  try {
    const body = await request.json();
    const volumes: { name: string; policy: string }[] = body.volumes;

    if (!volumes || !Array.isArray(volumes) || volumes.length === 0) {
      return NextResponse.json({ error: "No volumes specified" }, { status: 400 });
    }

    const validPolicies = ["Retain", "Delete", "Recycle"];
    const results: { name: string; success: boolean; error?: string }[] = [];

    for (const vol of volumes) {
      if (!validPolicies.includes(vol.policy)) {
        results.push({ name: vol.name, success: false, error: `Invalid policy: ${vol.policy}` });
        continue;
      }

      try {
        await kubectlExec(
          `patch pv ${vol.name} -p '{"spec":{"persistentVolumeReclaimPolicy":"${vol.policy}"}}'`,
          8000,
        );
        results.push({ name: vol.name, success: true });
      } catch (err) {
        results.push({ name: vol.name, success: false, error: String(err) });
      }
    }

    const allOk = results.every((r) => r.success);
    return NextResponse.json({ results, success: allOk }, { status: allOk ? 200 : 207 });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
