import { kubectlJSON as rawKubectlJSON, kubectlExec, validateNamespace, validateResourceName, KubernetesCommandError } from "./k8s";
import { createSecretTransport, secretNamespaces } from "./secret-client";
import { SecretError, secretFailure, validateTarget } from "./cluster-secrets";
import prisma from "./db";
import { dumpYaml } from "@kubernetes/client-node";
import { writeFile, unlink } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";
import { randomUUID } from "crypto";
import { repositoryUrl, publicRepositoryUrl, fluxReadiness, publicFluxConditions, requireCompleteFluxList } from "./flux-input";
import { publicClusterMetadata } from "./cluster-metadata";

async function kubectlJSON(args: readonly string[], timeout = 15000): Promise<any> {
  const value = await rawKubectlJSON(args, timeout);
  const get = args.indexOf("get");
  if (get >= 0 && ["gitrepositories", "kustomizations", "helmreleases"].includes(args[get + 1])) requireCompleteFluxList(value);
  return publicClusterMetadata(value);
}

const FLUX_NAMESPACE = "flux-system";

// =============================================================================
// Helpers
// =============================================================================

function buildKubectlCmd(args: readonly string[]): string[] {
  return ["--namespace", FLUX_NAMESPACE, ...args];
}

async function ignoringMissing(operation: () => Promise<unknown>): Promise<boolean> {
  try { await operation(); return true; }
  catch (error) {
    if (error instanceof KubernetesCommandError && error.status === 404) return false;
    throw error;
  }
}

async function namespaceExists(namespace: string): Promise<boolean> {
  return ignoringMissing(() => kubectlExec(["get", "namespace", validateNamespace(namespace), "-o", "name"]));
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

// Keep active admission/progress intact; only completed entries are eligible for cleanup.
function scheduleProgressCleanup(id: string) {
  setTimeout(() => {
    const progress = deleteProgressMap.get(id);
    if (progress && !progress.done) scheduleProgressCleanup(id);
    else deleteProgressMap.delete(id);
  }, 5 * 60 * 1000);
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
    metadata: { name: validateResourceName(name), namespace: FLUX_NAMESPACE },
    spec: {
      interval,
      url: repositoryUrl(url),
      ref: { branch },
    },
  };

  if (secretRef) {
    resource.spec.secretRef = { name: validateResourceName(secretRef) };
  }

  const yaml = dumpYaml(resource);
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
    metadata: { name: validateResourceName(name), namespace: FLUX_NAMESPACE },
    spec: {
      interval,
      path,
      prune,
      sourceRef: {
        kind: "GitRepository",
        name: validateResourceName(sourceName),
      },
    },
  };

  if (targetNamespace) {
    resource.spec.targetNamespace = validateNamespace(targetNamespace);
  }

  const yaml = dumpYaml(resource);
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
  try {
    const secretName = `${name}-auth`;
    validateTarget({ namespace: FLUX_NAMESPACE, name: secretName, key: "identity" });
    if (!secretNamespaces().includes(FLUX_NAMESPACE)) throw new SecretError(403, "flux-system is outside the Secret scope");
    const values = type === "ssh" ? { identity: credentials, known_hosts: await getGithubKnownHosts() } : { username: "git", password: credentials };
    await createSecretTransport().create(FLUX_NAMESPACE, {
      apiVersion: "v1", kind: "Secret", type: "Opaque", metadata: { namespace: FLUX_NAMESPACE, name: secretName },
      data: Object.fromEntries(Object.entries(values).map(([key, value]) => [key, Buffer.from(value!).toString("base64")])),
    });
    return { success: true };
  } catch (error) { return { success: false, error: secretFailure(error).message }; }
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
    kubectlJSON( buildKubectlCmd(["get", "gitrepositories", "-o", "json"])),
    kubectlJSON( buildKubectlCmd(["get", "kustomizations", "-o", "json"])),
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
    const combinedMessage = fluxReadiness(readyCond, ...(ks ? [ksReadyCond] : []));

    return {
      name,
      namespace: item.metadata?.namespace || FLUX_NAMESPACE,
      url: publicRepositoryUrl(item.spec?.url),
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

export async function triggerSync(name: string, expectedResourceVersion?: string): Promise<{ success: boolean; error?: string }> {
  if (expectedResourceVersion !== undefined && (!expectedResourceVersion || expectedResourceVersion.length > 1024 || expectedResourceVersion.includes("\0")))
    throw new KubernetesCommandError(400, "Invalid repository resource version");
  const cmd = ["annotate", "gitrepository", validateResourceName(name), `reconcile.fluxcd.io/requestedAt=${new Date().toISOString()}`, "--overwrite"];
  if (expectedResourceVersion !== undefined) cmd.push(`--resource-version=${expectedResourceVersion}`);
  const result = await kubectlJSON( buildKubectlCmd(cmd));
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
    kubectlJSON( buildKubectlCmd(["get", "gitrepositories", "-o", "json"])),
    kubectlJSON( buildKubectlCmd(["get", "kustomizations", "-o", "json"])),
    kubectlJSON( ["get", "helmreleases", "--all-namespaces", "-o", "json"]),
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

      children.push({
        id: `ks-${ks.metadata?.uid || ksName}`,
        name: ksName,
        kind: "Kustomization",
        path: ks.spec?.path || "./",
        namespace: ks.metadata?.namespace || FLUX_NAMESPACE,
        ready: ksReady,
        status: fluxReadiness(ksReadyCond),
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
      url: publicRepositoryUrl(gr.spec?.url),
      branch: gr.spec?.ref?.branch || "main",
      path: repoKS[0]?.spec?.path || "./",
      namespace: gr.metadata?.namespace || FLUX_NAMESPACE,
      ready: sourceReady,
      status: fluxReadiness(readyCond),
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
    status: fluxReadiness(readyCond),
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
    status: fluxReadiness(readyCond),
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
      url: publicRepositoryUrl(repo.url),
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
  authData?: string; // raw credential written only to native Secret
}): Promise<{ success: boolean; repo?: GitRepoRecord; error?: string }> {
  validateResourceName(data.name);
  const url = repositoryUrl(data.url);
  const branch = data.branch || "main";
  const path = data.path || "./";
  const authMethod = data.authMethod || "none";

  // Native values only: SQLite records references and public repository metadata.
  if (!["none", "ssh", "https"].includes(authMethod)) return { success: false, error: "Invalid repository authentication method" };
  if (authMethod !== "none" && !data.authData) return { success: false, error: "Repository credential is required" };

  // 2. Save to DB
  let repo;
  try {
    repo = await prisma.gitRepo.create({
      data: {
        name: data.name,
        url,
        branch,
        path,
        namespace: "",
        authMethod,
        authData: "",
      },
    });
  } catch (err: any) {
    if (err?.code === "P2002") {
      return { success: false, error: `Repository "${data.name}" already exists` };
    }
    return { success: false, error: "Failed to save repository metadata" };
  }

  // 3. Create K8s Secret if auth needed
  let secretRef: string | undefined;
  if (authMethod !== "none" && data.authData) {
    const secretResult = await createFluxSecret(data.name, authMethod as "ssh" | "https", data.authData);
    if (secretResult.success) {
      secretRef = `${data.name}-auth`;
    } else {
      await prisma.gitRepo.delete({ where: { id: repo.id } });
      return { success: false, error: `Failed to create auth secret: ${secretResult.error}` };
    }
  }

  // 4. Create GitRepository CRD
  const grResult = await createGitRepository(data.name, url, branch, path, secretRef);
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

  validateResourceName(name);
  validateNamespace(ns);
  const deleteId = dbId || `gr-${name}`;
  if (deleteProgressMap.get(deleteId)?.done === false || [...deleteProgressMap.values()].some(progress =>
    !progress.done && progress.repoName === name && progress.namespace === ns))
    throw new KubernetesCommandError(409, "Repository removal is already running");

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
      p.error = err instanceof KubernetesCommandError ? err.message : "Flux deletion failed";
      const active = p.steps.find(step => step.status === "running");
      if (active) { active.status = "error"; active.detail = p.error; }
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
    const kustRaw = await kubectlJSON( ["get", "kustomizations", "--all-namespaces"]);
    if (!kustRaw) throw new KubernetesCommandError(503, "Flux discovery unavailable");
    const kustItems = (kustRaw.items || []) as any[];
    for (const ks of kustItems) {
      const sourceName = ks.spec?.sourceRef?.name;
      // Child if sourceRef.name matches our repo AND the Kustomization itself isn't named the same
      // (the same-name one is the bootstrap kustomization we already handle)
      if (sourceName === name && ks.metadata?.name !== name) {
        childKustomizations.push({ name: ks.metadata.name, ns: ks.metadata.namespace || "flux-system" });
      }
    }
  } catch (error) { throw error; }

  try {
    const hrRaw = await kubectlJSON( ["get", "helmreleases", "--all-namespaces"]);
    if (!hrRaw) throw new KubernetesCommandError(503, "Flux discovery unavailable");
    const hrItems = (hrRaw.items || []) as any[];
    for (const hr of hrItems) {
      const sourceName = hr.spec?.chart?.spec?.sourceRef?.name;
      if (sourceName === name) {
        childHelmReleases.push({ name: hr.metadata.name, ns: hr.metadata.namespace || "default" });
      }
    }
  } catch (error) { throw error; }

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
      await kubectlExec(["--namespace", (validateNamespace(child.ns)), "delete", "kustomization", (validateResourceName(child.name)), "--wait=false", "--ignore-not-found"]);
      deletedChildren++;
      progress.steps[1].detail = `Deleted Kustomization "${child.name}" (${deletedChildren}/${totalChildren})…`;
    } catch (err) {
      throw err;
    }
  }

  // Delete child HelmReleases
  for (const child of childHelmReleases) {
    try {
      await kubectlExec(["--namespace", (validateNamespace(child.ns)), "delete", "helmrelease", (validateResourceName(child.name)), "--wait=false", "--ignore-not-found"]);
      deletedChildren++;
      progress.steps[1].detail = `Deleted HelmRelease "${child.name}" (${deletedChildren}/${totalChildren})…`;
    } catch (err) {
      throw err;
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
  const gitrepoSuspended = await ignoringMissing(() => kubectlExec(
    ["--namespace", FLUX_NAMESPACE, "patch", "gitrepository", validateResourceName(name), "--type", "merge", "-p", JSON.stringify({ spec: { suspend: true } })],
  ));
  if (gitrepoSuspended) {
    progress.steps[2].detail = `Suspended GitRepository "${name}" (kept in cluster to prevent recreation)…`;
  }

  // 2b. Suspend Kustomization so it stops reconciling before deletion
  await ignoringMissing(() => kubectlExec(
    ["--namespace", FLUX_NAMESPACE, "patch", "kustomization", validateResourceName(name), "--type", "merge", "-p", JSON.stringify({ spec: { suspend: true } })],
  ));

  // Brief pause to let controllers register the suspension
  await new Promise((r) => setTimeout(r, 1000));

  // 2c. Delete the Kustomization — it won't be recreated (its YAML is NOT in the parent's git path)
  await kubectlExec(["--namespace", FLUX_NAMESPACE, "delete", "kustomization", validateResourceName(name), "--wait=false", "--ignore-not-found"]);

  // 2d. Do NOT delete the GitRepository — parent Kustomization would recreate it unsuspended.
  //     The suspended GitRepository stays in the cluster, inert, and won't show in the dashboard.
  if (gitrepoSuspended) {
    progress.steps[2].detail = `GitRepository "${name}" suspended (inert), Kustomization deleted`;
  } else {
    progress.steps[2].detail = `Delete attempted — GitRepository may not exist`;
  }

  // Credentials have independent ownership/lifecycle. Never infer them from a repository name.
  // Current-namespace RBAC deliberately has no whole-Secret delete verb.
  progress.steps[2].detail += "; repository credentials retained for explicit native cleanup";
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
      ["get", "pvc", "-n", (validateNamespace(namespace)), "-o", "custom-columns=PV:.spec.volumeName", "--no-headers"],
    );
    if (pvOutput) {
      boundPVs.push(
        ...pvOutput.trim().split("\n").map((l) => l.trim()).filter(l => l && l !== "<none>"),
      );
    }

    await kubectlExec(["delete", "namespace", validateNamespace(namespace), "--wait=false", "--ignore-not-found"]);
    let deleted = false;
    for (let i = 0; i < 24; i++) {
      if (!await namespaceExists(namespace)) { deleted = true; break; }
      progress.steps[3].detail = `Waiting for namespace "${namespace}" cleanup…`;
      await new Promise((r) => setTimeout(r, 2500));
    }
    if (!deleted) throw new KubernetesCommandError(504, "Namespace cleanup timed out; inspect finalizers before retrying");
    progress.steps[3].status = "done";
    progress.steps[3].detail = `Namespace "${namespace}" deleted`;
  }

  // --- Step 4: Clean up orphaned PersistentVolumes ---
  progress.steps[4].status = "running";
  if (boundPVs.length > 0) {
    try {
      await kubectlExec(["delete", "pv", ...boundPVs.map(validateResourceName), "--force", "--grace-period=0", "--ignore-not-found"]);
      progress.steps[4].status = "done";
      progress.steps[4].detail = `Deleted ${boundPVs.length} volume${boundPVs.length !== 1 ? "s" : ""}: ${boundPVs.join(", ")}`;
    } catch (err) {
      throw err;
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
      throw err;
    }
  }

  progress.done = true;
}

export async function syncRepo(
  id: string,
  repoName?: string,
  namespace?: string,
): Promise<{ success: boolean; error?: string }> {
  if (namespace !== undefined && namespace !== FLUX_NAMESPACE)
    throw new KubernetesCommandError(400, "Repository reconciliation requires the Flux namespace");
  if (repoName !== undefined) validateResourceName(repoName);
  const repo = await prisma.gitRepo.findUnique({ where: { id } });
  if (repo) {
    if (repoName !== undefined && repoName !== repo.name)
      throw new KubernetesCommandError(409, "Repository identity changed. Refresh before reconciling");
    return triggerSync(repo.name);
  }
  if (!repoName || !id.startsWith("gr-")) return { success: false, error: "Repository not found" };
  const current = await kubectlJSON(buildKubectlCmd(["get", "gitrepository", repoName]));
  if (current?.kind !== "GitRepository" || current?.metadata?.name !== repoName || current?.metadata?.namespace !== FLUX_NAMESPACE
    || typeof current?.metadata?.uid !== "string" || !current.metadata.uid || typeof current?.metadata?.resourceVersion !== "string")
    throw new KubernetesCommandError(502, "Invalid repository identity response");
  if (id !== `gr-${current.metadata.uid}`)
    throw new KubernetesCommandError(409, "Repository identity changed. Refresh before reconciling");
  return triggerSync(repoName, current.metadata.resourceVersion);
}

// =============================================================================
// Detail queries — single repo / single kustomization drill-down
// =============================================================================

export interface GitRepoDetail {
  name: string;
  namespace: string;
  url: string;
  branch: string;
  path: string;
  ready: boolean;
  status: string;
  lastSync: string | null;
  revision: string | null;
  suspended: boolean;
  labels: { key: string; value: string }[];
  annotations: { key: string; value: string }[];
  age: string | null;
  conditions: { type: string; status: string; reason: string; message: string }[];
  bundles: BundleSummary[];
  totalResources: number;
  readyResources: number;
  events: { type: string; reason: string; message: string; lastTimestamp: string; age: string }[];
}

export interface BundleSummary {
  name: string;
  path: string;
  ready: boolean;
  status: string;
  lastSync: string | null;
  resourceCounts: { kind: string; count: number }[];
  totalResources: number;
}

export async function getGitRepoDetail(name: string): Promise<GitRepoDetail | null> {
  const repoRaw = await kubectlJSON(["get", "gitrepository", (validateResourceName(name)), "-n", (FLUX_NAMESPACE), "-o", "json"]);
  if (!repoRaw) return null;

  const conditions = publicFluxConditions(repoRaw.status?.conditions);
  const readyCond = conditions.find((c: any) => c.type === "Ready");
  const ready = readyCond?.status === "True";

  const labels = Object.entries(repoRaw.metadata?.labels || {}).map(
    ([k, v]) => ({ key: k, value: String(v) })
  );
  const annotations = Object.entries(repoRaw.metadata?.annotations || {}).map(
    ([k, v]) => ({ key: k, value: String(v) })
  );

  const creationTs = repoRaw.metadata?.creationTimestamp;
  const age = creationTs ? formatAge(Date.now() - new Date(creationTs).getTime()) : null;

  // Fetch Kustomizations that reference this repo
  const kustomizationsRaw = await kubectlJSON(["get", "kustomizations", "-n", (FLUX_NAMESPACE), "-o", "json"]);
  const kustomizations = (kustomizationsRaw?.items || []) as any[];
  const bundles: BundleSummary[] = [];
  let totalResources = 0;
  let readyResources = 0;

  for (const ks of kustomizations) {
    if (ks.spec?.sourceRef?.name !== name) continue;

    const ksName = ks.metadata?.name || "unknown";
    const ksConditions = publicFluxConditions(ks.status?.conditions);
    const ksReadyCond = ksConditions.find((c: any) => c.type === "Ready");
    const ksReady = ksReadyCond?.status === "True";

    // Parse inventory into kind counts
    const inventoryEntries: { id: string; v: string }[] = ks.status?.inventory?.entries || [];
    const kindCounts = new Map<string, number>();
    for (const entry of inventoryEntries) {
      const parsed = parseFluxInventoryId(entry.id);
      const kind = parsed.kind || "Unknown";
      kindCounts.set(kind, (kindCounts.get(kind) || 0) + 1);
    }
    const resourceCounts = Array.from(kindCounts.entries())
      .map(([kind, count]) => ({ kind, count }))
      .sort((a, b) => b.count - a.count);
    const bundleTotal = inventoryEntries.length;

    totalResources += bundleTotal;
    if (ksReady) readyResources += bundleTotal;

    bundles.push({
      name: ksName,
      path: ks.spec?.path || "./",
      ready: ksReady,
      status: fluxReadiness(ksReadyCond),
      lastSync: ks.status?.lastHandledReconcileAt || null,
      resourceCounts,
      totalResources: bundleTotal,
    });
  }

  // Events
  const events = await fetchFluxEvents(name, FLUX_NAMESPACE);

  return {
    name,
    namespace: repoRaw.metadata?.namespace || FLUX_NAMESPACE,
    url: publicRepositoryUrl(repoRaw.spec?.url),
    branch: repoRaw.spec?.ref?.branch || "main",
    path: bundles[0]?.path || "./",
    ready,
    status: fluxReadiness(readyCond),
    lastSync: repoRaw.status?.lastHandledReconcileAt || null,
    revision: repoRaw.status?.artifact?.revision || null,
    suspended: repoRaw.spec?.suspend === true,
    labels,
    annotations,
    age,
    conditions,
    bundles,
    totalResources,
    readyResources,
    events,
  };
}

export interface KustomizationDetail {
  name: string;
  namespace: string;
  path: string;
  sourceRef: { kind: string; name: string };
  ready: boolean;
  status: string;
  lastSync: string | null;
  revision: string | null;
  suspended: boolean;
  age: string | null;
  conditions: { type: string; status: string; reason: string; message: string }[];
  resources: { kind: string; name: string; namespace: string; apiGroup: string }[];
  events: { type: string; reason: string; message: string; lastTimestamp: string; age: string }[];
}

export async function getKustomizationDetail(name: string): Promise<KustomizationDetail | null> {
  const ksRaw = await kubectlJSON(["get", "kustomization", (validateResourceName(name)), "-n", (FLUX_NAMESPACE), "-o", "json"]);
  if (!ksRaw) return null;

  const conditions = publicFluxConditions(ksRaw.status?.conditions);
  const readyCond = conditions.find((c: any) => c.type === "Ready");
  const ready = readyCond?.status === "True";

  const creationTs = ksRaw.metadata?.creationTimestamp;
  const age = creationTs ? formatAge(Date.now() - new Date(creationTs).getTime()) : null;

  // Parse inventory entries
  const inventoryEntries: { id: string; v: string }[] = ksRaw.status?.inventory?.entries || [];
  const resources = inventoryEntries
    .map((entry) => {
      const parsed = parseFluxInventoryId(entry.id);
      return {
        kind: parsed.kind || "Unknown",
        name: parsed.name || "unknown",
        namespace: parsed.namespace || "default",
        apiGroup: parsed.apiGroup || "",
      };
    })
    .sort((a, b) => a.kind.localeCompare(b.kind) || a.name.localeCompare(b.name));

  // Events
  const events = await fetchFluxEvents(name, FLUX_NAMESPACE);

  return {
    name,
    namespace: ksRaw.metadata?.namespace || FLUX_NAMESPACE,
    path: ksRaw.spec?.path || "./",
    sourceRef: {
      kind: ksRaw.spec?.sourceRef?.kind || "GitRepository",
      name: ksRaw.spec?.sourceRef?.name || "unknown",
    },
    ready,
    status: fluxReadiness(readyCond),
    lastSync: ksRaw.status?.lastHandledReconcileAt || null,
    revision: ksRaw.status?.lastAppliedRevision || null,
    suspended: ksRaw.spec?.suspend === true,
    age,
    conditions,
    resources,
    events,
  };
}

async function fetchFluxEvents(
  resourceName: string,
  namespace: string,
): Promise<{ type: string; reason: string; message: string; lastTimestamp: string; age: string }[]> {
  const raw = await kubectlExec(
    ["get", "events", "-n", (validateNamespace(namespace)), "--field-selector", "involvedObject.name=" + (validateResourceName(resourceName)), "--sort-by=.lastTimestamp"],
  );
  if (!raw) return [];

  // Parse kubectl table output into structured events
  const lines = raw.trim().split("\n").slice(1); // skip header
  const events: { type: string; reason: string; message: string; lastTimestamp: string; age: string }[] = [];

  for (const line of lines) {
    const parts = line.trim().split(/\s{2,}/);
    if (parts.length >= 5) {
      const type = ["Normal", "Warning"].includes(parts[1]) ? parts[1] : "Unknown";
      const reason = "Controller event";
      let lastTimestamp = "";
      let age = "Unknown";
      try {
        const ts = new Date(parts[0]);
        if (!isNaN(ts.getTime())) {
          lastTimestamp = ts.toISOString();
          age = formatAge(Date.now() - ts.getTime());
        }
      } catch { /* Invalid producer timestamps are withheld. */ }
      const message = "Controller output withheld";
      events.push({ type, reason, message, lastTimestamp, age });
    }
  }

  return events;
}

function formatAge(ms: number): string {
  if (ms < 0) return "—";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 365) return `${d}d`;
  return `${Math.floor(d / 365)}y`;
}

async function kubectlApplyYaml(yaml: string): Promise<boolean> {
  const fileName = join(tmpdir(), `flux-${randomUUID()}.yaml`);
  try {
    await writeFile(fileName, yaml, { mode: 0o600 });
    await kubectlExec(["apply", "-f", fileName], 15000);
    return true;
  } finally {
    await unlink(fileName).catch(() => {});
  }
}
