export const RESOURCE_CAPABILITIES = {
  pod: { collection: "pods", kind: "Pod", apiVersion: "v1", namespaced: true, yamlEdit: true, delete: true, logs: true, actions: [] },
  deployment: { collection: "deployments", kind: "Deployment", apiVersion: "apps/v1", namespaced: true, yamlEdit: true, delete: true, logs: false, actions: ["restart", "rollback", "pause", "resume", "scale"] },
  namespace: { collection: "namespaces", kind: "Namespace", apiVersion: "v1", namespaced: false, yamlEdit: true, delete: true, logs: false, actions: [] },
  node: { collection: "nodes", kind: "Node", apiVersion: "v1", namespaced: false, yamlEdit: false, delete: false, logs: false, actions: ["cordon", "uncordon", "drain"] },
  ingress: { collection: "ingresses", kind: "Ingress", apiVersion: "networking.k8s.io/v1", namespaced: true, yamlEdit: true, delete: true, logs: false, actions: [] },
  service: { collection: "services", kind: "Service", apiVersion: "v1", namespaced: true, yamlEdit: false, delete: false, logs: false, actions: [] },
  pvc: { collection: "volumes", kind: "PersistentVolumeClaim", apiVersion: "v1", namespaced: true, yamlEdit: false, delete: false, logs: false, actions: [] },
} as const;
export type ResourceType = keyof typeof RESOURCE_CAPABILITIES;

export function resourceBase(type: ResourceType, namespace: string, name: string) {
  const capability = RESOURCE_CAPABILITIES[type];
  return `/api/cluster/${capability.collection}/${capability.namespaced ? `${encodeURIComponent(namespace)}/` : ""}${encodeURIComponent(name)}`;
}
