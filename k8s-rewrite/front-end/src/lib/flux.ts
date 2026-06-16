import { kubectlJSON, kubectlExec } from "./k8s";
import { encryptWithKey, decrypt } from "../../lib/encryption";
import prisma from "./db";
import { execFile } from "child_process";
import { promisify } from "util";
import { existsSync } from "fs";
import { homedir } from "os";

const execFileAsync = promisify(execFile);
const KUBECONFIG_PATH = `${homedir()}/.kube/config`;
const HAS_LOCAL_KUBECTL = existsSync(KUBECONFIG_PATH);

const FLUX_NAMESPACE = "flux-system";
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || "botrus-k8s-manager-key-2026";

// =============================================================================
// Helpers
// =============================================================================

function buildKubectlCmd(cmd: string): string {
  return `--namespace ${FLUX_NAMESPACE} ${cmd}`;
}

// =============================================================================
// Delete progress tracking (globalThis survives Next.js module isolation)
// =============================================================================

export interface DeleteStep {
  step: string;
  status: "pending" | "running" | "done" | "error";
  detail: string;
}

export interface DeleteProgress {
  deleteId: string;
  repoName: string;
  namespace: string;
  steps: DeleteStep[];
  done: boolean;
  error?: string;
}

const _global = globalThis as typeof globalThis & {
  __deleteProgress?: Map<string, DeleteProgress>;
};

if (!_global.__deleteProgress) {
  _global.__deleteProgress = new Map<string, DeleteProgress>();
}

const deleteProgressMap = _global.__deleteProgress;

export function getDeleteProgress(id: string): DeleteProgress | undefined {
  return deleteProgressMap.get(id);
}

// Clean up stale progress entries after 5 minutes
function scheduleProgressCleanup(id: string) {
  setTimeout(() => { deleteProgressMap.delete(id); }, 5 * 60 * 1000);
}

// =============================================================================
// GitRepository CRD
// =============================================================================

export async function createGitRepository(
  name: string,
  url: string,
  branch: string,
  path: string = "./",
  secretRef?: string,
): Promise<{ success: boolean; error?: string }> {
  const interval = "5m";

  const resource: any = {
    apiVersion: "source.toolkit.fluxcd.io/v1",
    kind: "GitRepository",
    metadata: { name, namespace: FLUX_NAMESPACE },
    spec: {
      interval,
      url,
      ref: { branch },
    },
  };

  if (secretRef) {
    resource.spec.secretRef = { name: secretRef };
  }

  const yaml = toYaml(resource);
  const result = await kubectlApplyYaml(yaml);

  if (!result) {
    return { success: false, error: "Failed to create GitRepository" };
  }
  return { success: true };
}

export async function createKustomization(
  name: string,
  sourceName: string,
  path: string = "./",
  targetNamespace?: string,
): Promise<{ success: boolean; error?: string }> {
  const interval = "5m";
  const prune = true;

  const resource: any = {
    apiVersion: "kustomize.toolkit.fluxcd.io/v1",
    kind: "Kustomization",
    metadata: { name, namespace: FLUX_NAMESPACE },
    spec: {
      interval,
      path,
      prune,
      sourceRef: {
        kind: "GitRepository",
        name: sourceName,
      },
    },
  };

  if (targetNamespace) {
    resource.spec.targetNamespace = targetNamespace;
  }

  const yaml = toYaml(resource);
  const result = await kubectlApplyYaml(yaml);

  if (!result) {
    return { success: false, error: "Failed to create Kustomization" };
  }
  return { success: true };
}

// =============================================================================
// Secret management for private repos
// =============================================================================

export async function createFluxSecret(
  name: string,
  type: "ssh" | "https",
  credentials: string,
): Promise<{ success: boolean; error?: string }> {
  // Secret name used by GitRepository
  const secretName = `${name}-auth`;

  if (type === "ssh") {
    // SSH deploy key: create secret with known_hosts and identity
    const knownHosts = await getGithubKnownHosts();
    const cmd = `create secret generic ${secretName} ` +
      `--from-literal=identity="${credentials}" ` +
      `--from-literal=known_hosts="${knownHosts}"`;
    const result = await kubectlJSON("u1", buildKubectlCmd(cmd));
    if (!result) {
      return { success: false, error: "Failed to create SSH secret" };
    }
  } else {
    // HTTPS token: create secret with username and password
    const cmd = `create secret generic ${secretName} ` +
      `--from-literal=username=git ` +
      `--from-literal=password="${credentials}"`;
    const result = await kubectlJSON("u1", buildKubectlCmd(cmd));
    if (!result) {
      return { success: false, error: "Failed to create HTTPS secret" };
    }
  }

  return { success: true };
}

async function getGithubKnownHosts(): Promise<string> {
  // Default GitHub SSH host key
  return "github.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCj7ndNxQowgcQnjshcLrqPEiiphnt+VTTvDP6mHBL9j1aNUkY4Ue1gvwnGLVlOhGeYrnZaMgRK6+PKCUXaDbC7qtbW8gIkhL7aGCsOr/C56SJMy/BCZfxd1nWzAOxSDPgOfmerHwyMCUHTPkUmRhln2LQaxLJCFZFCp0oL/cLvgl3kL0PoWgTQyDc6dKfK9ORLqaHVxKvKsUSdRLmGRpQn/Sy2keLI+0B1WGMj2AVJwNFhCVsuGGN4ZTZmTr6sWBPdLQaBhfEVMlnm6GIovJ6c+n/vOanIGCnYF2s1L3qGkYh/MPGKPJhK+VQFpF59FnR6iH7ZrLZRnPqk3DpD2btBfqHLMPQkKlRZmjRl5z0ZXoBWs6VNs/r4J/CQyQJyMtH+NR9uTZ1yPW7XGorLNYKDzL4JnMlAVqTMrpXAmd5qdMWsDKJLwnqImf+UJeR4D0EZ4qNBevbKmPKeipwZ42Wm3l7X5MvPTELdnJ1BbNerNa+j1PojpFeHTKkhgOs=";
}

// =============================================================================
// Status queries
// =============================================================================

export interface FluxRepoStatus {
  name: string;
  namespace: string;
  url: string;
  branch: string;
  path: string;
  ready: boolean;
  status: string; // e.g. "kustomize build failed: ..."
  sourceReady: boolean; // GitRepository artifact fetched OK?
  ksReady: boolean | null; // Kustomization applied OK? (null if no KS exists)
  lastSync?: string;
  revision?: string;
}

export async function getFluxStatus(): Promise<FluxRepoStatus[]> {
  // Fetch both GitRepositories and Kustomizations
  const [gitReposRaw, kustomizationsRaw] = await Promise.all([
    kubectlJSON("u1", buildKubectlCmd("get gitrepositories -o json")),
    kubectlJSON("u1", buildKubectlCmd("get kustomizations -o json")),
  ]);

  const kustomizations = (kustomizationsRaw?.items || []) as any[];

  if (!gitReposRaw?.items) return [];

  return gitReposRaw.items.map((item: any) => {
    const conditions = item.status?.conditions || [];
    const readyCond = conditions.find((c: any) => c.type === "Ready");
    const name = item.metadata?.name || "unknown";

    // Find matching Kustomization
    const ks = kustomizations.find((k: any) => k.metadata?.name === name);
    const ksConditions = ks?.status?.conditions || [];
    const ksReadyCond = ksConditions.find((c: any) => c.type === "Ready");

    // Merge error info: prefer Kustomization error > GitRepository error
    const sourceReady = readyCond?.status === "True";
    const ksReady = ksReadyCond?.status === "True";
    const combinedReady = sourceReady && (ks ? ksReady : true); // if no KS exists, only care about source
    const combinedMessage = ksReadyCond?.message || readyCond?.message || (combinedReady ? "Ready" : "Not Ready");

    return {
      name,
      namespace: item.metadata?.namespace || FLUX_NAMESPACE,
      url: item.spec?.url || "",
      branch: item.spec?.ref?.branch || "main",
      path: ks?.spec?.path || "./",
      ready: combinedReady,
      status: combinedMessage,
      sourceReady,
      ksReady: ks ? ksReady : null,
      lastSync: item.status?.lastHandledReconcileAt || null,
      revision: item.status?.artifact?.revision || null,
    };
  });
}

// =============================================================================
// Sync trigger
// =============================================================================

export async function triggerSync(name: string): Promise<{ success: boolean; error?: string }> {
  const cmd = `annotate gitrepository ${name} reconcile.fluxcd.io/requestedAt="${new Date().toISOString()}" --overwrite`;
  const result = await kubectlJSON("u1", buildKubectlCmd(cmd));
  if (!result) {
    return { success: false, error: "Failed to trigger sync" };
  }
  return { success: true };
}

// =============================================================================
// DB-backed repo management (combines DB + K8s CRDs)
// =============================================================================

export interface GitRepoRecord {
  id: string;
  name: string;
  url: string;
  branch: string;
  path: string;
  namespace: string;
  authMethod: string;
  syncInterval: string;
  status: string;
  lastSync: string | null;
  lastError: string | null;
  createdAt: string;
  updatedAt: string;
  // Live Flux status merged in
  fluxReady?: boolean;
  fluxStatus?: string;
  fluxRevision?: string;
  sourceReady?: boolean;
  ksReady?: boolean | null;
}

export async function listRepos(): Promise<GitRepoRecord[]> {
  const dbRepos = await prisma.gitRepo.findMany({
    orderBy: { createdAt: "desc" },
  });

  const fluxStatuses = await getFluxStatus();

  return dbRepos.map((repo) => {
    const flux = fluxStatuses.find((f) => f.name === repo.name);
    return {
      ...repo,
      authData: undefined, // Never expose auth data
      createdAt: repo.createdAt.toISOString(),
      updatedAt: repo.updatedAt.toISOString(),
      lastSync: repo.lastSync?.toISOString() || null,
      namespace: repo.namespace || repo.name, // Default to repo name
      fluxReady: flux?.ready,
      fluxStatus: flux?.status,
      fluxRevision: flux?.revision,
      sourceReady: flux?.sourceReady,
      ksReady: flux?.ksReady,
    } as GitRepoRecord;
  });
}

export async function addRepo(data: {
  name: string;
  url: string;
  branch?: string;
  path?: string;
  authMethod?: string;
  authData?: string; // raw deploy key or token (will be encrypted)
}): Promise<{ success: boolean; repo?: GitRepoRecord; error?: string }> {
  const branch = data.branch || "main";
  const path = data.path || "./";
  const authMethod = data.authMethod || "none";
  const ns = data.name; // Namespace = repo name convention

  // 1. Encrypt auth data if provided
  let encryptedAuth = "";
  if (data.authData && authMethod !== "none") {
    const enc = encryptWithKey(data.authData, ENCRYPTION_KEY);
    encryptedAuth = JSON.stringify(enc);
  }

  // 2. Save to DB
  let repo;
  try {
    repo = await prisma.gitRepo.create({
      data: {
        name: data.name,
        url: data.url,
        branch,
        path,
        namespace: ns,
        authMethod,
        authData: encryptedAuth,
      },
    });
  } catch (err: any) {
    if (err?.code === "P2002") {
      return { success: false, error: `Repository "${data.name}" already exists` };
    }
    return { success: false, error: String(err) };
  }

  // 3. Create K8s Secret if auth needed
  let secretRef: string | undefined;
  if (authMethod !== "none" && data.authData) {
    const secretResult = await createFluxSecret(data.name, authMethod as "ssh" | "https", data.authData);
    if (secretResult.success) {
      secretRef = `${data.name}-auth`;
    } else {
      return { success: false, error: `Failed to create auth secret: ${secretResult.error}` };
    }
  }

  // 4. Create GitRepository CRD
  const grResult = await createGitRepository(data.name, data.url, branch, path, secretRef);
  if (!grResult.success) {
    return { success: false, error: `Failed to create GitRepository: ${grResult.error}` };
  }

  // 5. Create Kustomization CRD with targetNamespace so Flux auto-creates the namespace
  const ksResult = await createKustomization(data.name, data.name, path, ns);
  if (!ksResult.success) {
    return { success: false, error: `Failed to create Kustomization: ${ksResult.error}` };
  }

  return {
    success: true,
    repo: {
      ...repo,
      authData: undefined,
      createdAt: repo.createdAt.toISOString(),
      updatedAt: repo.updatedAt.toISOString(),
      namespace: ns,
      lastSync: null,
    } as GitRepoRecord,
  };
}

export async function removeRepo(
  id: string,
): Promise<{ success: boolean; deleteId?: string; error?: string }> {
  const repo = await prisma.gitRepo.findUnique({ where: { id } });
  if (!repo) {
    return { success: false, error: "Repository not found" };
  }

  const ns = repo.namespace || repo.name;
  const deleteId = id;

  const progress: DeleteProgress = {
    deleteId,
    repoName: repo.name,
    namespace: ns,
    steps: [
      { step: "flux_crds", status: "pending", detail: "Deleting Flux resources…" },
      { step: "namespace", status: "pending", detail: `Deleting namespace "${ns}"…` },
      { step: "volumes", status: "pending", detail: "Cleaning up persistent volumes…" },
      { step: "db", status: "pending", detail: "Removing from database…" },
    ],
    done: false,
  };

  deleteProgressMap.set(deleteId, progress);
  scheduleProgressCleanup(deleteId);

  // Run async — don't await, let it complete in the background
  performCascadeDelete(deleteId, repo.name, ns, id).catch((err) => {
    const p = deleteProgressMap.get(deleteId);
    if (p) {
      p.done = true;
      p.error = String(err);
    }
  });

  return { success: true, deleteId };
}

// =============================================================================
// Cascade delete: Flux CRDs → namespace (polled) → DB
// =============================================================================

async function performCascadeDelete(
  deleteId: string,
  name: string,
  namespace: string,
  dbId: string,
) {
  const progress = deleteProgressMap.get(deleteId);
  if (!progress) return;

  // --- Step 1: Delete Flux CRDs ---
  progress.steps[0].status = "running";
  try { await kubectlJSON("u1", `--namespace flux-system delete kustomization ${name} --ignore-not-found`); } catch {}
  try { await kubectlJSON("u1", `--namespace flux-system delete gitrepository ${name} --ignore-not-found`); } catch {}
  try { await kubectlJSON("u1", `--namespace flux-system delete secret ${name}-auth --ignore-not-found`); } catch {}
  progress.steps[0].status = "done";

  // --- Step 2: Delete namespace with polling ---
  progress.steps[1].status = "running";

  // Capture PV names bound to PVCs in this namespace BEFORE deletion
  const pvOutput = await kubectlExec(
    `get pvc -n ${namespace} -o custom-columns=PV:.spec.volumeName --no-headers`,
  );
  const boundPVs = pvOutput
    ? pvOutput
        .trim()
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
    : [];

  const deleteResult = await kubectlExec(`delete namespace ${namespace} --wait=false --ignore-not-found`);

  // If the delete command itself failed, namespace might not exist
  if (deleteResult === null) {
    // Namespace might already be gone or never existed — check
    const stillThere = await kubectlExec(`get namespace ${namespace} --no-headers`);
    if (stillThere && stillThere.trim()) {
      progress.steps[1].status = "error";
      progress.steps[1].detail = `Failed to issue delete for namespace "${namespace}"`;
    } else {
      progress.steps[1].status = "done";
      progress.steps[1].detail = `Namespace "${namespace}" already gone`;
    }
  } else {
    for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 2000));

    const nsCheck = await kubectlExec(`get namespace ${namespace} --no-headers`);
    if (!nsCheck || !nsCheck.trim()) {
      progress.steps[1].status = "done";
      progress.steps[1].detail = `Namespace "${namespace}" deleted`;
      break;
    }

    // Count remaining pods while namespace is terminating
    const pods = await kubectlExec(`get pods -n ${namespace} --no-headers`);
    const podCount = pods ? pods.trim().split("\n").filter(Boolean).length : 0;
    if (podCount > 0) {
      progress.steps[1].detail = `Terminating: ${podCount} pod${podCount !== 1 ? "s" : ""} remaining…`;
    } else {
      progress.steps[1].detail = "Waiting for namespace cleanup…";
    }
    }
  }

  if (progress.steps[1].status !== "done") {
    progress.steps[1].status = "error";
    progress.steps[1].detail = `Namespace deletion timed out — "${namespace}" may still be terminating`;
  }

  // --- Step 3: Clean up orphaned PersistentVolumes ---
  progress.steps[2].status = "running";
  if (boundPVs.length > 0) {
    const pvList = boundPVs.join(" ");
    try {
      await kubectlExec(`delete pv ${pvList} --force --grace-period=0 --ignore-not-found`);
      progress.steps[2].status = "done";
      progress.steps[2].detail = `Deleted ${boundPVs.length} volume${boundPVs.length !== 1 ? "s" : ""}: ${boundPVs.join(", ")}`;
    } catch (err) {
      progress.steps[2].status = "error";
      progress.steps[2].detail = `Failed to delete volumes: ${String(err)}`;
    }
  } else {
    progress.steps[2].status = "done";
    progress.steps[2].detail = "No bound volumes to clean up";
  }

  // --- Step 4: Delete from DB ---
  progress.steps[3].status = "running";
  try {
    await prisma.gitRepo.delete({ where: { id: dbId } });
    progress.steps[3].status = "done";
  } catch (err) {
    progress.steps[3].status = "error";
    progress.steps[3].detail = String(err);
  }

  progress.done = true;
}

export async function syncRepo(
  id: string,
): Promise<{ success: boolean; error?: string }> {
  const repo = await prisma.gitRepo.findUnique({ where: { id } });
  if (!repo) {
    return { success: false, error: "Repository not found" };
  }
  return triggerSync(repo.name);
}

// =============================================================================
// Low-level YAML helpers
// =============================================================================

function toYaml(obj: any, indent = 0): string {
  const pad = "  ".repeat(indent);
  let yaml = "";

  for (const [key, value] of Object.entries(obj)) {
    if (value === null || value === undefined) continue;

    if (Array.isArray(value)) {
      yaml += `${pad}${key}:\n`;
      for (const item of value) {
        if (typeof item === "object" && item !== null) {
          yaml += `${pad}  - ${toYaml(item, indent + 2).trimStart()}\n`;
        } else {
          yaml += `${pad}  - ${item}\n`;
        }
      }
    } else if (typeof value === "object" && value !== null) {
      yaml += `${pad}${key}:\n${toYaml(value, indent + 1)}`;
    } else if (typeof value === "boolean") {
      yaml += `${pad}${key}: ${value}\n`;
    } else if (typeof value === "number") {
      yaml += `${pad}${key}: ${value}\n`;
    } else {
      const str = String(value);
      // Quote if contains special YAML chars
      if (str.includes(":") || str.includes("#") || str.includes("{") || str.includes("[")) {
        yaml += `${pad}${key}: "${str.replace(/"/g, '\\"')}"\n`;
      } else {
        yaml += `${pad}${key}: ${str}\n`;
      }
    }
  }

  return yaml;
}

async function kubectlApplyYaml(yaml: string): Promise<boolean> {
  const fileName = `/tmp/flux-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.yaml`;

  // Prefer local kubectl if kubeconfig is available
  if (HAS_LOCAL_KUBECTL) {
    const { writeFile, unlink } = await import("fs/promises");
    try {
      await writeFile(fileName, yaml);
      const { stdout } = await execFileAsync(
        "kubectl",
        ["--kubeconfig", KUBECONFIG_PATH, "apply", "-f", fileName],
        { timeout: 15000 }
      );
      try { await unlink(fileName); } catch {}
      return stdout.includes("created") || stdout.includes("configured") || stdout.includes("unchanged");
    } catch {
      try { await unlink(fileName); } catch {}
      return false;
    }
  }

  // Fallback: SSH-based apply (writes YAML via heredoc, applies, cleans up)
  const cmd = `cat > ${fileName} << 'FLUXEOF'\n${yaml}\nFLUXEOF\nkubectl --kubeconfig=/etc/kubernetes/admin.conf apply -f ${fileName} 2>&1\nrm -f ${fileName}`;
  const { sshExec } = await import("./k8s");
  const result = await sshExec("u1", cmd, 15000);

  if (result === null) return false;
  return result.includes("created") || result.includes("configured") || result.includes("unchanged");
}
