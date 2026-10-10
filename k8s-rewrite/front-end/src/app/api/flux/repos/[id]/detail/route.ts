import { NextRequest, NextResponse } from "next/server";
import { getGitRepoDetail } from "@/lib/flux";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params;
    const detail = await getGitRepoDetail(decodeURIComponent(id));

    if (!detail) {
      return NextResponse.json({ error: "Repository not found" }, { status: 404 });
    }

    return NextResponse.json(detail);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
