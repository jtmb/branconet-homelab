import { NextResponse, NextRequest } from "next/server";
import prisma from "@/lib/db";

export async function GET() {
  const jobs = await prisma.job.findMany({
    orderBy: { startedAt: "desc" },
    take: 50,
  });

  return NextResponse.json(jobs);
}

export async function DELETE(req: NextRequest) {
  const jobId = req.nextUrl.searchParams.get("jobId");

  if (!jobId) {
    return NextResponse.json({ error: "jobId is required" }, { status: 400 });
  }

  await prisma.job.delete({ where: { id: jobId } });

  return NextResponse.json({ success: true });
}