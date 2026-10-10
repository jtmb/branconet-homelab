import type { Prisma, PrismaClient } from "@prisma/client";
import { KvError, KV_ACTIONS, fieldMapping, logicalPath, metadataRevision, policyAllows, parseActions, type KvAction, type KvActor, type KvConfig, type KvRule, type KvScope } from "./kv-contract";
import { hashMatches, issueCredential, presentedCredential } from "./kv-credentials";
import { validateTarget } from "./cluster-secrets";

type Client = Prisma.TransactionClient;
const identityMetadata = { id: true, ownerId: true, name: true, expiresAt: true, revokedAt: true, createdAt: true } as const;
export type RegisteredPath = Prisma.KvPathGetPayload<{ include: { fields: true; mount: true } }>;
export type PolicyInput = { principal: string; mountId: string | null; prefix: string; effect: "allow" | "deny"; actions: KvAction[] };
export type IdentityScope = { mountId: string; prefix: string; actions: KvAction[] };

export class KvRegistry {
  constructor(readonly db: PrismaClient, readonly namespaces: readonly string[], readonly config: KvConfig) {}

  async serialized<T>(operation: (tx: Client) => Promise<T>): Promise<T> {
    for (let attempt = 0; attempt < 4; attempt++) {
      try {
        return await this.db.$transaction(async tx => {
          await tx.accountLock.update({ where: { id: 1 }, data: { locked: 0 } });
          return operation(tx);
        }, { maxWait: 10000, timeout: 10000 });
      } catch (error) {
        if (error instanceof KvError) throw error;
        const code = (error as { code?: string }).code;
        if (code === "P2002") throw new KvError(409, "KV metadata or native key ownership already exists");
        if (!["P2034", "P2028", "P1008"].includes(code || "")) throw new KvError(503, "KV metadata unavailable");
        if (attempt === 3) throw new KvError(503, "KV metadata is busy; retry shortly");
        await new Promise(resolve => setTimeout(resolve, 25 * (attempt + 1)));
      }
    }
    throw new KvError(503, "KV metadata unavailable");
  }

  async current(actor: KvActor, client: Client = this.db) {
    const user = await client.user.findUnique({ where: { id: actor.id } });
    if (!user || user.sessionVersion !== actor.sessionVersion) throw new KvError(401, "Authentication required");
    if (actor.identityId) {
      const identity = await client.kvIdentity.findUnique({ where: { id: actor.identityId } });
      if (!identity || identity.ownerId !== user.id || identity.ownerSessionVersion !== user.sessionVersion ||
        identity.revokedAt || identity.expiresAt.getTime() <= Date.now() || user.role !== "write")
        throw new KvError(401, "KV identity revoked or expired");
    }
    return user;
  }

  async admin(actor: KvActor, client: Client = this.db) {
    const user = await this.current(actor, client);
    if (actor.identityId || user.role !== "write" || !user.engineAdmin) throw new KvError(403, "Engine administration required");
    return user;
  }

  async rules(principal: string, client: Client = this.db): Promise<KvRule[]> {
    const rules = await client.kvPolicy.findMany({ where: { principal }, take: 257 });
    if (rules.length > 256) throw new KvError(503, "KV policy metadata limit exceeded");
    for (const rule of rules) {
      try {
        parseActions(rule.actions); logicalPath(rule.prefix, true);
        if (!["allow", "deny"].includes(rule.effect)) throw new KvError(503, "KV policy metadata unavailable");
      } catch { throw new KvError(503, "KV policy metadata unavailable"); }
    }
    return rules;
  }

  async authorize(actor: KvActor, scope: KvScope, action: KvAction, client: Client = this.db) {
    const user = await this.current(actor, client);
    if (action !== "list" && user.role !== "write") throw new KvError(403, "KV values and changes require write access");
    const ownerRules = await this.rules(`user:${user.id}`, client);
    if (!policyAllows(ownerRules, scope, action) || (actor.identityId && !policyAllows(await this.rules(`identity:${actor.identityId}`, client), scope, action)))
      throw new KvError(403, "KV policy denies this action");
    return user;
  }

  async capabilities(actor: KvActor, id: string) {
    const path = await this.path(id), user = await this.authorize(actor, path, "list");
    const owner = await this.rules(`user:${user.id}`), identity = actor.identityId ? await this.rules(`identity:${actor.identityId}`) : null;
    const latest = await this.current(actor);
    if (latest.role !== user.role || latest.engineAdmin !== user.engineAdmin) throw new KvError(409, "KV permissions changed; refresh capabilities");
    const permissions = Object.fromEntries(KV_ACTIONS.map(action => [action,
      (action === "list" || user.role === "write") && policyAllows(owner, path, action) && (!identity || policyAllows(identity, path, action))]));
    return { pathId: id, revision: path.revision, permissions,
      nativeMutationEnabled: this.config.guardedAdoption,
      initializationAllowed: !!permissions.create && this.config.guardedAdoption && user.role === "write" && user.engineAdmin && !actor.identityId,
      supportedActions: ["list", "read", "create", "update", "delete", "rollback", "reconcile"],
      guardVerification: "operator assertion; external admission/RBAC evidence required" };
  }

  async listAudit(actor: KvActor, filters: { pathId?: string; operationId?: string; cursor?: string }) {
    const user = await this.current(actor);
    if (filters.pathId) { const path = await this.path(filters.pathId); await this.authorize(actor, path, "list"); }
    const admin = user.role === "write" && user.engineAdmin && !actor.identityId;
    const rules = admin ? null : await this.rules(`user:${actor.id}`), identity = actor.identityId ? await this.rules(`identity:${actor.identityId}`) : null;
    const grants = rules?.filter(rule => rule.effect === "allow" && parseActions(rule.actions).includes("list"));
    const rows = admin || grants?.length ? await this.db.kvAudit.findMany({ where: {
      ...(filters.cursor ? { id: { gt: filters.cursor } } : {}), ...(filters.pathId ? { pathId: filters.pathId } : {}), ...(filters.operationId ? { operationId: filters.operationId } : {}),
      ...(!admin ? { mountId: { not: null }, path: { not: null },
        ...(!grants!.some(rule => rule.mountId === null && rule.prefix === "") ? { OR: grants!.map(rule => ({ ...(rule.mountId ? { mountId: rule.mountId } : {}),
          ...(rule.prefix ? { OR: [{ path: rule.prefix }, { path: { startsWith: rule.prefix + "/" } }] } : {}) })) } : {}) } : {}),
    }, orderBy: { id: "asc" }, take: 101 }) : [];
    const latest = await this.current(actor);
    if (admin && (latest.role !== "write" || !latest.engineAdmin)) throw new KvError(403, "Engine administration revoked");
    const freshRules = admin ? null : await this.rules(`user:${actor.id}`), freshIdentity = identity ? await this.rules(`identity:${actor.identityId}`) : null;
    const permitted = (row: typeof rows[number]) => admin || !!row.mountId && !!row.path && policyAllows(freshRules!, { mountId: row.mountId, path: row.path }, "list") &&
      (!freshIdentity || policyAllows(freshIdentity, { mountId: row.mountId, path: row.path }, "list"));
    const items = rows.slice(0, 100).filter(permitted).map(({ id, actorId, operationId, pathId, mountId, path, namespace, name, action, previousVersion, newVersion, outcome, createdAt }) =>
      ({ id, actorId, operationId, pathId, mountId, path, namespace, name, action, previousVersion, newVersion, outcome, createdAt }));
    await this.current(actor);
    return { items, nextCursor: rows.length > 100 ? rows[99].id : null };
  }

  async path(id: string, client: Client = this.db): Promise<RegisteredPath> {
    const path = await client.kvPath.findUnique({ where: { id }, include: { fields: true, mount: true } });
    if (!path) throw new KvError(404, "KV path not found");
    logicalPath(path.path);
    this.allowedNamespaces(JSON.parse(path.mount.namespaces));
    if (!this.namespaces.includes(path.namespace) || path.namespace === this.config.historyNamespace ||
      !JSON.parse(path.mount.namespaces).includes(path.namespace)) throw new KvError(403, "KV namespace scope is no longer allowed");
    fieldMapping(path.fields, path.namespace, path.name);
    if (path.fields.some(field => field.namespace !== path.namespace || field.name !== path.name) || path.retention < 1 || path.retention > this.config.maxRetention)
      throw new KvError(503, "KV path metadata unavailable");
    return path;
  }

  allowedNamespaces(value: unknown): string[] {
    if (!Array.isArray(value) || !value.length || value.length > 128 || new Set(value).size !== value.length)
      throw new KvError(400, "Invalid mount namespace scopes");
    return value.map(ns => {
      if (typeof ns !== "string") throw new KvError(400, "Invalid mount namespace scopes");
      validateTarget({ namespace: ns, name: "validation", key: "validation" });
      if (!this.namespaces.includes(ns) || ns === this.config.historyNamespace) throw new KvError(403, "Mount must stay within the current namespace allowlist");
      return ns;
    });
  }

  async listMounts(actor: KvActor, cursor?: string) {
    const user = await this.current(actor), rules = await this.rules(`user:${actor.id}`);
    if (actor.identityId) throw new KvError(403, "Automation cannot enumerate mount administration");
    const allowed = user.role === "write" && user.engineAdmin ? undefined : rules.filter(r => r.effect === "allow" && parseActions(r.actions).includes("list"));
    const rows = await this.db.kvMount.findMany({ where: {
      ...(cursor ? { id: { gt: cursor } } : {}),
      ...(allowed && !allowed.some(r => r.mountId === null) ? { id: { ...(cursor ? { gt: cursor } : {}), in: allowed.map(r => r.mountId!).filter(Boolean) } } : {}),
    }, orderBy: { id: "asc" }, take: 101 });
    const page = rows.slice(0, 100).filter(m => !allowed || !rules.some(r => r.effect === "deny" && r.prefix === "" && (r.mountId === null || r.mountId === m.id) && parseActions(r.actions).includes("list")));
    return { items: page.map(m => ({ ...m, namespaces: JSON.parse(m.namespaces) as string[] })), nextCursor: rows.length > 100 ? rows[99].id : null };
  }

  createMount(actor: KvActor, input: { name: string; namespaces: unknown }) {
    return this.serialized(async tx => {
      await this.admin(actor, tx);
      if (!/^[a-z][a-z0-9-]{0,62}$/.test(input.name)) throw new KvError(400, "Invalid mount name");
      const result = await tx.kvMount.create({ data: { name: input.name, namespaces: JSON.stringify(this.allowedNamespaces(input.namespaces)) } });
      await tx.kvAudit.create({ data: { actorId: actor.id, action: "mount-create", mountId: result.id, outcome: "committed" } });
      return { ...result, namespaces: JSON.parse(result.namespaces) as string[] };
    });
  }

  async changeMount(actor: KvActor, id: string, revision: unknown, input: { name?: string; namespaces?: unknown } | null) {
    const expected = metadataRevision(revision);
    return this.serialized(async tx => {
      await this.admin(actor, tx);
      const mount = await tx.kvMount.findUnique({ where: { id } });
      if (!mount) throw new KvError(404, "KV mount not found");
      if (mount.revision !== expected) throw new KvError(409, "KV metadata changed; refresh before editing");
      if (input === null) {
        if (await tx.kvPath.count({ where: { mountId: id } }) || await tx.kvOperation.count({ where: { mountId: id } }))
          throw new KvError(409, "Mount still has registered paths or operation history");
        await tx.kvMount.delete({ where: { id } });
        await tx.kvPolicy.deleteMany({ where: { mountId: id } });
      } else {
        if (input.name !== undefined && !/^[a-z][a-z0-9-]{0,62}$/.test(input.name)) throw new KvError(400, "Invalid mount name");
        const scopes = input.namespaces === undefined ? undefined : this.allowedNamespaces(input.namespaces);
        if (scopes && await tx.kvPath.count({ where: { mountId: id, namespace: { notIn: scopes } } }))
          throw new KvError(409, "Namespace scope still contains registered paths");
        await tx.kvMount.update({ where: { id }, data: { name: input.name, namespaces: scopes && JSON.stringify(scopes), revision: { increment: 1 } } });
      }
      await tx.kvAudit.create({ data: { actorId: actor.id, mountId: id, action: input === null ? "mount-delete" : "mount-update", outcome: "committed" } });
      const result = input === null ? null : await tx.kvMount.findUniqueOrThrow({ where: { id } });
      return result && { ...result, namespaces: JSON.parse(result.namespaces) as string[] };
    });
  }

  async listPaths(actor: KvActor, mountId?: string, cursor?: string) {
    await this.current(actor);
    const ownerRules = await this.rules(`user:${actor.id}`), identityRules = actor.identityId ? await this.rules(`identity:${actor.identityId}`) : null;
    const grants = ownerRules.filter(r => r.effect === "allow" && parseActions(r.actions).includes("list"));
    const rows = grants.length ? await this.db.kvPath.findMany({ where: {
      ...(mountId ? { mountId } : {}), ...(cursor ? { id: { gt: cursor } } : {}),
      OR: grants.map(r => ({ ...(r.mountId ? { mountId: r.mountId } : {}), ...(r.prefix ? { OR: [{ path: r.prefix }, { path: { startsWith: r.prefix + "/" } }] } : {}) })),
    }, include: { fields: true }, orderBy: { id: "asc" }, take: 101 }) : [];
    const page = rows.slice(0, 100).filter(p => policyAllows(ownerRules, p, "list") && (!identityRules || policyAllows(identityRules, p, "list")));
    return { items: page, nextCursor: rows.length > 100 ? rows[99].id : null };
  }

  async registerPath(actor: KvActor, input: { mountId: string; path: string; namespace: string; name: string; fields: unknown; retention?: number }) {
    logicalPath(input.path);
    const fields = fieldMapping(input.fields, input.namespace, input.name), retention = input.retention ?? this.config.retention;
    if (!Number.isInteger(retention) || retention < 1 || retention > this.config.maxRetention) throw new KvError(400, "Invalid path retention");
    return this.serialized(async tx => {
      await this.authorize(actor, input, "create", tx);
      const mount = await tx.kvMount.findUnique({ where: { id: input.mountId } });
      if (!mount) throw new KvError(404, "KV mount not found");
      if (!this.allowedNamespaces(JSON.parse(mount.namespaces)).includes(input.namespace)) throw new KvError(403, "Path namespace is outside its mount");
      const result = await tx.kvPath.create({ data: { mountId: input.mountId, path: input.path, namespace: input.namespace, name: input.name, retention,
        fields: { create: fields.map(f => ({ ...f, namespace: input.namespace, name: input.name })) } }, include: { fields: true } });
      await tx.kvAudit.create({ data: { actorId: actor.identityId || actor.id, action: "path-register", mountId: result.mountId, pathId: result.id, path: result.path, namespace: result.namespace, name: result.name, outcome: "committed" } });
      return result;
    });
  }

  async changeRetention(actor: KvActor, id: string, revision: unknown, retention: number) {
    const expected = metadataRevision(revision);
    if (!Number.isInteger(retention) || retention < 1 || retention > this.config.maxRetention) throw new KvError(400, "Invalid path retention");
    return this.serialized(async tx => {
      const path = await this.path(id, tx);
      await this.authorize(actor, path, "update", tx);
      if (path.revision !== expected) throw new KvError(409, "KV metadata changed; refresh before editing");
      const result = await tx.kvPath.update({ where: { id }, data: { retention, revision: { increment: 1 } }, include: { fields: true } });
      await tx.kvAudit.create({ data: { actorId: actor.identityId || actor.id, pathId: id, action: "path-retention", outcome: "committed" } });
      return result;
    });
  }

  private async validPolicy(input: PolicyInput, tx: Client, updatingId?: string) {
    logicalPath(input.prefix, true);
    if (!["allow", "deny"].includes(input.effect) || !input.actions.length || input.actions.some(a => !KV_ACTIONS.includes(a)) || new Set(input.actions).size !== input.actions.length)
      throw new KvError(400, "Invalid policy actions or effect");
    if (input.mountId && !await tx.kvMount.findUnique({ where: { id: input.mountId } })) throw new KvError(404, "KV mount not found");
    if (input.principal === "legacy-lookup") {
      if (input.actions.some(a => !["list", "read"].includes(a))) throw new KvError(400, "Legacy lookup has metadata/current-read audience only");
    } else if (input.principal.startsWith("user:")) {
      if (!await tx.user.findUnique({ where: { id: input.principal.slice(5) } })) throw new KvError(404, "Policy user not found");
    } else if (input.principal.startsWith("identity:")) {
      if (!await tx.kvIdentity.findUnique({ where: { id: input.principal.slice(9) } })) throw new KvError(404, "KV identity not found");
    } else throw new KvError(400, "Invalid policy principal");
    if (await tx.kvPolicy.count({ where: { principal: input.principal, ...(updatingId ? { id: { not: updatingId } } : {}) } }) >= 256) throw new KvError(413, "Policy rule limit exceeded");
    return { ...input, actions: JSON.stringify(input.actions) };
  }

  savePolicy(actor: KvActor, input: PolicyInput, id?: string, revision?: unknown) {
    return this.serialized(async tx => {
      await this.admin(actor, tx);
      const data = await this.validPolicy(input, tx, id);
      if (id) {
        const old = await tx.kvPolicy.findUnique({ where: { id } });
        if (!old) throw new KvError(404, "KV policy not found");
        if (old.revision !== metadataRevision(revision)) throw new KvError(409, "KV policy changed; refresh before editing");
      }
      const result = id ? await tx.kvPolicy.update({ where: { id }, data: { ...data, revision: { increment: 1 } } }) : await tx.kvPolicy.create({ data });
      await tx.kvAudit.create({ data: { actorId: actor.id, action: id ? "policy-update" : "policy-create", mountId: input.mountId, path: input.prefix || null, outcome: "committed" } });
      return { ...result, actions: parseActions(result.actions) };
    });
  }

  deletePolicy(actor: KvActor, id: string, revision: unknown) {
    const expected = metadataRevision(revision);
    return this.serialized(async tx => {
      await this.admin(actor, tx);
      const policy = await tx.kvPolicy.findUnique({ where: { id } });
      if (!policy) throw new KvError(404, "KV policy not found");
      if (policy.revision !== expected) throw new KvError(409, "KV policy changed; refresh before editing");
      await tx.kvPolicy.delete({ where: { id } });
      await tx.kvAudit.create({ data: { actorId: actor.id, action: "policy-delete", mountId: policy.mountId, path: policy.prefix || null, outcome: "committed" } });
    });
  }

  async listPolicies(actor: KvActor, cursor?: string) {
    await this.admin(actor);
    const rows = await this.db.kvPolicy.findMany({ where: cursor ? { id: { gt: cursor } } : {}, orderBy: { id: "asc" }, take: 101 });
    return { items: rows.slice(0, 100).map(p => ({ ...p, actions: parseActions(p.actions) })), nextCursor: rows.length > 100 ? rows[99].id : null };
  }

  async issueIdentity(actor: KvActor, input: { ownerId: string; name: string; expiresAt: Date; scopes: IdentityScope[] }) {
    if (!/^[A-Za-z0-9._-]{1,64}$/.test(input.name) || !Number.isFinite(input.expiresAt.getTime()) ||
      input.expiresAt.getTime() <= Date.now() || input.expiresAt.getTime() > Date.now() + 30 * 86400000 ||
      !Array.isArray(input.scopes) || !input.scopes.length || input.scopes.length > 32) throw new KvError(400, "Invalid identity name, expiry or scopes");
    return this.serialized(async tx => {
      const current = await this.current(actor, tx);
      if (actor.identityId || current.role !== "write" || (input.ownerId !== actor.id && !current.engineAdmin)) throw new KvError(403, "Identity issuance requires its owner or engine administration");
      const owner = await tx.user.findUnique({ where: { id: input.ownerId } });
      if (!owner || owner.role !== "write") throw new KvError(403, "Identity owner must have write access");
      const issued = issueCredential();
      const identity = await tx.kvIdentity.create({ data: { id: issued.id, ownerId: owner.id, ownerSessionVersion: owner.sessionVersion, name: input.name, expiresAt: input.expiresAt, credentialHash: issued.hash }, select: identityMetadata });
      for (const scope of input.scopes) {
        const data = await this.validPolicy({ ...scope, principal: `identity:${identity.id}`, effect: "allow" }, tx);
        if (!scope.mountId) throw new KvError(400, "Automation requires an explicit mount scope");
        await tx.kvPolicy.create({ data });
      }
      await tx.kvAudit.create({ data: { actorId: actor.id, action: "identity-issue", outcome: "committed" } });
      return { ...identity, credential: issued.credential };
    });
  }

  async authenticateIdentity(header: string | null): Promise<KvActor> {
    const presented = presentedCredential(header);
    if (!presented) throw new KvError(401, "Invalid KV automation credential");
    const identity = await this.db.kvIdentity.findUnique({ where: { id: presented.id } });
    if (!identity || !hashMatches(presented.hash, identity.credentialHash)) throw new KvError(401, "Invalid KV automation credential");
    const actor = { id: identity.ownerId, sessionVersion: identity.ownerSessionVersion, identityId: identity.id };
    await this.current(actor);
    return actor;
  }

  async listIdentities(actor: KvActor, cursor?: string) {
    const user = await this.current(actor);
    if (actor.identityId) throw new KvError(403, "Automation cannot manage identities");
    const rows = await this.db.kvIdentity.findMany({ where: { ...(user.role === "write" && user.engineAdmin ? {} : { ownerId: actor.id }), ...(cursor ? { id: { gt: cursor } } : {}) }, select: identityMetadata, orderBy: { id: "asc" }, take: 101 });
    return { items: rows.slice(0, 100), nextCursor: rows.length > 100 ? rows[99].id : null };
  }

  revokeIdentity(actor: KvActor, id: string) {
    return this.serialized(async tx => {
      const user = await this.current(actor, tx), identity = await tx.kvIdentity.findUnique({ where: { id } });
      if (!identity) throw new KvError(404, "KV identity not found");
      if (actor.identityId || user.role !== "write" || (identity.ownerId !== user.id && !user.engineAdmin)) throw new KvError(403, "Identity revocation requires its owner or engine administration");
      await tx.kvIdentity.update({ where: { id }, data: { revokedAt: new Date() } });
      await tx.kvAudit.create({ data: { actorId: actor.id, action: "identity-revoke", outcome: "committed" } });
    });
  }
}
