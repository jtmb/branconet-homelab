import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  await prisma.variable.delete({ where: { id } }).catch(() => {
    // Variable may not exist — ignore
  });
  return NextResponse.json({ success: true });
}
