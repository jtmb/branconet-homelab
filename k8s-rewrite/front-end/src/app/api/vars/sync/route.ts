import { NextResponse } from "next/server";
import { syncVarsToYAML, syncInventoryToFile, syncNodesFromVars } from "@/lib/sync-vars";
import { requireWrite } from "@/lib/permissions";

/**
 * POST /api/vars/sync
 * Sync all variables from the database to the Ansible group_vars/all.yml file.
 * Also syncs node variables to the Node table and rebuilds the inventory.
 */
export async function POST() {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  try {
    const varsResult = await syncVarsToYAML();
    const nodesResult = await syncNodesFromVars();
    const invResult = await syncInventoryToFile();

    return NextResponse.json({
      success: true,
      vars: { synced: varsResult.synced, file: varsResult.file },
      nodes: { synced: nodesResult.synced },
      inventory: { synced: invResult.synced, file: invResult.file },
    });
  } catch (err) {
    return NextResponse.json(
      { error: "Failed to sync vars", details: String(err) },
      { status: 500 }
    );
  }
}

/**
 * GET /api/vars/sync
 * Returns information about the last sync (read-only, does NOT trigger sync).
 */
export async function GET() {
  return NextResponse.json({
    message: "Use POST to trigger a sync from DB to group_vars/all.yml",
  });
}
