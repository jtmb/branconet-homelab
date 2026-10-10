import { randomUUID } from "node:crypto";
import type { V1Secret } from "@kubernetes/client-node";
import { KvError, KvMutationError, requireGuarded, type KvAction, type KvActor } from "./kv-contract";
import { KvRegistry, type RegisteredPath } from "./kv-registry";
import type { NativeSecretTransport } from "./secret-client";
import { secretFailure } from "./cluster-secrets";
import { validateAlias, type SecretAlias } from "./secret-aliases";
import { CREATED_ANNOTATION, encodedValues, equalValues, exportFields, historyBody, historyValues, nativeIdentity, ownedPath, parseState, selectedValues, stateBody, type PathState, type VersionRef } from "./kv-native-state";

export type NativePrerequisites = { resourceVersion?: string; expectedHead?: number };
const prerequisites = (input: NativePrerequisites, secret: V1Secret, head: number) => {
  if (input.resourceVersion === undefined || input.expectedHead === undefined) throw new KvError(428, "Native resourceVersion and expected head required");
  if (typeof input.resourceVersion !== "string" || !input.resourceVersion || input.resourceVersion.length > 128 || !Number.isSafeInteger(input.expectedHead) || input.expectedHead < 0)
    throw new KvError(400, "Invalid native mutation prerequisites");
  if (nativeIdentity(secret).resourceVersion !== input.resourceVersion || head !== input.expectedHead) throw new KvError(409, "KV head or Secret changed; refresh before retrying");
};
const target = (path: RegisteredPath) => ({ mountId: path.mountId, pathId: path.id, path: path.path, namespace: path.namespace, name: path.name });
const markerName = (pathId: string, operationId: string) => "kv-" + pathId.replaceAll("-", "") + "-" + operationId.replaceAll("-", "").slice(0, 24);

export class KvNativeEngine {
  constructor(readonly registry: KvRegistry, readonly transport: NativeSecretTransport, readonly aliases: () => Promise<SecretAlias[]> = async () => []) {}
  private async permitted(actor: KvActor, id: string, action: KvAction) {
    const path = await this.registry.path(id); await this.registry.authorize(actor, path, action); return path;
  }
  private async canonical(path: RegisteredPath) {
    try { return await this.transport.read(path.namespace, path.name); } catch (error) { throw secretFailure(error); }
  }
  private async history(path: RegisteredPath, current: PathState, ref: VersionRef) {
    const secret = await this.transport.read(this.registry.config.historyNamespace, ref.name);
    if (secret.metadata?.namespace !== this.registry.config.historyNamespace) throw new KvError(409, "History namespace identity changed");
    return historyValues(secret, path, current.sourceUid, ref);
  }
  private async drift(path: RegisteredPath, secret: V1Secret, current: PathState) {
    const values = current.head ? await this.history(path, current, current.versions.find(v => v.version === current.head)!) : {};
    if (!equalValues(values, selectedValues(secret, path))) throw new KvError(409, "Selected native values changed externally; reconcile explicitly");
    return values;
  }
  async status(actor: KvActor, id: string) {
    const path = await this.permitted(actor, id, "list"), secret = await this.canonical(path), current = ownedPath(secret, path);
    return { pathId: id, resourceVersion: nativeIdentity(secret).resourceVersion, adopted: !!current, head: current?.head || 0, tombstone: current?.tombstone || false,
      versions: current?.versions.length || 0, guardedAdoption: this.registry.config.guardedAdoption, guardVerification: "operator assertion; external admission/RBAC evidence required" };
  }
  async read(actor: KvActor, id: string, version?: number, action: "read" | "export" = "read") {
    const path = await this.permitted(actor, id, action), secret = await this.canonical(path), current = ownedPath(secret, path);
    if (!current) throw new KvError(409, "KV path requires explicit administrator adoption or creation");
    let values: Record<string,string>, tombstone = current.tombstone;
    if (version !== undefined) {
      if (!Number.isSafeInteger(version) || version < 1) throw new KvError(400, "Invalid history version");
      const ref = current.versions.find(v => v.version === version); if (!ref) throw new KvError(404, "Committed KV version not found");
      values = await this.history(path, current, ref); tombstone = ref.tombstone;
    } else values = await this.drift(path, secret, current);
    await this.registry.authorize(actor, path, action); // Do not return a value after revocation during an API read.
    return { pathId: id, version: version ?? current.head, resourceVersion: nativeIdentity(secret).resourceVersion, head: current.head, tombstone, fields: exportFields(values) };
  }
  async versions(actor: KvActor, id: string) {
    const path = await this.permitted(actor, id, "list"), secret = await this.canonical(path), current = ownedPath(secret, path);
    return { pathId: id, resourceVersion: nativeIdentity(secret).resourceVersion, head: current?.head || 0, items: (current?.versions || []).map(({version,createdAt,tombstone}) => ({version,createdAt,tombstone})) };
  }
  private async matchingAliases(path: RegisteredPath) {
    const aliases = await this.aliases();
    if (aliases.length > 10000) throw new KvError(503, "Legacy alias metadata exceeds the limit");
    return aliases.map(validateAlias).filter(a => a.namespace === path.namespace && a.name === path.name && path.fields.some(f => f.key === a.key)).sort((a,b) => a.alias.localeCompare(b.alias));
  }
  async adoptionPreview(actor: KvActor, id: string) {
    const path = await this.permitted(actor, id, "create"); await this.registry.admin(actor);
    const secret = await this.canonical(path);
    if (ownedPath(secret, path)) throw new KvError(409, "KV path is already adopted");
    selectedValues(secret, path, true);
    const aliases = await this.matchingAliases(path);
    return { pathId: id, ...nativeIdentity(secret), expectedHead: 0, fields: path.fields.map(({field,key}) => ({field,key})), legacyAliases: aliases, guardedAdoption: this.registry.config.guardedAdoption };
  }
  private async start(actor: KvActor, path: RegisteredPath, action: KvAction | "adopt", previousVersion: number, newVersion: number, aliases: SecretAlias[] = []) {
    return this.registry.serialized(async tx => {
      await this.registry.authorize(actor, path, action === "adopt" ? "create" : action, tx);
      if (action === "adopt" || action === "create") await this.registry.admin(actor, tx);
      const op = await tx.kvOperation.create({ data: { id: randomUUID(), actorId: actor.identityId || actor.id, ...target(path), action, previousVersion, newVersion, outcome: "pending" } });
      await tx.kvAudit.create({ data: { actorId: op.actorId, operationId: op.id, ...target(path), action, previousVersion, newVersion, outcome: "pending" } });
      for (const alias of aliases) await tx.kvLegacyGrant.upsert({ where: { pathId_alias: { pathId: path.id, alias: alias.alias } }, update: {}, create: { pathId: path.id, ...alias } });
      return op;
    });
  }
  private async finish(operation: Awaited<ReturnType<KvNativeEngine["start"]>>, outcome: string) {
    try {
      await this.registry.serialized(async tx => {
        await tx.kvOperation.update({ where: { id: operation.id }, data: { outcome } });
        await tx.kvAudit.create({ data: { actorId: operation.actorId, operationId: operation.id, mountId: operation.mountId, pathId: operation.pathId, path: operation.path, namespace: operation.namespace, name: operation.name,
          action: operation.action, previousVersion: operation.previousVersion, newVersion: operation.newVersion, outcome } });
      });
      return true;
    } catch { return false; }
  }
  private async commit(actor: KvActor, path: RegisteredPath, secret: V1Secret, current: PathState | undefined, values: Record<string,string>, action: KvAction | "adopt", tombstone = false, prepared?: Awaited<ReturnType<KvNativeEngine["start"]>>) {
    const operation = prepared || await this.start(actor, path, action, current?.head || 0, (current?.sequence || 0) + 1);
    const version = operation.newVersion!, historyName = markerName(path.id, operation.id), source = nativeIdentity(secret);
    let candidate: V1Secret | undefined, attemptedCas = false;
    try {
      if (secret.immutable) throw new KvError(409, "Canonical Secret is immutable");
      if (!Number.isSafeInteger(version)) throw new KvError(413, "KV version counter exceeds its limit");
      const candidateBody = historyBody(path, source.uid, this.registry.config.historyNamespace, historyName, version, operation.id, values, tombstone);
      await this.registry.authorize(actor, path, action === "adopt" ? "create" : action);
      try { candidate = await this.transport.create(this.registry.config.historyNamespace, candidateBody); }
      catch (error) {
        if (secretFailure(error).status !== 503) throw error;
        try { candidate = await this.transport.read(this.registry.config.historyNamespace, historyName); } catch { throw error; }
      }
      const identity = nativeIdentity(candidate), createdAt = new Date().toISOString();
      const ref: VersionRef = { version, name: historyName, uid: identity.uid, operationId: operation.id, createdAt, tombstone };
      if (candidate.metadata?.namespace !== this.registry.config.historyNamespace || !equalValues(historyValues(candidate, path, source.uid, ref), values)) throw new KvError(409, "Candidate history ownership changed");
      const state = parseState(secret);
      const next: PathState = { id: path.id, mountId: path.mountId, path: path.path, sourceUid: source.uid, fields: path.fields.map(({field,key}) => ({field,key})),
        head: version, sequence: version, tombstone, versions: [...(current?.versions || []), ref].slice(-path.retention),
        operations: [...(current?.operations || []), { id: operation.id, action, previousVersion: current?.head || 0, newVersion: version, historyName, historyUid: identity.uid, createdAt }].slice(-100) };
      state.paths = [...state.paths.filter(p => p.id !== path.id), next];
      const body = stateBody(secret, state, path, values);
      await this.registry.authorize(actor, path, action === "adopt" ? "create" : action);
      if (action === "adopt" || action === "create") await this.registry.admin(actor);
      attemptedCas = true;
      const result = await this.transport.replace(path.namespace, path.name, body);
      const committed = ownedPath(result, path);
      if (committed?.head !== version || !committed.operations.some(op => op.id === operation.id && op.historyUid === identity.uid) || !equalValues(selectedValues(result, path), values))
        throw new KvError(503, "Native commit requires recovery verification");
      if (!await this.finish(operation, "committed")) throw new KvMutationError(503, "Native KV committed; metadata recovery required", operation.id, "recovery-required");
      return { operationId: operation.id, outcome: "committed", head: version, resourceVersion: nativeIdentity(result).resourceVersion, tombstone };
    } catch (error) {
      if (error instanceof KvMutationError) throw error;
      const safe = secretFailure(error);
      if (attemptedCas && safe.status === 503) {
        try {
          const readBack = await this.canonical(path), owner = ownedPath(readBack, path);
          const proof = owner?.operations.find(op => op.id === operation.id && op.historyName === historyName && op.historyUid === candidate?.metadata?.uid);
          if (owner?.sourceUid === source.uid && proof && (owner.head !== version || equalValues(selectedValues(readBack, path), values))) {
            if (!await this.finish(operation, "committed")) throw new KvMutationError(503, "Native KV committed; metadata recovery required", operation.id, "recovery-required");
            return { operationId: operation.id, outcome: "committed", head: version, resourceVersion: nativeIdentity(readBack).resourceVersion, tombstone };
          }
        } catch (readError) { if (readError instanceof KvMutationError) throw readError; }
      }
      const outcome = safe.status === 503 ? "ambiguous" : "conflict";
      const recorded = await this.finish(operation, outcome);
      throw new KvMutationError(safe.status, safe.status === 503 ? "Native KV outcome is ambiguous; inspect operation before retrying" : safe.message, operation.id, recorded ? outcome : "recovery-required");
    }
  }
  async adopt(actor: KvActor, id: string, input: NativePrerequisites & { legacyAliases: string[] }) {
    requireGuarded(this.registry.config);
    const path = await this.permitted(actor, id, "create"); await this.registry.admin(actor);
    const secret = await this.canonical(path);
    if (ownedPath(secret, path)) throw new KvError(409, "KV path is already adopted");
    prerequisites(input, secret, 0);
    const values = selectedValues(secret, path, true), aliases = await this.matchingAliases(path);
    if (!Array.isArray(input.legacyAliases) || input.legacyAliases.length !== aliases.length || new Set(input.legacyAliases).size !== aliases.length || aliases.some(a => !input.legacyAliases.includes(a.alias)))
      throw new KvError(409, "Legacy alias impact changed; refresh the adoption preview");
    const operation = await this.start(actor, path, "adopt", 0, 1, aliases);
    return this.commit(actor, path, secret, undefined, values, "adopt", false, operation);
  }
  async create(actor: KvActor, id: string, input: NativePrerequisites & { fields: unknown }) {
    requireGuarded(this.registry.config);
    const path = await this.permitted(actor, id, "create"); await this.registry.admin(actor);
    const values = encodedValues(input.fields, path);
    let secret: V1Secret;
    try { secret = await this.canonical(path); }
    catch (error) {
      if (secretFailure(error).status !== 404) throw error;
      if (input.resourceVersion === undefined || input.expectedHead === undefined) throw new KvError(428, "Absent resourceVersion and expected head required");
      if (input.resourceVersion !== "absent" || input.expectedHead !== 0) throw new KvError(409, "New path requires absent resourceVersion and head zero");
      const operation = await this.start(actor, path, "create", 0, 1);
      try {
        await this.registry.admin(actor); await this.registry.authorize(actor, path, "create");
        secret = await this.transport.create(path.namespace, { apiVersion: "v1", kind: "Secret", type: "Opaque", metadata: { namespace: path.namespace, name: path.name,
          annotations: { [CREATED_ANNOTATION]: JSON.stringify({ pathId: path.id, operationId: operation.id }) } }, data: {} });
      } catch (failure) {
        if (secretFailure(failure).status === 503) {
          try {
            secret = await this.canonical(path);
            const marker = JSON.parse(secret.metadata?.annotations?.[CREATED_ANNOTATION] || "");
            if (marker.pathId !== path.id || marker.operationId !== operation.id || Object.keys(secret.data || {}).length) throw failure;
          } catch { await this.finish(operation, "ambiguous"); throw new KvMutationError(503, "Empty canonical creation is ambiguous; inspect operation", operation.id, "ambiguous"); }
        } else { await this.finish(operation, "conflict"); throw new KvMutationError(secretFailure(failure).status, secretFailure(failure).message, operation.id, "conflict"); }
      }
      return this.commit(actor, path, secret!, undefined, values, "create", false, operation);
    }
    if (ownedPath(secret, path)) throw new KvError(409, "KV path already exists; use versioned update");
    let marker: any; try { marker = JSON.parse(secret.metadata?.annotations?.[CREATED_ANNOTATION] || ""); } catch { /* existing imported object needs adoption */ }
    if (marker?.pathId !== path.id || Object.keys(secret.data || {}).length) throw new KvError(409, "Existing native Secret requires explicit adoption");
    prerequisites(input, secret, 0);
    return this.commit(actor, path, secret, undefined, values, "create");
  }
  async change(actor: KvActor, id: string, input: NativePrerequisites & { fields?: unknown; version?: number }, action: "update" | "delete" | "rollback" | "reconcile" | "rotate" = "update") {
    requireGuarded(this.registry.config);
    const path = await this.permitted(actor, id, action), secret = await this.canonical(path), current = ownedPath(secret, path);
    if (!current) throw new KvError(409, "KV path requires explicit administrator adoption or creation");
    prerequisites(input, secret, current.head);
    if (action !== "reconcile") await this.drift(path, secret, current);
    let values: Record<string,string>, tombstone = action === "delete";
    if (action === "rollback") {
      const ref = current.versions.find(v => v.version === input.version); if (!ref) throw new KvError(404, "Committed rollback version not found");
      values = await this.history(path, current, ref); tombstone = ref.tombstone;
    } else if (action === "reconcile") { values = selectedValues(secret, path); tombstone = current.tombstone && !Object.keys(values).length; }
    else values = action === "delete" ? {} : encodedValues(input.fields, path);
    return this.commit(actor, path, secret, current, values, action, tombstone);
  }
  async resolve(actor: KvActor, id: string) {
    const operation = await this.registry.db.kvOperation.findUnique({ where: { id } });
    if (!operation) throw new KvError(404, "KV operation not found");
    const path = await this.permitted(actor, operation.pathId, "list");
    if (!["pending", "ambiguous", "recovery-required"].includes(operation.outcome)) return operation;
    try {
      const secret = await this.canonical(path), current = ownedPath(secret, path), proof = current?.operations.find(op => op.id === id);
      if (proof && proof.action === operation.action && proof.newVersion === operation.newVersion && await this.finish(operation, "committed"))
        return { ...operation, outcome: "committed" };
    } catch { /* Missing/unreachable/replaced state never proves failure or permits deletion. */ }
    return { ...operation, outcome: operation.outcome === "pending" ? "ambiguous" : operation.outcome };
  }
}
