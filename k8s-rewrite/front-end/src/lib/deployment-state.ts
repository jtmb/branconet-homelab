export function deploymentPods(deployment: any, pods: any[], replicaSets: any[]) {
  const namespace = deployment.metadata?.namespace, uid = deployment.metadata?.uid;
  if (!uid) return [];
  const owned = new Set(replicaSets.filter(rs => rs.metadata?.uid && rs.metadata?.namespace === namespace && rs.metadata?.ownerReferences?.some((owner: any) => owner.kind === "Deployment" && owner.uid === uid && owner.controller === true)).map(rs => rs.metadata.uid));
  return pods.filter(pod => pod.metadata?.namespace === namespace && pod.metadata?.ownerReferences?.some((owner: any) => owner.kind === "ReplicaSet" && owner.controller === true && owned.has(owner.uid)));
}

const count = (value: unknown, fallback = 0) => Number.isInteger(value) && Number(value) >= 0 ? Number(value) : fallback;
export function deploymentState(deployment: any) {
  const desired = count(deployment.spec?.replicas, 1), observed = count(deployment.status?.replicas);
  const ready = count(deployment.status?.readyReplicas), updated = count(deployment.status?.updatedReplicas), available = count(deployment.status?.availableReplicas);
  const generation = count(deployment.metadata?.generation), observedGeneration = count(deployment.status?.observedGeneration);
  const conditions = deployment.status?.conditions || [];
  const failed = conditions.some((condition: any) => condition.type === "ReplicaFailure" && condition.status === "True" || condition.type === "Progressing" && condition.status === "False" && condition.reason === "ProgressDeadlineExceeded");
  const state = deployment.metadata?.deletionTimestamp ? "Deleting" : failed ? "Failed" : deployment.spec?.paused ? "Paused" : observedGeneration < generation ? "Reconciling" : desired === 0 ? observed === 0 && ready === 0 && updated === 0 && available === 0 ? "Scaled down" : "Scaling down" : ready === desired && updated === desired && available === desired && observed === desired ? "Ready" : updated < desired ? "Updating" : "Progressing";
  return {
    state, health: failed ? "Degraded" : state === "Ready" || state === "Scaled down" ? "Healthy" : "Progressing",
    desiredReplicas: desired, observedReplicas: observed, readyReplicas: ready, updatedReplicas: updated, availableReplicas: available,
    generation, observedGeneration, ready: `${ready}/${desired}`, upToDate: updated, available,
  };
}

export function podRestarts(pod: any): number {
  return [...(pod.status?.containerStatuses || []), ...(pod.status?.initContainerStatuses || [])].reduce((sum, container) => sum + count(container.restartCount), 0);
}
