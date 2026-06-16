import prisma from "./db";
import { sshExec, hasLocalKubectl } from "./k8s";
import { existsSync } from "fs";
import { mkdir, writeFile } from "fs/promises";
import { homedir } from "os";

const KUBECONFIG_DIR = `${homedir()}/.kube`;
const KUBECONFIG_PATH = `${KUBECONFIG_DIR}/config`;

/**
 * Ensure a local kubeconfig exists at ~/.kube/config so all kubectl
 * commands can run locally via execFile (no SSH fallback).
 *
 * This is THE ONLY place in the app that SSHes to the cluster.
 * Strategy (in order):
 *   1. Already exists — nothing to do
 *   2. Stored in DB (prisma.clusterState.kubeconfig) — write it to disk
 *   3. Fetch from master node via SSH — sudo cat /etc/kubernetes/admin.conf
 *
 * Returns true if a kubeconfig is now on disk, false if we couldn't get one.
 */
export async function ensureKubeconfig(): Promise<boolean> {
  // Already have it locally
  if (hasLocalKubectl()) {
    return true;
  }

  // Try the DB — deploy/start writes kubeconfig to clusterState on success
  try {
    const state = await prisma.clusterState.findFirst({
      where: { deployed: true },
    });
    if (state?.kubeconfig) {
      await mkdir(KUBECONFIG_DIR, { recursive: true });
      await writeFile(KUBECONFIG_PATH, state.kubeconfig, { mode: 0o600 });
      console.log("[kubeconfig] Written from DB (clusterState)");
      return true;
    }
  } catch (err) {
    console.error("[kubeconfig] DB lookup failed:", err);
    // Continue to SSH fallback
  }

  // Last resort: SSH to master and grab /etc/kubernetes/admin.conf
  try {
    const master = await prisma.node.findFirst({
      where: { role: "master" },
    });
    if (!master?.ipAddress) {
      console.error("[kubeconfig] No master node in DB");
      return false;
    }

    const adminConf = await sshExec(
      master.ipAddress,
      "sudo cat /etc/kubernetes/admin.conf"
    );
    if (!adminConf) {
      console.error("[kubeconfig] SSH failed or admin.conf empty");
      return false;
    }

    await mkdir(KUBECONFIG_DIR, { recursive: true });
    await writeFile(KUBECONFIG_PATH, adminConf, { mode: 0o600 });
    console.log("[kubeconfig] Fetched from master node via SSH");
    return true;
  } catch (err) {
    console.error("[kubeconfig] SSH fetch failed:", err);
    return false;
  }
}
