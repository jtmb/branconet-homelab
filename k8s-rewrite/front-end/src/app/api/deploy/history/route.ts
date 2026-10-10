import { NextResponse, NextRequest } from "next/server";
import prisma from "@/lib/db";
import { requireWrite } from "@/lib/permissions";
import { jobIdValid, readJobTail } from "@/lib/job-output";

export async function GET(request: NextRequest) {
  try {
    const jobId = request.nextUrl.searchParams.get("jobId");
    if (jobId !== null) {
      const rawTail = request.nextUrl.searchParams.get("tail") ?? "65536";
      const tail = Number(rawTail);
      if (!jobIdValid(jobId) || !/^\d{1,5}$/.test(rawTail) || !Number.isInteger(tail) || tail < 1 || tail > 65536)
        return NextResponse.json({ error: "Valid jobId and tail from 1 to 65536 are required" }, { status: 400 });
      const result = await readJobTail(jobId, tail);
      return result ? NextResponse.json(result, { headers: { "Cache-Control": "private, no-store" } })
        : NextResponse.json({ error: "Job not found" }, { status: 404 });
    }
    const jobs = await prisma.job.findMany({ orderBy: { startedAt: "desc" }, take: 50,
      select: { id: true, playbook: true, status: true, startedAt: true, finishedAt: true } });
    return NextResponse.json(jobs, { headers: { "Cache-Control": "private, no-store" } });
  } catch { return NextResponse.json({ error: "Job history unavailable" }, { status: 503 }); }
}
export async function DELETE(request: NextRequest) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;
  const jobId = request.nextUrl.searchParams.get("jobId");
  if (!jobIdValid(jobId)) return NextResponse.json({ error: "Valid jobId is required" }, { status: 400 });
  try {
    const removed = await prisma.job.deleteMany({ where: { id: jobId, status: { not: "running" } } });
    if (!removed.count) {
      const exists = await prisma.job.findUnique({ where: { id: jobId }, select: { id: true } });
      return NextResponse.json({ error: exists ? "Running jobs cannot be deleted" : "Job not found" }, { status: exists ? 409 : 404 });
    }
    return NextResponse.json({ success: true });
  } catch { return NextResponse.json({ error: "Job deletion unavailable" }, { status: 503 }); }
}
