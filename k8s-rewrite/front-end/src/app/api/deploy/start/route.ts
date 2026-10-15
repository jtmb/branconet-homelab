import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { runAnsiblePlaybook } from "@/lib/ansible";
import { activeJobs } from "@/lib/active-jobs";
import { syncVarsToYAML, syncInventoryToFile, syncNodesFromVars } from "@/lib/sync-vars";
import { invalidateCache } from "@/lib/cluster-cache";
import { requireOperator } from "@/lib/permissions";
import { runtimeCapabilities } from "@/lib/runtime-capabilities";
import { ansibleSelection, AnsibleSelectionError } from "@/lib/ansible-selection";

export async function POST(request: NextRequest) {
  const auth = await requireOperator();
  if (auth instanceof NextResponse) return auth;

  if (!runtimeCapabilities().provisioning) return NextResponse.json({ error: "Run bootstrap/provisioning from the independent operator environment" }, { status: 501 });

  try {
    const body = await request.json();
    const selected = ansibleSelection(body?.playbook ?? "site.yml", body?.roles ?? []);
    const playbookFile = selected.playbook;

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
    void runAnsible(job.id, playbookFile, selected.roles, controller.signal);

    return NextResponse.json({ success: true, jobId: job.id });
  } catch (err) {
    if (err instanceof AnsibleSelectionError) return NextResponse.json({ error: err.message }, { status: 400 });
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
  let emitter: Awaited<ReturnType<typeof runAnsiblePlaybook>>;
  try { emitter = await runAnsiblePlaybook(playbookFile, roles, signal); }
  catch {
    try { await prisma.job.update({ where: { id: jobId }, data: { output: "[Provisioning runner could not start]\n", status: "failed", finishedAt: new Date() } }); }
    catch { console.error("Failed to save final provisioning state"); }
    finally { activeJobs.delete(jobId); }
    return;
  }

  let outputBuffer = "";
  let flushTimer: ReturnType<typeof setTimeout> | null = null;
  let finalizing = false;
  let flushing = Promise.resolve();

  // Throttled DB flush: accumulate output, write every 500ms
  function scheduleFlush() {
    if (flushTimer || finalizing) return;
    flushTimer = setTimeout(() => {
      flushTimer = null;
      if (finalizing) return;
      if (outputBuffer) {
        const text = outputBuffer;
        outputBuffer = "";
        flushing = flushing.then(async () => {
          // Fixed progress only. Terminal persistence waits for any in-flight append.
          try { await prisma.$executeRaw`UPDATE "Job" SET "output" = "output" || ${text} WHERE "id" = ${jobId} AND "status" = 'running'`; }
          catch { /* Final full progress snapshot remains authoritative. */ }
        });
      }
    }, 500);
  }

  emitter.on("data", (text: string) => {
    outputBuffer += text;
    scheduleFlush();
  });

  emitter.on("close", async ({ exitCode, fullOutput }: { exitCode: number | null; fullOutput: string }) => {
    if (finalizing) return;
    finalizing = true;
    if (flushTimer) clearTimeout(flushTimer);
    await flushing;

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
      console.error("Failed to save final provisioning state");
    }

    activeJobs.delete(jobId);
  });

  emitter.on("error", async () => {
    if (finalizing) return;
    finalizing = true;
    if (flushTimer) clearTimeout(flushTimer);
    await flushing;

    try {
      const current = await prisma.job.findUnique({ where: { id: jobId } });
      if (current) {
        await prisma.job.update({
          where: { id: jobId },
          data: {
            output: current.output + "\n[Provisioning runner failed]\n",
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
