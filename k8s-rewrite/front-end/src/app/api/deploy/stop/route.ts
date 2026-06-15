import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { activeJobs } from "@/lib/active-jobs";

export async function POST(request: NextRequest) {
  try {
    // Support both query param (?jobId=xxx) and JSON body ({jobId: "xxx"})
    let jobId = request.nextUrl.searchParams.get("jobId");
    if (!jobId) {
      try {
        const body = await request.json();
        jobId = body.jobId;
      } catch {
        // No JSON body either
      }
    }

    if (!jobId) {
      return NextResponse.json(
        { error: "Missing jobId parameter" },
        { status: 400 }
      );
    }

    // Find and abort the running process
    const controller = activeJobs.get(jobId);
    if (controller) {
      controller.abort();
      activeJobs.delete(jobId);
    }

    // Update job status in database
    const job = await prisma.job.findUnique({ where: { id: jobId } });
    if (job && job.status === "running") {
      await prisma.job.update({
        where: { id: jobId },
        data: {
          status: "failed",
          output: job.output + "\n\n[ Deployment stopped by user ]\n",
          finishedAt: new Date(),
        },
      });
    }

    return NextResponse.json({ success: true, jobId });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
