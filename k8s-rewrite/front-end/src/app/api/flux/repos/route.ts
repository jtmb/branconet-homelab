import { NextRequest, NextResponse } from "next/server";
import { listRepos, addRepo } from "@/lib/flux";
import { requireWrite } from "@/lib/permissions";

export async function GET() {
  try {
    const repos = await listRepos();
    return NextResponse.json({ repos });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  try {
    const body = await request.json();
    const { name, url, branch, path, authMethod, authData } = body;

    if (!name || !url) {
      return NextResponse.json({ error: "name and url are required" }, { status: 400 });
    }

    const result = await addRepo({
      name,
      url,
      branch: branch || "main",
      path: path || "./",
      authMethod: authMethod || "none",
      authData: authData || undefined,
    });

    if (!result.success) {
      return NextResponse.json({ error: result.error }, { status: 400 });
    }

    return NextResponse.json({ success: true, repo: result.repo }, { status: 201 });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
