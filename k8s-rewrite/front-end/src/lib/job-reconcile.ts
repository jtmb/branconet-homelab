import type { ProvisioningLease } from "./provisioning-lock";

export const ORPHAN_MARKER =
  "\n[The local provisioning runner exited without a recorded result. Inspect partial effects.]\n";

interface ReconcileClient {
  job: {
    findMany(args: { where: { status: "running"; id?: string }; select: { id: true } }): Promise<{ id: string }[]>;
  };
  $executeRaw(query: TemplateStringsArray, ...values: unknown[]): Promise<number>;
}

/** One SQLite write makes the claim atomic even across mismatched lock configs. */
export async function claimProvisioningJob(
    client: Pick<ReconcileClient, "$executeRaw">, lease: ProvisioningLease, playbook: string) {
  const id = lease.newJobId();
  const count = await client.$executeRaw`
    INSERT INTO "jobs" ("id", "playbook", "status", "output", "startedAt")
    SELECT ${id}, ${playbook}, 'running', '[Preparing provisioning]' || char(10), ${Date.now()}
    WHERE NOT EXISTS (SELECT 1 FROM "jobs" WHERE "status" = 'running')`;
  return count === 1 ? id : null;
}

/** Callers must hold the lease continuously through reconciliation and any new launch. */
export async function reconcileProvisioningJobs(client: ReconcileClient, lease: ProvisioningLease, id?: string) {
  const rows = await client.job.findMany({ where: { status: "running", ...(id ? { id } : {}) }, select: { id: true } });
  let interrupted = 0;
  let unknown = false;
  for (const row of rows) {
    if (!lease.ownsJobId(row.id)) {
      unknown = true;
      continue;
    }
    interrupted += await client.$executeRaw`
      UPDATE "jobs" SET "status" = 'interrupted', "finishedAt" = ${Date.now()},
                        "output" = "output" || ${ORPHAN_MARKER}
      WHERE "id" = ${row.id} AND "status" = 'running'`;
  }
  return { interrupted, unknown };
}
