import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { runAnsiblePlaybook } from "@/lib/ansible";
import { activeJobs } from "@/lib/active-jobs";
import { syncVarsToYAML, syncInventoryToFile } from "@/lib/sync-vars";
import { invalidateCache } from "@/lib/cluster-cache";
import { sshExec } from "@/lib/k8s";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { playbook, roles } = body;
    const playbookFile = playbook || "site.yml";

    // ── Sync vars from DB to YAML files before deploying ──
    // This ensures the latest DB values are used by Ansible.
    try {
      const varResult = await syncVarsToYAML();
      console.log(`[deploy] Synced ${varResult.synced} vars to ${varResult.file}`);
    } catch (syncErr) {
      console.error("[deploy] Failed to sync vars:", syncErr);
      // Continue — use whatever is on disk
    }

    try {
      const invResult = await syncInventoryToFile();
      console.log(`[deploy] Synced ${invResult.synced} nodes to ${invResult.file}`);
    } catch (syncErr) {
      console.error("[deploy] Failed to sync inventory:", syncErr);
    }

    // Create job record in SQLite via Prisma
    const job = await prisma.job.create({
      data: {
        playbook: playbookFile,
        status: "running",
        output: `[Synced vars from DB to group_vars/all.yml]\n`,
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
    return NextResponse.json({ error: String(err) }, { status: 500 });
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

        // Fetch kubeconfig from the deployed master node
        try {
          const masterNode = await prisma.node.findFirst({
            where: { role: "master" },
          });
          if (masterNode) {
            const kubeconfig = await sshExec(
              masterNode.ipAddress,
              "sudo cat /etc/kubernetes/admin.conf"
            );
            if (kubeconfig) {
              await prisma.clusterState.upsert({
                where: { id: "singleton" },
                update: {
                  kubeconfig,
                  deployed: true,
                  deployedAt: new Date(),
                },
                create: {
                  id: "singleton",
                  kubeconfig,
                  deployed: true,
                  deployedAt: new Date(),
                },
              });
              console.log("[deploy] Kubeconfig captured and stored");
            }
          }
        } catch (kubeErr) {
          console.error("[deploy] Failed to capture kubeconfig:", kubeErr);
          // Non-fatal — cluster is still deployed
        }
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