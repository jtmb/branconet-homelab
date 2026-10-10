import { NextRequest, NextResponse } from "next/server";
import { getDeleteProgress } from "@/lib/flux";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const progress = getDeleteProgress(id);

    if (!progress) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    return NextResponse.json(progress);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
