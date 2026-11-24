import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { activeJobs } from "@/lib/active-jobs";
import { requireOperator } from "@/lib/permissions";
import { jobIdValid } from "@/lib/job-output";
import { reconcileProvisioningJobs } from "@/lib/job-reconcile";
import { acquireProvisioningLock } from "@/lib/provisioning-lock";
import { runtimeCapabilities } from "@/lib/runtime-capabilities";

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
    if (!controller) {
      if (!runtimeCapabilities().provisioning)
        return NextResponse.json({ error: "Provisioning is disabled in this runtime" }, { status: 409 });
      const lock = await acquireProvisioningLock();
      if (lock.state === "held") {
        try {
          if ((await reconcileProvisioningJobs(prisma, lock.lease, jobId)).interrupted)
            return NextResponse.json({ success: true, jobId, interrupted: true,
              note: "The local runner exited without recording a result. Its history is kept; inspect partial effects." });
        } finally { await lock.lease.release(); }
      }
      return NextResponse.json({ error: "This job cannot be cancelled here; inspect the operator runner before retrying" }, { status: 409 });
    }
    controller.abort();
    return NextResponse.json({ success: true, jobId, stopping: true }, { status: 202 });
  } catch { return NextResponse.json({ error: "Job cancellation unavailable" }, { status: 503 }); }
}
