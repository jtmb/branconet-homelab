import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { requireWrite } from "@/lib/permissions";

export async function GET() {
  const nodes = await prisma.node.findMany({ orderBy: { hostname: "asc" } });
  return NextResponse.json(nodes);
}

export async function POST(request: Request) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  const body = await request.json();
  const { name, hostname, ipAddress, role } = body;

  if (!hostname || !ipAddress) {
    return NextResponse.json({ error: "hostname and ipAddress required" }, { status: 400 });
  }

  // Upsert — update if hostname exists, create if not
  const node = await prisma.node.upsert({
    where: { hostname },
    update: { name: name || hostname, ipAddress, role: role || "worker" },
    create: { name: name || hostname, hostname, ipAddress, role: role || "worker", status: "pending" },
  });

  return NextResponse.json(node);
}
