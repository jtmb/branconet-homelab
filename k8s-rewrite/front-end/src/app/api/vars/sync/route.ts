import { NextResponse } from "next/server";
import { syncVarsToYAML, syncInventoryToFile } from "@/lib/sync-vars";

/**
 * POST /api/vars/sync
 * Sync all variables from the database to the Ansible group_vars/all.yml file.
 * Optionally also sync the inventory from the Node table.
 */
export async function POST() {
  try {
    const varsResult = await syncVarsToYAML();
    const invResult = await syncInventoryToFile();

    return NextResponse.json({
      success: true,
      vars: { synced: varsResult.synced, file: varsResult.file },
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
