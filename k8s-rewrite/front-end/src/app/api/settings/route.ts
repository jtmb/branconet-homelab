import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { requireWrite } from "@/lib/permissions";

/**
 * GET /api/settings — return all app settings as key-value pairs
 * PATCH /api/settings — update a single setting by key
 */
export async function GET() {
  const settings = await prisma.appSetting.findMany();
  const map: Record<string, string> = {};
  for (const s of settings) {
    map[s.key] = s.value;
  }
  return NextResponse.json(map);
}

export async function PATCH(request: NextRequest) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  try {
    const { key, value } = await request.json();

    if (!key || value === undefined) {
      return NextResponse.json(
        { error: "Both 'key' and 'value' are required" },
        { status: 400 }
      );
    }

    const setting = await prisma.appSetting.upsert({
      where: { key },
      update: { value: String(value) },
      create: { key, value: String(value) },
    });

    return NextResponse.json({ success: true, key: setting.key, value: setting.value });
  } catch (err) {
    console.error("[settings] PATCH error:", err);
    return NextResponse.json({ error: "Failed to update setting" }, { status: 500 });
  }
}
