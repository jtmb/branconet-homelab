import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { activeJobs } from "@/lib/active-jobs";
import { requireOperator } from "@/lib/permissions";
import { jobIdValid } from "@/lib/job-output";

export async function POST(request: NextRequest) {
  const auth = await requireOperator();
  if (auth instanceof NextResponse) return auth;
  try {
    const jobId = request.nextUrl.searchParams.get("jobId") ?? (await request.json().catch(() => ({}))).jobId;
    if (!jobIdValid(jobId)) return NextResponse.json({ error: "Valid jobId is required" }, { status: 400 });
    const job = await prisma.job.findUnique({ where: { id: jobId }, select: { id: true, status: true } });
    if (!job) return NextResponse.json({ error: "Job not found" }, { status: 404 });
    if (job.status !== "running") return NextResponse.json({ error: "Job is already complete" }, { status: 409 });
    const controller = activeJobs.get(jobId);
    if (!controller) return NextResponse.json({ error: "Job is not running in this process; inspect the operator runner" }, { status: 409 });
    controller.abort();
    return NextResponse.json({ success: true, jobId, stopping: true }, { status: 202 });
  } catch { return NextResponse.json({ error: "Job cancellation unavailable" }, { status: 503 }); }
}
