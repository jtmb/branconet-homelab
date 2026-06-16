import { NextRequest, NextResponse } from "next/server";
import { removeRepo } from "@/lib/flux";

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const result = await removeRepo(id);

    if (!result.success) {
      return NextResponse.json({ error: result.error }, { status: 400 });
    }

    return NextResponse.json({ success: true, deleteId: result.deleteId });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
