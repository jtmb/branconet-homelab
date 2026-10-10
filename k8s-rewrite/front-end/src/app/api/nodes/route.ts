import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { requireOperator } from "@/lib/permissions";
import { nodeInput } from "@/lib/node-input";

export async function GET() {
  const nodes = await prisma.node.findMany({ orderBy: { hostname: "asc" } });
  return NextResponse.json(nodes);
}

export async function POST(request: Request) {
  const auth = await requireOperator();
  if (auth instanceof NextResponse) return auth;

  const parsed = nodeInput.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message || "Invalid node" }, { status: 400 });
  const { name, hostname, ipAddress, role } = parsed.data;
  try {
    const node = await prisma.node.upsert({
    where: { hostname },
    update: { name: name || hostname, ipAddress, role: role || "worker" },
    create: { name: name || hostname, hostname, ipAddress, role: role || "worker", status: "pending" },
  });

    return NextResponse.json(node);
  } catch {
    return NextResponse.json({ error: "Node inventory update unavailable" }, { status: 503 });
  }
}
