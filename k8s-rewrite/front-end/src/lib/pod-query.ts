import { KubernetesCommandError, validateNamespace, validateResourceName } from "./kubectl-client";
import { podRestarts } from "./deployment-state";

const SYSTEM_NAMESPACES = new Set(["kube-system", "kube-public", "kube-node-lease", "calico-system", "calico-apiserver", "tigera-operator", "longhorn-system", "cert-manager", "metallb-system", "ingress-nginx", "flux-system", "traefik", "local-path-storage"]);
const selectorError = () => new KubernetesCommandError(400, "Invalid label selector");
const validValue = (value: string) => value.length <= 63 && (value === "" || /^[a-zA-Z0-9](?:[a-zA-Z0-9_.-]*[a-zA-Z0-9])?$/.test(value));
function validKey(key: string) {
  const parts = key.split("/");
  if (parts.length > 2) throw selectorError();
  if (parts.length === 2) { try { validateResourceName(parts[0]); } catch { throw selectorError(); } }
  if (!parts.at(-1) || !validValue(parts.at(-1)!)) throw selectorError();
}

export function labelPredicate(selector: string | null): (labels: Record<string, string>) => boolean {
  if (selector === null || selector === "") return () => true;
  if (selector.length > 2048) throw selectorError();
  const parts = selector.split(/,(?![^()]*\))/);
  if (parts.length > 20) throw selectorError();
  const predicates = parts.map(part => {
    const match = part.trim().match(/^(!?)([a-zA-Z0-9_.\/-]+)(?:\s+(in|notin)\s*\(([^()]*)\)|\s*(==|!=|=)\s*([a-zA-Z0-9_.-]*))?$/);
    if (!match) throw selectorError();
    const [, absent, key, setOperator, setValues, operator, value] = match;
    validKey(key);
    if (absent && (setOperator || operator)) throw selectorError();
    if (setOperator) {
      const values = setValues.split(",").map(item => item.trim());
      if (!values.length || values.length > 64 || values.some(item => !item || !validValue(item))) throw selectorError();
      return (labels: Record<string, string>) => setOperator === "in" ? Object.hasOwn(labels, key) && values.includes(labels[key]) : !Object.hasOwn(labels, key) || !values.includes(labels[key]);
    }
    if (operator && !validValue(value)) throw selectorError();
    return (labels: Record<string, string>) => absent ? !Object.hasOwn(labels, key) : operator === "!=" ? !Object.hasOwn(labels, key) || labels[key] !== value : operator ? Object.hasOwn(labels, key) && labels[key] === value : Object.hasOwn(labels, key);
  });
  return labels => predicates.every(predicate => predicate(labels));
}

export function podFilter(query: URLSearchParams) {
  const type = query.get("type") || "all", namespace = query.get("namespace");
  if (!["all", "app", "system"].includes(type)) throw new KubernetesCommandError(400, "Invalid pod type");
  if (namespace !== null) validateNamespace(namespace);
  const labels = labelPredicate(query.get("labelSelector"));
  return (pod: any) => {
    const ns = pod.metadata?.namespace || "default", metadataLabels = pod.metadata?.labels || {};
    const override = metadataLabels["branconet.io/type"];
    const podType = ["app", "system"].includes(override) ? override : SYSTEM_NAMESPACES.has(ns) ? "system" : "app";
    return (type === "all" || type === podType) && (namespace === null || namespace === ns) && labels(metadataLabels);
  };
}

export function podSummary(pod: any) {
  const namespace = pod.metadata?.namespace || "default", name = pod.metadata?.name || "unknown";
  const statuses = pod.status?.containerStatuses || [], containers = pod.spec?.containers || [];
  return {
    id: pod.metadata?.uid || `${namespace}/${name}`, name, namespace, status: pod.status?.phase || "Unknown",
    ready: `${statuses.filter((container: any) => container.ready).length}/${containers.length || statuses.length}`,
    restarts: podRestarts(pod), image: containers.map((container: any) => container.image).join(", ") || "-",
    ip: pod.status?.podIP || "-", node: pod.spec?.nodeName || "-", created: pod.metadata?.creationTimestamp || null,
    labels: pod.metadata?.labels || {},
  };
}
