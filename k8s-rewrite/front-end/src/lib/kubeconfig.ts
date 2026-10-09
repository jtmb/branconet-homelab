import { hasLocalKubectl } from "./k8s";
/** Operator kubeconfig or mounted service account only; no DB/SSH startup bootstrap. */
export async function ensureKubeconfig(): Promise<boolean> { return hasLocalKubectl(); }
