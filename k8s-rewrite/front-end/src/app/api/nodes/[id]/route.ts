import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { requireOperator } from "@/lib/permissions";
import { nodeInput } from "@/lib/node-input";
import { Prisma } from "@prisma/client";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const auth = await requireOperator();
  if (auth instanceof NextResponse) return auth;

  const { id } = await params;
  try {
    await prisma.node.delete({ where: { id } });
    return NextResponse.json({ success: true });
  } catch (error) {
    return inventoryFailure(error);
  }
}

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireOperator();
  if (auth instanceof NextResponse) return auth;
  const { id } = await params;
  const parsed = nodeInput.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message || "Invalid node" }, { status: 400 });
  try {
    return NextResponse.json(await prisma.node.update({ where: { id }, data: parsed.data }));
  } catch (error) {
    return inventoryFailure(error);
  }
}
function inventoryFailure(error: unknown) {
  if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === "P2025") return NextResponse.json({ error: "Node inventory record not found" }, { status: 404 });
  if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === "P2002") return NextResponse.json({ error: "Hostname already registered" }, { status: 409 });
  return NextResponse.json({ error: "Node inventory update unavailable" }, { status: 503 });
}
