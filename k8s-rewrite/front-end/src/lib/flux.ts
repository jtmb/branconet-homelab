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
// Hierarchy Tree — Fleet-style expandable repo view
// =============================================================================

export type FluxNodeKind = "GitRepository" | "Kustomization" | "HelmRelease" | "Namespace";

export interface FluxTreeNode {
  id: string;
  name: string;
  kind: FluxNodeKind;
  url?: string;
  branch?: string;
  path?: string;
  namespace: string;
  ready: boolean;
  status: string;
  lastSync: string | null;
  revision: string | null;
  authMethod?: string;
  suspended?: boolean;
  children: FluxTreeNode[];
}

export async function getFluxHierarchy(): Promise<FluxTreeNode[]> {
  // Fetch all Flux resources + DB records in parallel
  const [gitReposRaw, kustomizationsRaw, helmReleasesRaw, dbRepos] = await Promise.all([
    kubectlJSON("u1", buildKubectlCmd("get gitrepositories -o json")),
    kubectlJSON("u1", buildKubectlCmd("get kustomizations -o json")),
    kubectlJSON("u1", `--all-namespaces get helmreleases -o json`).catch(() => null),
    prisma.gitRepo.findMany({ orderBy: { createdAt: "desc" } }),
  ]);

  const gitRepos = (gitReposRaw?.items || []) as any[];
  const kustomizations = (kustomizationsRaw?.items || []) as any[];
  const helmReleases = (helmReleasesRaw?.items || []) as any[];

  // Index Kustomizations by sourceRef name (for parent → child linking)
  const ksBySource = new Map<string, any[]>();
  for (const ks of kustomizations) {
    const sourceName = ks.spec?.sourceRef?.name || ks.metadata?.name;
    if (!ksBySource.has(sourceName)) ksBySource.set(sourceName, []);
    ksBySource.get(sourceName)!.push(ks);
  }

  // Index HelmReleases by sourceRef name
  const hrBySource = new Map<string, any[]>();
  for (const hr of helmReleases) {
    const sourceName = hr.spec?.chart?.spec?.sourceRef?.name;
    if (sourceName) {
      if (!hrBySource.has(sourceName)) hrBySource.set(sourceName, []);
      hrBySource.get(sourceName)!.push(hr);
    }
  }

  // DB lookup by name for auth/id metadata
  const dbByName = new Map(dbRepos.map((r) => [r.name, r]));

  // Build tree: each GitRepository is a root node with its Kustomizations + HelmReleases as children
  const trees: FluxTreeNode[] = gitRepos.map((gr: any) => {
    const name = gr.metadata?.name || "unknown";
    const conditions = gr.status?.conditions || [];
    const readyCond = conditions.find((c: any) => c.type === "Ready");
    const sourceReady = readyCond?.status === "True";
    const dbRepo = dbByName.get(name);

    const children: FluxTreeNode[] = [];

    // Kustomization children (linked by sourceRef.name === GitRepository name)
    const repoKS = ksBySource.get(name) || [];
    for (const ks of repoKS) {
      const ksName = ks.metadata?.name || "unknown";
      const ksConditions = ks.status?.conditions || [];
      const ksReadyCond = ksConditions.find((c: any) => c.type === "Ready");
      const ksReady = ksReadyCond?.status === "True";

      // This Kustomization might itself be a source for sub-kustomizations or helmreleases
      const subKS = (ksBySource.get(ksName) || [])
        .filter((s) => s.metadata?.uid !== ks.metadata?.uid);
      const subHR = hrBySource.get(ksName) || [];

      const subChildren: FluxTreeNode[] = [
        ...subKS.map((s: any) => buildKustomizationNode(s)),
        ...subHR.map((h: any) => buildHelmReleaseNode(h)),
      ];

      // Parse inventory entries to surface managed namespaces as children
      const inventoryEntries: { id: string; v: string }[] = ks.status?.inventory?.entries || [];
      const namespacesSeen = new Set<string>();
      for (const entry of inventoryEntries) {
        const parsed = parseFluxInventoryId(entry.id);
        if (parsed.namespace && !namespacesSeen.has(parsed.namespace)) {
          namespacesSeen.add(parsed.namespace);
          subChildren.push({
            id: `ns-${ks.metadata?.uid || ksName}-${parsed.namespace}`,
            name: parsed.namespace,
            kind: "Namespace",
            namespace: parsed.namespace,
            ready: ksReady,
            status: ksReady ? "Managed" : "Pending",
            lastSync: null,
            revision: null,
            children: [],
          });
        }
      }

      children.push({
        id: `ks-${ks.metadata?.uid || ksName}`,
        name: ksName,
        kind: "Kustomization",
        path: ks.spec?.path || "./",
        namespace: ks.metadata?.namespace || FLUX_NAMESPACE,
        ready: ksReady,
        status: ksReadyCond?.message || (ksReady ? "Ready" : "Not Ready"),
        lastSync: ks.status?.lastHandledReconcileAt || null,
        revision: ks.status?.lastAppliedRevision || null,
        children: subChildren,
      });
    }

    // HelmRelease children (linked by chart.spec.sourceRef.name === GitRepository name)
    const repoHR = hrBySource.get(name) || [];
    for (const hr of repoHR) {
      children.push(buildHelmReleaseNode(hr));
    }

    const suspended = gr.spec?.suspend === true;

    return {
      id: dbRepo?.id || `gr-${gr.metadata?.uid || name}`,
      name,
      kind: "GitRepository",
      url: gr.spec?.url || "",
      branch: gr.spec?.ref?.branch || "main",
      path: repoKS[0]?.spec?.path || "./",
      namespace: gr.metadata?.namespace || FLUX_NAMESPACE,
      ready: sourceReady,
      status: readyCond?.message || (sourceReady ? "Ready" : "Not Ready"),
      lastSync: gr.status?.lastHandledReconcileAt || null,
      revision: gr.status?.artifact?.revision || null,
      authMethod: dbRepo?.authMethod || "none",
      suspended,
      children,
    };
  });

  // Filter 1: remove suspended GitRepositories — they're in the cluster but inert
  // Filter 2: remove self-referencing orphan GitRepositories.
  //   A GitRepository whose NAME matches the repo in its URL (e.g. "branconet-homelab" pointing to
  //   github.com/…/branconet-homelab.git) with zero downstream Kustomizations/HelmReleases is a
  //   bootstrap artifact — the "real" repo with a different name (like branconet-charts or plex)
  //   that points to the same URL already handles any configs under it.
  const urlRepoCount = new Map<string, number>(); // how many repos share each URL
  for (const t of trees) {
    if (t.url) urlRepoCount.set(t.url, (urlRepoCount.get(t.url) || 0) + 1);
  }

  return trees.filter((t) => {
    if (t.suspended) return false;
    // Always keep repos that have their own downstream resources
    if (t.children.length > 0) return true;
    if ((ksBySource.get(t.name)?.length ?? 0) > 0) return true;
    if ((hrBySource.get(t.name)?.length ?? 0) > 0) return true;
    // If this repo shares a URL with at least one other repo, AND its name matches
    // the repo part of that URL (self-referencing bootstrap cruft), hide it.
    if (t.url && (urlRepoCount.get(t.url) || 0) > 1) {
      const repoFromUrl = t.url.split("/").pop()?.replace(/\.git$/, "") || "";
      if (t.name === repoFromUrl) return false;
    }
    return true;
  });
}

/** Parse a Flux inventory entry ID into its components.
 *  Format: namespace_name_apiGroup_Kind (double-underscore __ means empty segment) */
function parseFluxInventoryId(id: string): { namespace: string; name: string; apiGroup: string; kind: string } {
  const parts = id.split("_");
  const kind = parts[parts.length - 1] || "";
  const apiGroup = parts.length >= 2 ? parts[parts.length - 2] : "";
  const remaining = parts.slice(0, parts.length - 2);
  let namespace = "";
  let name = "";
  if (remaining.length > 0 && remaining[0] === "") {
    namespace = "";
    name = remaining.slice(1).join("_");
  } else if (remaining.length > 0) {
    namespace = remaining[0];
    name = remaining.slice(1).join("_");
  }
  return { namespace, name, apiGroup, kind };
}

function buildKustomizationNode(ks: any): FluxTreeNode {
  const name = ks.metadata?.name || "unknown";
  const conditions = ks.status?.conditions || [];
  const readyCond = conditions.find((c: any) => c.type === "Ready");
  const ready = readyCond?.status === "True";

  return {
    id: `ks-${ks.metadata?.uid || name}`,
    name,
    kind: "Kustomization",
    path: ks.spec?.path || "./",
    namespace: ks.metadata?.namespace || FLUX_NAMESPACE,
    ready,
    status: readyCond?.message || (ready ? "Ready" : "Not Ready"),
    lastSync: ks.status?.lastHandledReconcileAt || null,
    revision: ks.status?.lastAppliedRevision || null,
    children: [],
  };
}

function buildHelmReleaseNode(hr: any): FluxTreeNode {
  const name = hr.metadata?.name || "unknown";
  const conditions = hr.status?.conditions || [];
  const readyCond = conditions.find((c: any) => c.type === "Ready");
  const ready = readyCond?.status === "True";

  return {
    id: `hr-${hr.metadata?.uid || name}`,
    name,
    kind: "HelmRelease",
    path: hr.spec?.chart?.spec?.chart || "",
    namespace: hr.metadata?.namespace || "default",
    ready,
    status: readyCond?.message || (ready ? "Ready" : "Not Ready"),
    lastSync: hr.status?.lastHandledReconcileAt || null,
    revision: hr.status?.lastAppliedRevision || null,
    children: [],
  };
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
        namespace: "",
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

  // 5. Create Kustomization CRD (no targetNamespace — charts bring their own namespaces)
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
      namespace: "",
      lastSync: null,
    } as GitRepoRecord,
  };
}

export async function removeRepo(
  id: string,
  repoName?: string,
  repoNamespace?: string,
): Promise<{ success: boolean; deleteId?: string; error?: string }> {
  let name: string;
  let ns: string;
  let dbId: string | null = null;

  // Try Prisma first — repos added via dashboard have a DB record
  const repo = await prisma.gitRepo.findUnique({ where: { id } });
  if (repo) {
    name = repo.name;
    ns = repo.namespace || repo.name;
    dbId = id;
  } else if (repoName) {
    // CRD-only repo (exists in cluster but not in our DB) — delete by name/namespace
    name = repoName;
    ns = repoNamespace || name;
  } else {
    return { success: false, error: "Repository not found" };
  }

  const deleteId = dbId || `gr-${name}`;

  const steps = dbId
    ? [
        { step: "discover", status: "pending" as const, detail: "Discovering child resources…" },
        { step: "children", status: "pending" as const, detail: "Deleting child Kustomizations & HelmReleases…" },
        { step: "flux_crds", status: "pending" as const, detail: "Suspending GitRepository & deleting Kustomization…" },
        { step: "namespace", status: "pending" as const, detail: `Deleting namespace "${ns}"…` },
        { step: "volumes", status: "pending" as const, detail: "Cleaning up persistent volumes…" },
        { step: "db", status: "pending" as const, detail: "Removing from database…" },
      ]
    : [
        { step: "discover", status: "pending" as const, detail: "Discovering child resources…" },
        { step: "children", status: "pending" as const, detail: "Deleting child Kustomizations & HelmReleases…" },
        { step: "flux_crds", status: "pending" as const, detail: "Suspending GitRepository & deleting Kustomization…" },
        { step: "namespace", status: "pending" as const, detail: `Deleting namespace "${ns}"…` },
        { step: "volumes", status: "pending" as const, detail: "Cleaning up persistent volumes…" },
      ];

  const progress: DeleteProgress = {
    deleteId,
    repoName: name,
    namespace: ns,
    steps,
    done: false,
  };

  deleteProgressMap.set(deleteId, progress);
  scheduleProgressCleanup(deleteId);

  // Run async — don't await, let it complete in the background
  performCascadeDelete(deleteId, name, ns, dbId).catch((err) => {
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
  dbId: string | null,
) {
  const progress = deleteProgressMap.get(deleteId);
  if (!progress) return;

  // --- Step 0: Discover all child resources linked to this repo ---
  progress.steps[0].status = "running";
  const childKustomizations: { name: string; ns: string }[] = [];
  const childHelmReleases: { name: string; ns: string }[] = [];

  try {
    const kustRaw = await kubectlJSON("u1", `--all-namespaces get kustomizations`);
    const kustItems = (kustRaw?.items || []) as any[];
    for (const ks of kustItems) {
      const sourceName = ks.spec?.sourceRef?.name;
      // Child if sourceRef.name matches our repo AND the Kustomization itself isn't named the same
      // (the same-name one is the bootstrap kustomization we already handle)
      if (sourceName === name && ks.metadata?.name !== name) {
        childKustomizations.push({ name: ks.metadata.name, ns: ks.metadata.namespace || "flux-system" });
      }
    }
  } catch { /* proceed with what we have */ }

  try {
    const hrRaw = await kubectlJSON("u1", `--all-namespaces get helmreleases`);
    const hrItems = (hrRaw?.items || []) as any[];
    for (const hr of hrItems) {
      const sourceName = hr.spec?.chart?.spec?.sourceRef?.name;
      if (sourceName === name) {
        childHelmReleases.push({ name: hr.metadata.name, ns: hr.metadata.namespace || "default" });
      }
    }
  } catch { /* proceed */ }

  const totalChildren = childKustomizations.length + childHelmReleases.length;
  progress.steps[0].status = "done";
  progress.steps[0].detail = totalChildren > 0
    ? `Found ${childKustomizations.length} Kustomization(s), ${childHelmReleases.length} HelmRelease(s)`
    : "No child resources found";

  // --- Step 1: Delete child resources ---
  progress.steps[1].status = "running";
  let deletedChildren = 0;

  // Delete child Kustomizations first (so their managed resources start terminating)
  for (const child of childKustomizations) {
    try {
      await kubectlExec(`--namespace ${child.ns} delete kustomization ${child.name} --wait=false --ignore-not-found`);
      deletedChildren++;
      progress.steps[1].detail = `Deleted Kustomization "${child.name}" (${deletedChildren}/${totalChildren})…`;
    } catch (err) {
      progress.steps[1].detail = `Warning: failed to delete Kustomization "${child.name}": ${String(err)}`;
    }
  }

  // Delete child HelmReleases
  for (const child of childHelmReleases) {
    try {
      await kubectlExec(`--namespace ${child.ns} delete helmrelease ${child.name} --wait=false --ignore-not-found`);
      deletedChildren++;
      progress.steps[1].detail = `Deleted HelmRelease "${child.name}" (${deletedChildren}/${totalChildren})…`;
    } catch (err) {
      progress.steps[1].detail = `Warning: failed to delete HelmRelease "${child.name}": ${String(err)}`;
    }
  }

  progress.steps[1].status = "done";
  progress.steps[1].detail = totalChildren > 0
    ? `Deleted ${deletedChildren}/${totalChildren} child resources`
    : "No child resources to delete";

  // Give child resources a moment to start terminating before we delete the parent
  if (totalChildren > 0) {
    await new Promise((r) => setTimeout(r, 2000));
  }

  // --- Step 2: Suspend GitRepository, delete Kustomization ---
  // The GitRepository YAML lives in the parent Kustomization's git source (e.g. branconet-charts).
  // If we delete the GitRepository, the parent Kustomization immediately recreates it unsuspended.
  // Instead, we permanently suspend the GitRepository (stops fetching) and only delete the Kustomization.
  progress.steps[2].status = "running";

  // 2a. Suspend GitRepository FIRST — keep it suspended permanently.
  //     The parent Kustomization will NOT unsuspend a suspended resource on reconcile.
  let gitrepoSuspended = false;
  try {
    await kubectlExec(
      `--namespace ${FLUX_NAMESPACE} patch gitrepository ${name} --type merge -p {\"spec\":{\"suspend\":true}}`,
    );
    gitrepoSuspended = true;
    progress.steps[2].detail = `Suspended GitRepository "${name}" (kept in cluster to prevent recreation)…`;
  } catch { /* may not exist */ }

  // 2b. Suspend Kustomization so it stops reconciling before deletion
  try {
    await kubectlExec(
      `--namespace ${FLUX_NAMESPACE} patch kustomization ${name} --type merge -p {\"spec\":{\"suspend\":true}}`,
    );
    progress.steps[2].detail = `Suspended Kustomization "${name}"…`;
  } catch { /* may not exist */ }

  // Brief pause to let controllers register the suspension
  await new Promise((r) => setTimeout(r, 1000));

  // 2c. Delete the Kustomization — it won't be recreated (its YAML is NOT in the parent's git path)
  try { await kubectlExec(`--namespace ${FLUX_NAMESPACE} delete kustomization ${name} --wait=false --ignore-not-found`); } catch {}

  // 2d. Do NOT delete the GitRepository — parent Kustomization would recreate it unsuspended.
  //     The suspended GitRepository stays in the cluster, inert, and won't show in the dashboard.
  if (gitrepoSuspended) {
    progress.steps[2].detail = `GitRepository "${name}" suspended (inert), Kustomization deleted`;
  } else {
    progress.steps[2].detail = `Delete attempted — GitRepository may not exist`;
  }

  // 2e. Clean up associated secret if present
  try { await kubectlExec(`--namespace ${FLUX_NAMESPACE} delete secret ${name}-auth --wait=false --ignore-not-found`); } catch {}
  progress.steps[2].status = "done";

  // --- Step 3: Delete namespace with polling ---
  // Never delete system/critical namespaces — repos that live there share the space
  const PROTECTED_NAMESPACES = new Set([
    "flux-system", "kube-system", "kube-public", "kube-node-lease",
    "default", "cert-manager", "ingress-nginx", "metallb-system",
  ]);

  const boundPVs: string[] = [];

  if (PROTECTED_NAMESPACES.has(namespace)) {
    progress.steps[3].status = "done";
    progress.steps[3].detail = `Skipped — "${namespace}" is a protected namespace`;
  } else {
    progress.steps[3].status = "running";

    // Capture PV names bound to PVCs in this namespace BEFORE deletion
    const pvOutput = await kubectlExec(
      `get pvc -n ${namespace} -o custom-columns=PV:.spec.volumeName --no-headers`,
    );
    if (pvOutput) {
      boundPVs.push(
        ...pvOutput.trim().split("\n").map((l) => l.trim()).filter(Boolean),
      );
    }

    const deleteResult = await kubectlExec(`delete namespace ${namespace} --wait=false --ignore-not-found`);

    if (deleteResult === null) {
      const stillThere = await kubectlExec(`get namespace ${namespace} --no-headers`);
      if (stillThere && stillThere.trim()) {
        progress.steps[3].status = "error";
        progress.steps[3].detail = `Failed to issue delete for namespace "${namespace}"`;
      } else {
        progress.steps[3].status = "done";
        progress.steps[3].detail = `Namespace "${namespace}" already gone`;
      }
    } else {
      let deleted = false;
      for (let i = 0; i < 24; i++) {
        await new Promise((r) => setTimeout(r, 2500));

        const nsCheck = await kubectlExec(`get namespace ${namespace} --no-headers`);
        if (!nsCheck || !nsCheck.trim()) {
          progress.steps[3].status = "done";
          progress.steps[3].detail = `Namespace "${namespace}" deleted`;
          deleted = true;
          break;
        }

        const pods = await kubectlExec(`get pods -n ${namespace} --no-headers`);
        const podCount = pods ? pods.trim().split("\n").filter(Boolean).length : 0;
        if (podCount > 0) {
          progress.steps[3].detail = `Terminating: ${podCount} pod${podCount !== 1 ? "s" : ""} remaining…`;
        } else {
          progress.steps[3].detail = "Waiting for namespace cleanup…";
        }
      }

      if (!deleted) {
        // Force cleanup: remove finalizers, force-delete all pods, then retry
        try {
          progress.steps[3].detail = "Force-clearing finalizers…";
          await kubectlExec(
            `get namespace ${namespace} -o json | ` +
            `python3 -c "import sys,json; d=json.load(sys.stdin); d['spec']['finalizers']=[]; json.dump(d,sys.stdout)" | ` +
            `kubectl replace --raw "/api/v1/namespaces/${namespace}/finalize" -f -`,
          );
          // Force-delete any remaining pods
          await kubectlExec(`delete pods --all -n ${namespace} --force --grace-period=0 --ignore-not-found`);
        } catch { /* best effort */ }

        // Quick final check
        const nsCheck = await kubectlExec(`get namespace ${namespace} --no-headers`);
        if (!nsCheck || !nsCheck.trim()) {
          progress.steps[3].status = "done";
          progress.steps[3].detail = `Namespace "${namespace}" deleted (forced)`;
        } else {
          progress.steps[3].status = "error";
          progress.steps[3].detail = `Could not delete namespace "${namespace}" — may need manual cleanup`;
        }
      }
    }
  }

  // --- Step 4: Clean up orphaned PersistentVolumes ---
  progress.steps[4].status = "running";
  if (boundPVs.length > 0) {
    const pvList = boundPVs.join(" ");
    try {
      await kubectlExec(`delete pv ${pvList} --force --grace-period=0 --ignore-not-found`);
      progress.steps[4].status = "done";
      progress.steps[4].detail = `Deleted ${boundPVs.length} volume${boundPVs.length !== 1 ? "s" : ""}: ${boundPVs.join(", ")}`;
    } catch (err) {
      progress.steps[4].status = "error";
      progress.steps[4].detail = `Failed to delete volumes: ${String(err)}`;
    }
  } else {
    progress.steps[4].status = "done";
    progress.steps[4].detail = "No bound volumes to clean up";
  }

  // --- Step 5 (only if DB record exists): Delete from Prisma ---
  if (dbId && progress.steps[5]) {
    progress.steps[5].status = "running";
    try {
      await prisma.gitRepo.delete({ where: { id: dbId } });
      progress.steps[5].status = "done";
    } catch (err) {
      progress.steps[5].status = "error";
      progress.steps[5].detail = String(err);
    }
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
