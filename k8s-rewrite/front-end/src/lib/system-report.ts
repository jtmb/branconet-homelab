import { activeJobs } from "./active-jobs";
import { getCachedClusterResource } from "./cluster-cache";
import { workloadInventory } from "./system-report-inventory";
import { SystemReportJobs } from "./system-report-jobs";
import { localTrivyScanner } from "./system-report-scanner";

async function inventory() {
  const [pods, services, replicasets] = await Promise.all([
    getCachedClusterResource("pods"), getCachedClusterResource("services"), getCachedClusterResource("replicasets"),
  ]);
  return workloadInventory({ pods: pods.value?.items, services: services.value?.items, replicasets: replicasets.value?.items,
    sampledAt: pods.availability.sampledAt, stale: [pods, services, replicasets].some(snapshot => snapshot.availability.state === "stale") });
}
const globals = globalThis as typeof globalThis & { __bortusSystemReports?: SystemReportJobs };
export const systemReports = globals.__bortusSystemReports ??= new SystemReportJobs(inventory, localTrivyScanner(), activeJobs);
