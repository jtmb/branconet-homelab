import { NextRequest, NextResponse } from "next/server";
import { removeRepo } from "@/lib/flux";
import { requireWrite } from "@/lib/permissions";

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  try {
    const { id } = await params;
    const url = new URL(request.url);
    const name = url.searchParams.get("name") || undefined;
    const namespace = url.searchParams.get("namespace") || undefined;
    const result = await removeRepo(id, name, namespace);

    if (!result.success) {
      return NextResponse.json({ error: result.error }, { status: 400 });
    }

    return NextResponse.json({ success: true, deleteId: result.deleteId });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
