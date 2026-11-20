import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { runAnsiblePlaybook } from "@/lib/ansible";
import { activeJobs } from "@/lib/active-jobs";
import { syncVarsToYAML, syncInventoryToFile, syncNodesFromVars } from "@/lib/sync-vars";
import { invalidateCache } from "@/lib/cluster-cache";
import { requireOperator } from "@/lib/permissions";
import { runtimeCapabilities } from "@/lib/runtime-capabilities";
import { ansibleSelection, AnsibleSelectionError } from "@/lib/ansible-selection";
import { acquireProvisioningLock, type ProvisioningLease } from "@/lib/provisioning-lock";
import { claimProvisioningJob, reconcileProvisioningJobs } from "@/lib/job-reconcile";

const PREPARATION_OUTPUT = "[Generated lookup references and inventory]\n";

export async function POST(request: NextRequest) {
  const auth = await requireOperator();
  if (auth instanceof NextResponse) return auth;

  if (!runtimeCapabilities().provisioning) return NextResponse.json({ error: "Run bootstrap/provisioning from the independent operator environment" }, { status: 501 });

  let lease: ProvisioningLease | undefined;
  try {
    const body = await request.json();
    const selected = ansibleSelection(body?.playbook ?? "site.yml", body?.roles ?? []);
    const playbookFile = selected.playbook;

    const lock = await acquireProvisioningLock();
    if (lock.state !== "held") return NextResponse.json({ error: lock.state === "busy"
      ? "A provisioning run is still active" : "Cannot verify the provisioning lock; inspect the operator environment" }, { status: 409 });
    lease = lock.lease;
    if ((await reconcileProvisioningJobs(prisma, lease)).unknown)
      return NextResponse.json({ error: "A previous provisioning run has an unknown state; inspect the operator runner before retrying" }, { status: 409 });

    // Also refuse overlapping claims if two processes have different lock
    // directories configured for the same SQLite database.
    const id = await claimProvisioningJob(prisma, lease, playbookFile);
    if (!id) return NextResponse.json({ error: "A provisioning run is still active or unverified" }, { status: 409 });

    // Create AbortController for cancellation
    const controller = new AbortController();
    activeJobs.set(id, controller);
    try {
      // Fail before launching on invalid lookup references; never use old generated files.
      await syncVarsToYAML();
      await syncNodesFromVars();
      await syncInventoryToFile();
      await prisma.job.update({ where: { id }, data: { output: PREPARATION_OUTPUT } });
    } catch (error) {
      activeJobs.delete(id);
      await prisma.job.update({ where: { id }, data: { status: "failed", finishedAt: new Date(),
        output: "[Provisioning preparation failed; runner not started]\n" } });
      throw error;
    }

    // Start Ansible asynchronously (don't await)
    void runAnsible(id, playbookFile, selected.roles, lease, controller.signal);
    lease = undefined; // The runner lifecycle now owns the descriptor.

    return NextResponse.json({ success: true, jobId: id });
  } catch (err) {
    if (err instanceof AnsibleSelectionError) return NextResponse.json({ error: err.message }, { status: 400 });
    return NextResponse.json({ error: "Provisioning preparation failed" }, { status: 500 });
  } finally {
    await lease?.release().catch(() => {});
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
  lease: ProvisioningLease,
  signal: AbortSignal
) {
  let emitter: Awaited<ReturnType<typeof runAnsiblePlaybook>>;
  const release = async () => {
    activeJobs.delete(jobId);
    await lease.release().catch(() => {});
  };
  try { emitter = await runAnsiblePlaybook(playbookFile, roles, lease.fd, signal); }
  catch {
    try { await prisma.job.update({ where: { id: jobId }, data: { output: PREPARATION_OUTPUT + "[Provisioning runner could not start]\n", status: "failed", finishedAt: new Date() } }); }
    catch { console.error("Failed to save final provisioning state"); }
    finally { await release(); }
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
          try { await prisma.$executeRaw`UPDATE "jobs" SET "output" = "output" || ${text} WHERE "id" = ${jobId} AND "status" = 'running'`; }
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
          output: PREPARATION_OUTPUT + fullOutput,
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

    await release();
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

    await release();
  });
}
