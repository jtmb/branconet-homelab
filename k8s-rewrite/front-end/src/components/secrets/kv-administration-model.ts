/** Browser-only administration contracts. Never import the server/native engine here. */
export const ADMIN_ACTIONS = [
  "list",
  "read",
  "create",
  "update",
  "delete",
  "rollback",
  "reconcile",
  "destroy",
  "export",
  "rotate",
] as const;
export type AdminAction = (typeof ADMIN_ACTIONS)[number];
export type AdminSession = {
  authenticated: boolean;
  username?: string;
  role?: string;
  engineAdmin?: boolean;
};
export type Page<T> = { items: T[]; nextCursor: string | null };
export type Policy = {
  id: string;
  revision: number;
  principal: string;
  mountId: string | null;
  prefix: string;
  effect: "allow" | "deny";
  actions: AdminAction[];
};
export type PolicyFields = Omit<Policy, "id" | "revision">;
export type Identity = {
  id: string;
  ownerId: string;
  name: string;
  expiresAt: string;
  revokedAt: string | null;
  createdAt: string;
};
export type IdentityScope = {
  mountId: string;
  prefix: string;
  actions: AdminAction[];
};
export type Grant = {
  id: string;
  pathId: string;
  alias: string;
  namespace: string;
  name: string;
  key: string;
};
export type LegacyPrincipal = {
  id: string;
  revision: number;
  enabled: boolean;
  grantCount: number;
};
export type ImpactRow = {
  alias: string;
  namespace: string;
  name: string;
  key: string;
  pathId: string | null;
  path: string | null;
  pathRevision: number | null;
  mountRevision: number | null;
  beforeAllowed: boolean;
  afterAllowed: boolean;
  basis: string;
};
export type ImpactPage = Page<ImpactRow> & {
  required: boolean;
  fingerprint: string | null;
  revision?: number;
  affectedAliasCount: number;
  nonsecretConfigurationAffected?: boolean;
  boundary?: string;
};
export type ImpactSnapshot = {
  page: ImpactPage;
  aliases: string[];
  cursors: string[];
  complete: boolean;
};
export type Audit = {
  id: string;
  actorId: string;
  operationId: string | null;
  pathId: string | null;
  mountId: string | null;
  path: string | null;
  namespace: string | null;
  name: string | null;
  principal: string | null;
  alias: string | null;
  key: string | null;
  action: string;
  previousVersion: number | null;
  newVersion: number | null;
  outcome: string;
  createdAt: string;
};
export type PathMetadata = {
  id: string;
  mountId: string;
  path: string;
  namespace: string;
  name: string;
  revision: number;
  retention: number;
  fields: { field: string; key: string }[];
};
export type NativeStatus = {
  pathId: string;
  uid: string;
  resourceVersion: string;
  head: number;
  adopted: boolean;
  tombstone: boolean;
  versions: number;
  guardedAdoption: boolean;
};
export type Capabilities = {
  pathId: string;
  revision: number;
  nativeMutationEnabled: boolean;
  permissions: Partial<Record<AdminAction, boolean>>;
};
export type Versions = {
  pathId: string;
  uid: string;
  resourceVersion: string;
  head: number;
  items: { version: number; name: string; uid: string; createdAt: string; tombstone: boolean }[];
};
export type PathSnapshot = {
  path: PathMetadata;
  status: NativeStatus;
  capabilities: Capabilities;
  versions: Versions;
};
export type HistoryCandidate = {
  name: string;
  uid: string;
  resourceVersion: string;
};
export type GcPreview = {
  pathId: string;
  pathRevision: number;
  resourceVersion: string;
  expectedHead: number;
  minimumAgeHours: number;
  eligible: number;
  retained: number;
  complete: boolean;
  items: HistoryCandidate[];
};
export type CleanupResult = {
  operationId: string;
  outcome: string;
  head: number;
  resourceVersion: string;
  cleanupComplete: boolean;
  cleanup: {
    version?: number;
    name: string;
    outcome: string;
    status: number;
  }[];
};
export type Operation = {
  id: string;
  pathId: string;
  path: string;
  namespace: string;
  name: string;
  action: string;
  previousVersion: number | null;
  newVersion: number | null;
  outcome: string;
};
export type Rotation = {
  id: string;
  pathId: string;
  field: string;
  revision: number;
  state: string;
  operationId: string | null;
  consumerKind: string;
  consumerNamespace: string;
  consumerName: string;
  consumerUid: string | null;
  consumerResourceVersion: string | null;
};
export type ConsumerPreview = {
  rotationId: string;
  revision: number;
  consumer: string;
  uid: string;
  resourceVersion: string;
  rotationIdMarker?: string;
};

export const isUuid = (value: string) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
export const isAdmin = (session: AdminSession | null) =>
  session?.authenticated === true &&
  session.role === "write" &&
  session.engineAdmin === true;
export function canAct(
  snapshot: PathSnapshot | null,
  action: AdminAction,
  native = true,
) {
  return (
    !!snapshot &&
    snapshot.capabilities.revision === snapshot.path.revision &&
    snapshot.capabilities.permissions[action] === true &&
    (!native || snapshot.capabilities.nativeMutationEnabled)
  );
}
export const consumerTarget = (row: Rotation) =>
  `${row.consumerNamespace}/${row.consumerKind}/${row.consumerName}`;
export const pathConfirmation = (snapshot: PathSnapshot) =>
  `${snapshot.path.id} ${snapshot.path.namespace}/${snapshot.path.name} ${snapshot.path.path} revision=${snapshot.path.revision} head=${snapshot.status.head} uid=${snapshot.status.uid} rv=${snapshot.status.resourceVersion}`;
export const policyConfirmation = (policy: Policy | PolicyFields) =>
  "id" in policy
    ? `policy ${policy.id} revision=${policy.revision}`
    : `create ${policy.principal} ${policy.mountId ?? "all-mounts"}/${policy.prefix || "(root)"} ${policy.effect} ${policy.actions.join(",")}`;
export const identityConfirmation = (identity: Identity) =>
  `revoke ${identity.id} owner=${identity.ownerId} expires=${identity.expiresAt}`;
export const historyConfirmation = (row: HistoryCandidate) =>
  `${row.name} uid=${row.uid} rv=${row.resourceVersion}`;

export function appendImpact(
  previous: ImpactSnapshot | null,
  page: ImpactPage,
): ImpactSnapshot {
  if (
    page.items.length > 100 ||
    page.affectedAliasCount > 10000 ||
    page.items.some((row) => typeof row.alias !== "string")
  )
    throw new AdminInputError("Invalid impact page; start a fresh preview.");
  if (
    previous &&
    (previous.complete ||
      page.fingerprint !== previous.page.fingerprint ||
      page.affectedAliasCount !== previous.page.affectedAliasCount ||
      page.revision !== previous.page.revision ||
      page.nonsecretConfigurationAffected !==
        previous.page.nonsecretConfigurationAffected)
  )
    throw new AdminInputError(
      "Impact metadata changed; start a fresh preview.",
    );
  const aliases = [
    ...(previous?.aliases ?? []),
    ...page.items.map((row) => row.alias),
  ];
  const cursors = [...(previous?.cursors ?? [])];
  if (
    new Set(aliases).size !== aliases.length ||
    (page.nextCursor && cursors.includes(page.nextCursor)) ||
    aliases.length > page.affectedAliasCount
  )
    throw new AdminInputError("Impact paging changed; start a fresh preview.");
  if (page.nextCursor) cursors.push(page.nextCursor);
  const complete =
    page.nextCursor === null && aliases.length === page.affectedAliasCount;
  if (page.nextCursor === null && !complete)
    throw new AdminInputError(
      "Incomplete impact preview; start a fresh preview.",
    );
  return { page, aliases, cursors, complete };
}
export function impactAcknowledgement(
  snapshot: ImpactSnapshot | null,
  aliasesChecked: boolean,
  configurationChecked: boolean,
) {
  if (!snapshot) throw new AdminInputError("Preview the access impact first.");
  if (!snapshot.page.required) return undefined;
  if (
    !snapshot.complete ||
    !aliasesChecked ||
    (snapshot.page.nonsecretConfigurationAffected && !configurationChecked) ||
    !snapshot.page.fingerprint
  )
    throw new AdminInputError(
      "Review every impact page and acknowledge aliases and configuration before committing.",
    );
  return {
    fingerprint: snapshot.page.fingerprint,
    aliases: [...snapshot.aliases],
    confirmLegacyImpact: true as const,
    ...(snapshot.page.nonsecretConfigurationAffected
      ? { confirmConfigurationImpact: true as const }
      : {}),
  };
}

export function destroyBody(
  snapshot: PathSnapshot,
  versions: number[],
  confirmation: string,
) {
  if (
    confirmation !== pathConfirmation(snapshot) ||
    !canAct(snapshot, "destroy") ||
    !snapshot.status.uid ||
    snapshot.versions.uid !== snapshot.status.uid ||
    snapshot.versions.resourceVersion !== snapshot.status.resourceVersion ||
    snapshot.versions.head !== snapshot.status.head ||
    !versions.length ||
    versions.length > 100 ||
    new Set(versions).size !== versions.length ||
    versions.some(
      (version) =>
        !snapshot.versions.items.some((row) => row.version === version && row.name && row.uid),
    )
  )
    throw new AdminInputError(
      "Confirm the captured target and select committed versions.",
    );
  if (versions.includes(snapshot.status.head) && !snapshot.status.tombstone)
    throw new AdminInputError(
      "Tombstone the active path before destroying its head.",
    );
  return {
    versions,
    sourceUid: snapshot.status.uid,
    histories: versions.map(version => {
      const row = snapshot.versions.items.find(item => item.version === version)!;
      return { version, name: row.name, uid: row.uid };
    }),
    confirmPath: snapshot.path.path,
    pathRevision: snapshot.path.revision,
    resourceVersion: snapshot.status.resourceVersion,
    expectedHead: snapshot.status.head,
  };
}
export function gcBody(
  snapshot: PathSnapshot,
  preview: GcPreview,
  histories: HistoryCandidate[],
  confirmation: string,
) {
  if (
    confirmation !== pathConfirmation(snapshot) ||
    !canAct(snapshot, "destroy") ||
    preview.pathId !== snapshot.path.id ||
    preview.pathRevision !== snapshot.path.revision ||
    preview.expectedHead !== snapshot.status.head ||
    preview.resourceVersion !== snapshot.status.resourceVersion ||
    preview.minimumAgeHours < 24 ||
    !histories.length ||
    histories.length > 100 ||
    new Set(histories.map((row) => row.name)).size !== histories.length ||
    histories.some(
      (row) =>
        !preview.items.some(
          (item) => historyConfirmation(item) === historyConfirmation(row),
        ),
    )
  )
    throw new AdminInputError(
      "Cleanup preview or target changed; capture fresh metadata.",
    );
  return {
    pathId: snapshot.path.id,
    pathRevision: preview.pathRevision,
    histories,
    confirmPath: snapshot.path.path,
    resourceVersion: preview.resourceVersion,
    expectedHead: preview.expectedHead,
  };
}

/** Fixed local validation messages only; never construct this from server/transport text. */
export class AdminInputError extends Error {}
export class AdminFailure extends Error {
  constructor(
    readonly status: number,
    readonly operationId?: string,
    readonly outcome?: string,
  ) {
    super(
      status === 409
        ? "Captured metadata is stale or native state conflicts. Refresh and confirm again; no retry was sent."
        : status === 401 || status === 403
          ? "Fresh authorization denied this request. Sensitive state was cleared."
          : status === 428
            ? "A fresh captured revision or complete impact acknowledgement is required."
            : `Request failed (${status}). Inspect metadata before any new action.`,
    );
  }
}
export class AdminCancelled extends Error {
  constructor() {
    super(
      "Request cancelled. Already sent changes may require metadata inspection.",
    );
  }
}

/** Ephemeral request scope. Closing/navigation invalidates late replies even if fetch ignores abort. */
export class AdministrationClient {
  private epoch = 0;
  private controllers = new Set<AbortController>();
  constructor(
    private readonly fetcher: typeof fetch = fetch,
    private readonly authorizationLost: () => void = () => {},
    private readonly timeoutMs = 45000,
  ) {}
  invalidate() {
    this.epoch++;
    this.controllers.forEach((controller) => controller.abort());
    this.controllers.clear();
  }
  async run<T>(
    work: (
      request: <R>(url: string, method?: string, body?: unknown) => Promise<R>,
      session: AdminSession,
    ) => Promise<T>,
    admin = true,
  ): Promise<T> {
    const epoch = this.epoch,
      controller = new AbortController();
    this.controllers.add(controller);
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    const check = () => {
      if (epoch !== this.epoch) throw new AdminCancelled();
      if (controller.signal.aborted) throw new AdminFailure(408);
    };
    const request = async <R>(
      url: string,
      method = "GET",
      body?: unknown,
    ): Promise<R> => {
      check();
      if (!url.startsWith("/api/kv/") && url !== "/api/auth/session")
        throw new Error(
          "Administration requests require an explicit engine route.",
        );
      const response = await this.fetcher.call(globalThis, url, {
        method,
        signal: controller.signal,
        cache: "no-store",
        credentials: "same-origin",
        redirect: "error",
        headers:
          body === undefined
            ? undefined
            : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      check();
      // Authorization withdrawal must clear private UI state even when a proxy
      // returns an empty, malformed or unreadable denial body.
      if (response.status === 401 || response.status === 403) {
        this.authorizationLost();
        void response.body?.cancel().catch(() => {});
        throw new AdminFailure(response.status);
      }
      const reader = response.body?.getReader(),
        chunks: Uint8Array[] = [];
      let bytes = 0;
      if (reader) {
        try {
          while (true) {
            const chunk = await reader.read();
            check();
            if (chunk.done) break;
            bytes += chunk.value.byteLength;
            if (bytes > 1024 * 1024) {
              await reader.cancel();
              throw new Error("Administration response exceeds its bound.");
            }
            chunks.push(chunk.value);
          }
        } finally {
          reader.releaseLock();
        }
      }
      let data: Record<string, unknown>;
      try {
        const joined = new Uint8Array(bytes);
        let offset = 0;
        for (const chunk of chunks) {
          joined.set(chunk, offset);
          offset += chunk.byteLength;
        }
        data = JSON.parse(
          new TextDecoder("utf-8", { fatal: true }).decode(joined),
        );
        if (!data || typeof data !== "object") throw new Error();
      } catch {
        throw new Error("Invalid administration response.");
      }
      check();
      if (!response.ok) {
        throw new AdminFailure(
          response.status,
          typeof data.operationId === "string" && isUuid(data.operationId)
            ? data.operationId
            : undefined,
          typeof data.outcome === "string" &&
          [
            "committed",
            "conflict",
            "ambiguous",
            "pending",
            "recovery-required",
          ].includes(data.outcome)
            ? data.outcome
            : undefined,
        );
      }
      return data as R;
    };
    try {
      const session = await request<AdminSession>("/api/auth/session");
      if (
        !session.authenticated ||
        typeof session.username !== "string" ||
        !session.username ||
        (admin && !isAdmin(session))
      ) {
        this.authorizationLost();
        throw new AdminFailure(session.authenticated ? 403 : 401);
      }
      const result = await work(request, session);
      check();
      // In particular, an issued token never reaches UI after demotion/logout/account change.
      const fresh = await request<AdminSession>("/api/auth/session");
      if (
        !fresh.authenticated ||
        fresh.username !== session.username ||
        fresh.role !== session.role ||
        fresh.engineAdmin !== session.engineAdmin ||
        (admin && !isAdmin(fresh))
      ) {
        this.authorizationLost();
        throw new AdminFailure(403);
      }
      return result;
    } catch (error) {
      check();
      if (
        error instanceof AdminFailure ||
        error instanceof AdminCancelled ||
        error instanceof AdminInputError
      )
        throw error;
      // Never reflect a transport exception/body which might contain credentials.
      throw new Error(
        "Request outcome unavailable. Inspect metadata before another action; no retry was sent.",
      );
    } finally {
      clearTimeout(timer);
      this.controllers.delete(controller);
    }
  }
}
