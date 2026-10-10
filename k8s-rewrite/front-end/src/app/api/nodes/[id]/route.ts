import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { requireWrite } from "@/lib/permissions";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  const { id } = await params;
  await prisma.node.delete({ where: { id } });
  return NextResponse.json({ success: true });
}
