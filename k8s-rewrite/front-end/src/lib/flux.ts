import { kubectlJSON } from "./k8s";
import { encryptWithKey, decrypt } from "../../lib/encryption";
import prisma from "./db";

const FLUX_NAMESPACE = "flux-system";
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || "branconet-k8s-manager-key-2026";

// =============================================================================
// Helpers
// =============================================================================

function buildKubectlCmd(cmd: string): string {
  return `--namespace ${FLUX_NAMESPACE} ${cmd}`;
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
  status: string; // e.g. "Stalled: reconciliation failed"
  lastSync?: string;
  revision?: string;
}

export async function getFluxStatus(): Promise<FluxRepoStatus[]> {
  const raw = await kubectlJSON("u1", buildKubectlCmd("get gitrepositories -o json"));
  if (!raw?.items) return [];

  return raw.items.map((item: any) => {
    const conditions = item.status?.conditions || [];
    const readyCond = conditions.find((c: any) => c.type === "Ready");

    return {
      name: item.metadata?.name || "unknown",
      namespace: item.metadata?.namespace || FLUX_NAMESPACE,
      url: item.spec?.url || "",
      branch: item.spec?.ref?.branch || "main",
      path: "./", // Kustomization path is separate; we derive from Kustomization
      ready: readyCond?.status === "True",
      status: readyCond?.message || (readyCond?.status === "True" ? "Ready" : "Not Ready"),
      lastSync: item.status?.lastHandledReconcileAt || null,
      revision: item.status?.artifact?.revision || null,
    };
  });
}

// =============================================================================
// Delete
// =============================================================================

export async function deleteGitRepo(
  name: string,
): Promise<{ success: boolean; error?: string }> {
  // Delete Kustomization first
  await kubectlJSON("u1", buildKubectlCmd(`delete kustomization ${name} --ignore-not-found`));

  // Delete GitRepository
  const result = await kubectlJSON("u1", buildKubectlCmd(`delete gitrepository ${name} --ignore-not-found`));
  if (!result) {
    return { success: false, error: "Failed to delete GitRepository" };
  }

  // Delete auth secret if it exists
  await kubectlJSON("u1", buildKubectlCmd(`delete secret ${name}-auth --ignore-not-found`));

  return { success: true };
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
      fluxReady: flux?.ready,
      fluxStatus: flux?.status,
      fluxRevision: flux?.revision,
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

  // 5. Create Kustomization CRD (Flux needs both to actually deploy)
  const ksResult = await createKustomization(data.name, data.name, path);
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
      lastSync: null,
    } as GitRepoRecord,
  };
}

export async function removeRepo(
  id: string,
): Promise<{ success: boolean; error?: string }> {
  const repo = await prisma.gitRepo.findUnique({ where: { id } });
  if (!repo) {
    return { success: false, error: "Repository not found" };
  }

  // Delete K8s resources
  const delResult = await deleteGitRepo(repo.name);
  if (!delResult.success) {
    return { success: false, error: delResult.error };
  }

  // Delete from DB
  await prisma.gitRepo.delete({ where: { id } });

  return { success: true };
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
  // Use kubectl apply with stdin via a temporary approach: echo the YAML and pipe to kubectl
  // Since kubectlJSON uses execFile, we go through SSH for piping
  // Alternative: write to temp file and apply it
  const escaped = yaml
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\$/g, "\\$")
    .replace(/`/g, "\\`");

  const cmd = `echo "${escaped}" | kubectl --kubeconfig=/etc/kubernetes/admin.conf apply -f -`;
  const { sshExec } = await import("./k8s");
  const result = await sshExec("u1", cmd, 15000);

  if (result === null) return false;
  return result.includes("created") || result.includes("configured") || result.includes("unchanged");
}
