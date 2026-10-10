import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { getSessionFromHeaders } from "@/lib/auth";
import { createJobStream } from "@/lib/job-stream";
import { jobIdValid, readJobSlice } from "@/lib/job-output";

export const dynamic = "force-dynamic";
export async function GET(request: NextRequest) {
  const jobId = request.nextUrl.searchParams.get("jobId");
  const rawCursor = request.headers.get("last-event-id") ?? request.nextUrl.searchParams.get("cursor") ?? "0";
  if (!jobIdValid(jobId) || !/^\d{1,15}$/.test(rawCursor) || !Number.isSafeInteger(Number(rawCursor)))
    return NextResponse.json({ error: "Valid jobId and nonnegative cursor are required" }, { status: 400 });
  try {
    const cookie = request.headers.get("cookie");
    if (!await getSessionFromHeaders(cookie)) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    const job = await prisma.job.findUnique({ where: { id: jobId }, select: { id: true } });
    if (!job) return NextResponse.json({ error: "Job not found" }, { status: 404 });
    return new Response(createJobStream({ signal: request.signal, cursor: Number(rawCursor),
      authorize: async () => !!await getSessionFromHeaders(cookie), load: cursor => readJobSlice(jobId, cursor) }), {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "private, no-store", "X-Accel-Buffering": "no" },
    });
  } catch { return NextResponse.json({ error: "Job stream unavailable" }, { status: 503 }); }
}
