import { NextResponse } from "next/server";
import prisma from "@/lib/db";

export async function GET() {
  const jobs = await prisma.job.findMany({
    orderBy: { startedAt: "desc" },
    take: 50,
  });

  return NextResponse.json(jobs);
}