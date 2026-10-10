import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { runAnsiblePlaybook } from "@/lib/ansible";
import { activeJobs } from "@/lib/active-jobs";
import { syncVarsToYAML, syncInventoryToFile, syncNodesFromVars } from "@/lib/sync-vars";
import { invalidateCache } from "@/lib/cluster-cache";
import { requireWrite } from "@/lib/permissions";

export async function POST(request: NextRequest) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  if (process.env.BORTUS_DISABLE_PROVISIONING === "true" || process.env.KUBERNETES_SERVICE_HOST) return NextResponse.json({ error: "Run bootstrap/provisioning from the independent operator environment" }, { status: 501 });

  try {
    const body = await request.json();
    const { playbook, roles } = body;
    const playbookFile = playbook || "site.yml";

    // Fail before launching on invalid lookup references; never use old generated files.
    await syncVarsToYAML();
    await syncNodesFromVars();
    await syncInventoryToFile();

    // Create job record in SQLite via Prisma
    const job = await prisma.job.create({
      data: {
        playbook: playbookFile,
        status: "running",
        output: `[Generated lookup references and inventory]\n`,
        startedAt: new Date(),
      },
    });

    // Create AbortController for cancellation
    const controller = new AbortController();
    activeJobs.set(job.id, controller);

    // Start Ansible asynchronously (don't await)
    runAnsible(job.id, playbookFile, roles || [], controller.signal);

    return NextResponse.json({ success: true, jobId: job.id });
  } catch (err) {
    return NextResponse.json({ error: "Provisioning preparation failed" }, { status: 500 });
  }
}

export async function GET() {
  // Return list of active job IDs (for health check / status polling)
  return NextResponse.json({
    activeJobIds: Array.from(activeJobs.keys()),
  });
}

async function runAnsible(
  jobId: string,
  playbookFile: string,
  roles: string[],
  signal: AbortSignal
) {
  const emitter = await runAnsiblePlaybook(playbookFile, roles, signal);

  let outputBuffer = "";
  let flushTimer: ReturnType<typeof setTimeout> | null = null;
  let finalizing = false;

  // Throttled DB flush: accumulate output, write every 500ms
  function scheduleFlush() {
    if (flushTimer || finalizing) return;
    flushTimer = setTimeout(async () => {
      flushTimer = null;
      if (finalizing) return;
      if (outputBuffer) {
        const text = outputBuffer;
        outputBuffer = "";
        try {
          const current = await prisma.job.findUnique({ where: { id: jobId } });
          if (current) {
            await prisma.job.update({
              where: { id: jobId },
              data: { output: current.output + text },
            });
          }
        } catch {
          // DB write failed — silently retry next flush
        }
      }
    }, 500);
  }

  emitter.on("data", (text: string) => {
    outputBuffer += text;
    scheduleFlush();
  });

  emitter.on("close", async ({ exitCode, fullOutput }: { exitCode: number | null; fullOutput: string }) => {
    finalizing = true;
    if (flushTimer) clearTimeout(flushTimer);

    const isSuccess = exitCode === 0;

    try {
      await prisma.job.update({
        where: { id: jobId },
        data: {
          output: fullOutput,
          status: isSuccess ? "success" : "failed",
          finishedAt: new Date(),
        },
      });

      // ── On success: capture kubeconfig + mark cluster deployed ──
      if (isSuccess) {
        invalidateCache();

        await prisma.clusterState.upsert({
          where: { id: "singleton" },
          update: { deployed: true, deployedAt: new Date(), kubeconfig: "" },
          create: { id: "singleton", deployed: true, deployedAt: new Date() },
        });
        // Operator stores kubeconfig independently; never persist credentials in SQLite.

      }
    } catch (err) {
      console.error("Failed to save final job state:", err);
    }

    activeJobs.delete(jobId);
  });

  emitter.on("error", async (err: Error) => {
    finalizing = true;
    if (flushTimer) clearTimeout(flushTimer);

    try {
      const current = await prisma.job.findUnique({ where: { id: jobId } });
      if (current) {
        await prisma.job.update({
          where: { id: jobId },
          data: {
            output: current.output + `\nERROR: ${err.message}\n`,
            status: "failed",
            finishedAt: new Date(),
          },
        });
      }
    } catch {
      // Best-effort
    }

    activeJobs.delete(jobId);
  });
}