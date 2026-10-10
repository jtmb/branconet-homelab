import { NextRequest } from "next/server";
import prisma from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const jobId = request.nextUrl.searchParams.get("jobId");

  if (!jobId) {
    return new Response(
      JSON.stringify({ error: "Missing jobId parameter" }),
      {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }
    );
  }

  // Verify job exists
  const job = await prisma.job.findUnique({ where: { id: jobId } });
  if (!job) {
    return new Response(
      JSON.stringify({ error: "Job not found" }),
      {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }
    );
  }

  // Create an SSE stream
  const encoder = new TextEncoder();
  let lastOutputLength = 0;

  const stream = new ReadableStream({
    start(controller) {
      let closed = false;
      let interval: ReturnType<typeof setInterval> | null = null;

      const cleanup = () => {
        closed = true;
        if (interval) clearInterval(interval);
        try {
          controller.close();
        } catch {
          // Already closed
        }
      };

      // Check current state and enqueue any new output
      const sendState = async () => {
        if (closed) return;
        try {
          const current = await prisma.job.findUnique({
            where: { id: jobId },
          });
          if (!current || closed) return;

          // Only send new output since last read
          const newOutput = current.output.slice(lastOutputLength);
          if (newOutput) {
            lastOutputLength = current.output.length;
            const event = JSON.stringify({
              output: newOutput,
              status: current.status,
            });
            controller.enqueue(encoder.encode(`data: ${event}\n\n`));
          }

          // If job is done, close the stream
          if (current.status === "success" || current.status === "failed") {
            closed = true;
            if (interval) clearInterval(interval);
            controller.enqueue(
              encoder.encode(
                `data: ${JSON.stringify({ done: true, status: current.status })}\n\n`
              )
            );
            try {
              controller.close();
            } catch {
              /* already closed */
            }
          }
        } catch {
          // Poll error — retry on next interval
        }
      };

      // Handle client disconnect
      request.signal.addEventListener("abort", cleanup, { once: true });

      // Return promise so stream isn't readable until first data check completes
      return sendState().then(() => {
        interval = setInterval(sendState, 500);
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}