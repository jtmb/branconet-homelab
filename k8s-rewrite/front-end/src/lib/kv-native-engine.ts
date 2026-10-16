import { randomBytes, randomUUID } from "node:crypto";
import type { V1Secret } from "@kubernetes/client-node";
import type { Prisma } from "@prisma/client";
import { KvError, KvMutationError, requireGuarded, type KvAction, type KvActor } from "./kv-contract";
import { KvRegistry, type RegisteredPath } from "./kv-registry";
import type { NativeSecretTransport } from "./secret-client";
import { secretFailure } from "./cluster-secrets";
import { validateAlias, type SecretAlias } from "./secret-aliases";
import { CREATED_ANNOTATION, encodedValues, equalValues, exportFields, historyBody, historyReference, historyValues, nativeIdentity, ownedPath, parseState, selectedValues, stateBody, type PathState, type VersionRef } from "./kv-native-state";

export type NativePrerequisites = { resourceVersion?: string; expectedHead?: number; pathRevision?: number };
export type HistorySelection = { name: string; uid: string; resourceVersion: string };
export type DestroySelection = { version: number; name: string; uid: string };
export type DestroyInput = NativePrerequisites & { versions: number[]; confirmPath: string; sourceUid?: string; histories?: DestroySelection[] };
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
  private async permitted(actor: KvActor, id: string, action: KvAction, revision?: number) {
    const path = await this.registry.path(id); await this.registry.authorize(actor, path, action);
    if(revision!==undefined&&(!Number.isSafeInteger(revision)||revision<1))throw new KvError(400,"Invalid path metadata revision");
    if(revision!==undefined&&revision!==path.revision)throw new KvError(409,"KV metadata changed; refresh before retrying");
    return path;
  }
  private async canonical(path: RegisteredPath) {
    try { return await this.transport.read(path.namespace, path.name); } catch (error) { throw secretFailure(error); }
  }
  private async fresh(actor: KvActor, path: RegisteredPath, action: KvAction | "adopt", client?: Prisma.TransactionClient) {
    const latest = await this.registry.path(path.id, client);
    if (latest.revision !== path.revision || latest.mount.revision !== path.mount.revision) throw new KvError(409, "KV metadata changed; refresh before retrying");
    await this.registry.authorize(actor, latest, action === "adopt" ? "create" : action, client);
  }
  private async initial(path: RegisteredPath, partial = false) {
    if (await this.registry.db.kvOperation.count({ where: { pathId: path.id, outcome: partial ? "committed" : { in: ["committed", "pending", "ambiguous", "recovery-required"] } } }))
      throw new KvError(409, "Path has prior or unresolved native history; explicit recovery required");
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
    return { pathId: id, ...nativeIdentity(secret), adopted: !!current, head: current?.head || 0, tombstone: current?.tombstone || false,
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
    await this.registry.serialized(async tx => {
      await this.registry.authorize(actor, path, action, tx);
      await tx.kvAudit.create({ data: { actorId: actor.identityId || actor.id, ...target(path), action, previousVersion: current.head, newVersion: version ?? current.head, outcome: "authorized" } });
    }); // Fail closed if current permission or metadata audit is unavailable before value release.
    return { pathId: id, version: version ?? current.head, resourceVersion: nativeIdentity(secret).resourceVersion, head: current.head, tombstone, fields: exportFields(values) };
  }
  async versions(actor: KvActor, id: string) {
    const path = await this.permitted(actor, id, "list"), secret = await this.canonical(path), current = ownedPath(secret, path);
    return { pathId: id, ...nativeIdentity(secret), head: current?.head || 0, items: (current?.versions || []).map(({version,name,uid,createdAt,tombstone}) => ({version,name,uid,createdAt,tombstone})) };
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
    await this.initial(path);
    selectedValues(secret, path, true);
    const aliases = await this.matchingAliases(path);
    return { pathId: id, ...nativeIdentity(secret), expectedHead: 0, fields: path.fields.map(({field,key}) => ({field,key})), legacyAliases: aliases, guardedAdoption: this.registry.config.guardedAdoption };
  }
  private async start(actor: KvActor, path: RegisteredPath, action: KvAction | "adopt", previousVersion: number, newVersion: number, aliases: SecretAlias[] = [], administrative = false, rotation?: { id: string; revision: number; field: string }) {
    return this.registry.serialized(async tx => {
      await this.fresh(actor, path, action, tx);
      if (administrative || action === "adopt" || action === "create") await this.registry.admin(actor, tx);
      const op = await tx.kvOperation.create({ data: { id: randomUUID(), actorId: actor.identityId || actor.id, ...target(path), action, previousVersion, newVersion, outcome: "pending" } });
      if (rotation) {
        const changed = await tx.kvRotation.updateMany({ where: { id: rotation.id, pathId: path.id, field: rotation.field, revision: rotation.revision, state: "prepare", operationId: null },
          data: { operationId: op.id, state: "replace-pending", revision: { increment: 1 } } });
        if (changed.count !== 1) throw new KvError(409, "Rotation intent changed; refresh before generating a replacement");
      }
      await tx.kvAudit.create({ data: { actorId: op.actorId, operationId: op.id, ...target(path), action, previousVersion, newVersion, outcome: "pending" } });
      for (const alias of aliases) await tx.kvLegacyGrant.upsert({ where: { pathId_alias: { pathId: path.id, alias: alias.alias } }, update: {}, create: { pathId: path.id, ...alias } });
      if (aliases.length) await tx.kvServicePrincipal.update({ where: { id: "legacy-lookup" }, data: { revision: { increment: 1 } } });
      return op;
    });
  }
  private async finish(operation: Awaited<ReturnType<KvNativeEngine["start"]>>, outcome: string) {
    try {
      await this.registry.serialized(async tx => {
        await tx.kvOperation.update({ where: { id: operation.id }, data: { outcome } });
        await tx.kvRotation.updateMany({ where: { operationId: operation.id, state: { in: ["replace-pending", "recovery-required"] } },
          data: { state: outcome === "committed" ? "awaiting-ack" : outcome === "conflict" ? "conflict" : "recovery-required", revision: { increment: 1 } } });
        await tx.kvAudit.create({ data: { actorId: operation.actorId, operationId: operation.id, mountId: operation.mountId, pathId: operation.pathId, path: operation.path, namespace: operation.namespace, name: operation.name,
          action: operation.action, previousVersion: operation.previousVersion, newVersion: operation.newVersion, outcome } });
      });
      return true;
    } catch { return false; }
  }
  private async commit(actor: KvActor, path: RegisteredPath, secret: V1Secret, current: PathState | undefined, values: Record<string,string>, action: KvAction | "adopt", tombstone = false, prepared?: Awaited<ReturnType<KvNativeEngine["start"]>>) {
    const operation = prepared || await this.start(actor, path, action, current?.head || 0, (current?.sequence || 0) + 1);
    const version = operation.newVersion!, historyName = markerName(path.id, operation.id);
    let source: ReturnType<typeof nativeIdentity>;
    try { source = nativeIdentity(secret); }
    catch { await this.finish(operation, "recovery-required"); throw new KvMutationError(503, "Native source identity unavailable; inspect operation", operation.id, "recovery-required"); }
    let candidate: V1Secret | undefined, attemptedCas = false;
    try {
      if (secret.immutable) throw new KvError(409, "Canonical Secret is immutable");
      if (!Number.isSafeInteger(version)) throw new KvError(413, "KV version counter exceeds its limit");
      const candidateBody = historyBody(path, source.uid, this.registry.config.historyNamespace, historyName, version, operation.id, values, tombstone);
      const createdAt = new Date().toISOString();
      const canonicalBody = (historyUid: string) => {
        const ref: VersionRef = { version, name: historyName, uid: historyUid, operationId: operation.id, createdAt, tombstone };
        const state = parseState(secret);
        const next: PathState = { id: path.id, mountId: path.mountId, path: path.path, sourceUid: source.uid, fields: path.fields.map(({field,key}) => ({field,key})),
          head: version, sequence: version, tombstone, versions: [...(current?.versions || []), ref].slice(-path.retention),
          operations: [...(current?.operations || []), { id: operation.id, action, previousVersion: current?.head || 0, newVersion: version, historyName, historyUid, createdAt }].slice(-100) };
        state.paths = [...state.paths.filter(p => p.id !== path.id), next];
        return stateBody(secret, state, path, values);
      };
      // A UID is bounded to 128 UTF-16 units; NUL gives the largest JSON escape.
      // Preflight both annotation/object ceilings before any immutable candidate write.
      canonicalBody("\u0000".repeat(128));
      await this.fresh(actor, path, action);
      try { candidate = await this.transport.create(this.registry.config.historyNamespace, candidateBody); }
      catch (error) {
        if (secretFailure(error).status !== 503) throw error;
        try { candidate = await this.transport.read(this.registry.config.historyNamespace, historyName); } catch { throw error; }
      }
      const identity = nativeIdentity(candidate);
      const ref: VersionRef = { version, name: historyName, uid: identity.uid, operationId: operation.id, createdAt, tombstone };
      if (candidate.metadata?.namespace !== this.registry.config.historyNamespace || !equalValues(historyValues(candidate, path, source.uid, ref), values)) throw new KvError(409, "Candidate history ownership changed");
      const body = canonicalBody(identity.uid);
      await this.fresh(actor, path, action);
      if (action === "adopt" || action === "create") await this.registry.admin(actor);
      attemptedCas = true;
      const result = await this.transport.replace(path.namespace, path.name, body);
      let verified = false;
      try {
        const committed = ownedPath(result, path);
        verified = committed?.head === version && committed.operations.some(op => op.id === operation.id && op.historyUid === identity.uid) && equalValues(selectedValues(result, path), values);
      } catch { /* A successful PUT with unverifiable response is an unknown outcome, not a proven conflict. */ }
      if (!verified)
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
    const path = await this.permitted(actor, id, "create", input.pathRevision); await this.registry.admin(actor);
    const secret = await this.canonical(path);
    if (ownedPath(secret, path)) throw new KvError(409, "KV path is already adopted");
    await this.initial(path);
    prerequisites(input, secret, 0);
    const values = selectedValues(secret, path, true), aliases = await this.matchingAliases(path);
    if (!Array.isArray(input.legacyAliases) || input.legacyAliases.length !== aliases.length || new Set(input.legacyAliases).size !== aliases.length || aliases.some(a => !input.legacyAliases.includes(a.alias)))
      throw new KvError(409, "Legacy alias impact changed; refresh the adoption preview");
    const operation = await this.start(actor, path, "adopt", 0, 1, aliases);
    return this.commit(actor, path, secret, undefined, values, "adopt", false, operation);
  }
  async create(actor: KvActor, id: string, input: NativePrerequisites & { fields: unknown }) {
    requireGuarded(this.registry.config);
    const path = await this.permitted(actor, id, "create", input.pathRevision); await this.registry.admin(actor);
    const values = encodedValues(input.fields, path);
    let secret: V1Secret;
    try { secret = await this.canonical(path); }
    catch (error) {
      if (secretFailure(error).status !== 404) throw error;
      await this.initial(path);
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
    await this.initial(path, true);
    prerequisites(input, secret, 0);
    return this.commit(actor, path, secret, undefined, values, "create");
  }
  async change(actor: KvActor, id: string, input: NativePrerequisites & { fields?: unknown; version?: number }, action: "update" | "delete" | "rollback" | "reconcile" = "update") {
    requireGuarded(this.registry.config);
    const path = await this.permitted(actor, id, action, input.pathRevision), secret = await this.canonical(path), current = ownedPath(secret, path);
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

  async rotate(actor: KvActor, id: string, input: NativePrerequisites & { rotationId: string; revision: number; field: string }) {
    requireGuarded(this.registry.config);
    const path = await this.permitted(actor, id, "rotate", input.pathRevision), secret = await this.canonical(path), current = ownedPath(secret, path);
    if (!current || current.tombstone) throw new KvError(409, "Rotation requires an active adopted document");
    prerequisites(input, secret, current.head);
    const values = await this.drift(path, secret, current);
    if (!path.fields.some(mapping => mapping.field === input.field) || !Object.hasOwn(values, input.field)) throw new KvError(400, "Rotation requires an existing mapped field");
    const operation = await this.start(actor, path, "rotate", current.head, current.sequence + 1, [], false,
      { id: input.rotationId, revision: input.revision, field: input.field });
    // Link intent and operation atomically before generating anything. No generated value leaves native storage.
    try { Object.defineProperty(values, input.field, { value: Buffer.from(randomBytes(32).toString("base64url"), "utf8").toString("base64"), enumerable: true, configurable: true, writable: true }); }
    catch { await this.finish(operation, "conflict"); throw new KvMutationError(503, "Static replacement generation failed before native mutation", operation.id, "conflict"); }
    return this.commit(actor, path, secret, current, values, "rotate", false, operation);
  }

  async rotationProof(actor: KvActor, id: string, operationId: string, input: NativePrerequisites) {
    const path = await this.permitted(actor, id, "rotate"), secret = await this.canonical(path), current = ownedPath(secret, path);
    if (!current) throw new KvError(409, "Native rotation ownership requires recovery");
    prerequisites(input, secret, current.head);
    const operation = await this.registry.db.kvOperation.findUnique({ where: { id: operationId } });
    if (!operation || operation.pathId !== path.id || operation.action !== "rotate" || operation.newVersion !== current.head ||
      !current.operations.some(marker => marker.id === operationId && marker.action === "rotate" && marker.newVersion === current.head))
      throw new KvError(409, "Rotation is not the current native head; explicit recovery required");
    await this.drift(path, secret, current);
    await this.registry.authorize(actor, path, "rotate");
    return { head: current.head, resourceVersion: nativeIdentity(secret).resourceVersion };
  }

  private async detachHistory(actor: KvActor, path: RegisteredPath, secret: V1Secret, current: PathState, versions: number[], administrative = false) {
    const head = versions.includes(current.head) ? 0 : current.head;
    const operation = await this.start(actor, path, "destroy", current.head, head, [], administrative);
    const state = parseState(secret), sourceUid = nativeIdentity(secret).uid;
    const next: PathState = { ...current, head, versions: current.versions.filter(ref => !versions.includes(ref.version)),
      operations: [...current.operations, { id: operation.id, action: "destroy", previousVersion: current.head, newVersion: head, createdAt: new Date().toISOString() }].slice(-100) };
    state.paths = state.paths.map(p => p.id === path.id ? next : p);
    let attempted = false;
    const proven = (result: V1Secret) => {
      const owner = ownedPath(result, path);
      return owner?.sourceUid === sourceUid && owner.operations.some(op => op.id === operation.id && op.action === "destroy" && op.newVersion === head) &&
        !owner.versions.some(ref => versions.includes(ref.version));
    };
    try {
      const body = stateBody(secret, state, path);
      await this.fresh(actor, path, "destroy");
      if (administrative) await this.registry.admin(actor);
      attempted = true;
      const result = await this.transport.replace(path.namespace, path.name, body);
      let verified = false; try { verified = proven(result); } catch { /* Verify by read-back below. */ }
      if (!verified) throw new KvError(503, "History reference update requires recovery verification");
      if (!await this.finish(operation, "committed")) throw new KvMutationError(503, "History references committed; metadata recovery required", operation.id, "recovery-required");
      return { operationId: operation.id, outcome: "committed", head, resourceVersion: nativeIdentity(result).resourceVersion };
    } catch (error) {
      if (error instanceof KvMutationError) throw error;
      const safe = secretFailure(error);
      if (attempted && safe.status === 503) {
        try {
          const result = await this.canonical(path);
          if (proven(result)) {
            if (!await this.finish(operation, "committed")) throw new KvMutationError(503, "History references committed; metadata recovery required", operation.id, "recovery-required");
            return { operationId: operation.id, outcome: "committed", head, resourceVersion: nativeIdentity(result).resourceVersion };
          }
        } catch (readError) { if (readError instanceof KvMutationError) throw readError; }
      }
      const outcome = safe.status === 503 ? "ambiguous" : "conflict", recorded = await this.finish(operation, outcome);
      throw new KvMutationError(safe.status, safe.status === 503 ? "History reference outcome is ambiguous; inspect operation" : safe.message, operation.id, recorded ? outcome : "recovery-required");
    }
  }

  private async cleanupHistory(actor: KvActor, path: RegisteredPath, sourceUid: string, ref: VersionRef, operationId: string, selection?: HistorySelection, administrative = false) {
    try {
      const source = await this.canonical(path), state = parseState(source), owner = ownedPath(source, path, state);
      if (!owner || owner.sourceUid !== sourceUid || state.paths.some(p => p.versions.some(v => v.uid === ref.uid || v.name === ref.name)))
        throw new KvError(409, "History is referenced or source ownership changed; retained");
      let history: V1Secret;
      try { history = await this.transport.read(this.registry.config.historyNamespace, ref.name); }
      catch (error) { if (secretFailure(error).status === 404) return { version: ref.version, name: ref.name, outcome: "absent", status: 200 }; throw error; }
      if (history.metadata?.namespace !== this.registry.config.historyNamespace) throw new KvError(409, "History namespace identity changed");
      historyValues(history, path, sourceUid, ref);
      const identity = nativeIdentity(history);
      if (selection && (identity.uid !== selection.uid || identity.resourceVersion !== selection.resourceVersion)) throw new KvError(409, "History preview changed; retained");
      await this.registry.serialized(async tx => {
        await this.fresh(actor, path, "destroy", tx);
        if (administrative) await this.registry.admin(actor, tx);
        await tx.kvAudit.create({ data: { actorId: actor.identityId || actor.id, ...target(path), operationId, action: "history-delete", newVersion: ref.version, outcome: "pending" } });
      });
      let outcome = "deleted";
      try { await this.transport.delete(this.registry.config.historyNamespace, ref.name, identity.uid, identity.resourceVersion); }
      catch (error) {
        if (secretFailure(error).status !== 503) throw error;
        let absent = false;
        try { await this.transport.read(this.registry.config.historyNamespace, ref.name); }
        catch (readError) { absent = secretFailure(readError).status === 404; }
        if (!absent) throw new KvError(503, "History deletion outcome is ambiguous; inspect before retrying");
        outcome = "absent";
      }
      await this.registry.serialized(async tx => {
        await tx.kvAudit.create({ data: { actorId: actor.identityId || actor.id, ...target(path), operationId, action: "history-delete", newVersion: ref.version, outcome } });
      });
      return { version: ref.version, name: ref.name, outcome, status: 200 };
    } catch (error) {
      const safe = secretFailure(error);
      return { version: ref.version, name: ref.name, outcome: safe.status === 503 ? "recovery-required" : "retained", status: safe.status, error: safe.message };
    }
  }

  async destroy(actor: KvActor, id: string, input: DestroyInput, signal?: AbortSignal) {
    const deadline = Date.now() + 30000;
    requireGuarded(this.registry.config);
    const path = await this.permitted(actor, id, "destroy", input.pathRevision);
    if (input.confirmPath !== path.path) throw new KvError(400, "Exact logical path confirmation required");
    if (!Array.isArray(input.versions) || !input.versions.length || input.versions.length > 100 || new Set(input.versions).size !== input.versions.length || input.versions.some(v => !Number.isSafeInteger(v) || v < 1))
      throw new KvError(400, "Select between one and 100 distinct committed versions");
    const secret = await this.canonical(path), current = ownedPath(secret, path);
    if (!current) throw new KvError(409, "Owned canonical source required; history retained");
    prerequisites(input, secret, current.head);
    if (input.sourceUid === undefined || input.histories === undefined) throw new KvError(428, "Canonical UID and selected history identities required");
    if (typeof input.sourceUid !== "string" || !input.sourceUid || input.sourceUid.length > 128 || !Array.isArray(input.histories) ||
      input.histories.length !== input.versions.length || new Set(input.histories.map(item => item?.version)).size !== input.histories.length ||
      input.histories.some(item => !item || !Number.isSafeInteger(item.version) || !input.versions.includes(item.version) ||
        typeof item.name !== "string" || !/^kv-[0-9a-f]{32}-[0-9a-f]{24}$/.test(item.name) || typeof item.uid !== "string" || !item.uid || item.uid.length > 128))
      throw new KvError(400, "Invalid selected history identity capture");
    if (input.sourceUid !== nativeIdentity(secret).uid) throw new KvError(409, "Canonical Secret identity changed; refresh before retrying");
    if (input.versions.includes(current.head) && !current.tombstone) throw new KvError(409, "Tombstone the active path before destroying its head");
    const refs = input.versions.map(version => {
      const ref = current.versions.find(item => item.version === version);
      if (!ref) throw new KvError(404, "Committed KV version not found");
      const captured = input.histories!.find(item => item.version === version)!;
      if (captured.name !== ref.name || captured.uid !== ref.uid) throw new KvError(409, "Committed history identity changed; refresh before retrying");
      return ref;
    });
    await this.drift(path, secret, current);
    for (const ref of refs) {
      if (signal?.aborted || Date.now() >= deadline) throw new KvError(408, "History cleanup stopped before reference mutation");
      await this.history(path, current, ref);
    }
    if (signal?.aborted || Date.now() >= deadline) throw new KvError(408, "History cleanup stopped before reference mutation");
    const result = await this.detachHistory(actor, path, secret, current, input.versions), cleanup = [];
    for (const ref of refs) cleanup.push(signal?.aborted || Date.now() >= deadline ? { version: ref.version, name: ref.name, status: 408, outcome: "retained" } :
      await this.cleanupHistory(actor, path, current.sourceUid, ref, result.operationId));
    return { ...result, cleanupComplete: cleanup.every(item => ["deleted", "absent"].includes(item.outcome)), cleanup };
  }

  async gcPreview(actor: KvActor, id: string) {
    await this.registry.admin(actor);
    const path = await this.permitted(actor, id, "destroy"), secret = await this.canonical(path), state = parseState(secret), current = ownedPath(secret, path, state);
    if (!current) throw new KvError(409, "Owned canonical source required; history retained");
    await this.drift(path, secret, current);
    const metadata = await this.transport.listMetadata(this.registry.config.historyNamespace), items: HistorySelection[] = [];
    let retained = 0, eligible = 0;
    for (const meta of metadata) {
      const ref = historyReference(meta, path, current.sourceUid);
      if (!ref) continue;
      if (Date.now() - Date.parse(ref.createdAt) < 86400000 || state.paths.some(p => p.versions.some(v => v.uid === ref.uid || v.name === ref.name))) { retained++; continue; }
      eligible++;
      if (items.length < 100) items.push({ name: ref.name, ...nativeIdentity({ metadata: meta }) });
    }
    await this.fresh(actor, path, "destroy"); await this.registry.admin(actor);
    if (nativeIdentity(await this.canonical(path)).resourceVersion !== nativeIdentity(secret).resourceVersion) throw new KvError(409, "Source changed; refresh cleanup preview");
    return { pathId: id, pathRevision: path.revision, resourceVersion: nativeIdentity(secret).resourceVersion, expectedHead: current.head,
      minimumAgeHours: 24, eligible, retained, complete: eligible <= 100, items };
  }

  async gc(actor: KvActor, id: string, input: NativePrerequisites & { histories: HistorySelection[]; confirmPath: string }, signal?: AbortSignal) {
    requireGuarded(this.registry.config); await this.registry.admin(actor);
    const path = await this.permitted(actor, id, "destroy", input.pathRevision);
    if (input.confirmPath !== path.path || !Array.isArray(input.histories) || !input.histories.length || input.histories.length > 100 || new Set(input.histories.map(h => h.name)).size !== input.histories.length)
      throw new KvError(400, "Exact path and distinct history confirmation required");
    const secret = await this.canonical(path), state = parseState(secret), current = ownedPath(secret, path, state);
    if (!current) throw new KvError(409, "Owned canonical source required; history retained");
    prerequisites(input, secret, current.head);
    await this.drift(path, secret, current);
    const refs: VersionRef[] = [], deadline = Date.now() + 30000;
    for (const selection of input.histories) {
      if (signal?.aborted || Date.now() >= deadline) throw new KvError(408, "History cleanup stopped before reference mutation");
      const history = await this.transport.read(this.registry.config.historyNamespace, selection.name), ref = historyReference(history.metadata, path, current.sourceUid);
      if (!ref || history.metadata?.namespace !== this.registry.config.historyNamespace || ref.uid !== selection.uid || nativeIdentity(history).resourceVersion !== selection.resourceVersion ||
        Date.now() - Date.parse(ref.createdAt) < 86400000 || state.paths.some(p => p.versions.some(v => v.uid === ref.uid || v.name === ref.name)))
        throw new KvError(409, "History is referenced, too recent or ownership changed; retained");
      const operation = await this.registry.db.kvOperation.findUnique({ where: { id: ref.operationId } });
      if (!operation || operation.pathId !== path.id || operation.mountId !== path.mountId || operation.path !== path.path ||
        operation.namespace !== path.namespace || operation.name !== path.name || operation.newVersion !== ref.version ||
        !["adopt", "create", "update", "delete", "rollback", "reconcile", "rotate"].includes(operation.action))
        throw new KvError(409, "History operation ownership unavailable; retained");
      historyValues(history, path, current.sourceUid, ref); refs.push(ref);
    }
    await this.registry.admin(actor);
    if (signal?.aborted || Date.now() >= deadline) throw new KvError(408, "History cleanup stopped before reference mutation");
    // This source CAS fences any older in-flight canonical commit before its candidates are deleted.
    const result = await this.detachHistory(actor, path, secret, current, [], true), cleanup = [];
    for (let index = 0; index < refs.length; index++) cleanup.push(signal?.aborted || Date.now() >= deadline ? { name: refs[index].name, status: 408, outcome: "retained" } :
      await this.cleanupHistory(actor, path, current.sourceUid, refs[index], result.operationId, input.histories[index], true));
    return { ...result, cleanupComplete: cleanup.every(item => ["deleted", "absent"].includes(item.outcome)), cleanup };
  }

  async resolve(actor: KvActor, id: string, action: "list" | "rotate" = "list") {
    const operation = await this.registry.db.kvOperation.findUnique({ where: { id } });
    if (!operation) throw new KvError(404, "KV operation not found");
    const path = await this.permitted(actor, operation.pathId, action);
    if (!["pending", "ambiguous", "recovery-required"].includes(operation.outcome)) return operation;
    try {
      const secret = await this.canonical(path), current = ownedPath(secret, path), proof = current?.operations.find(op => op.id === id);
      if (proof && proof.action === operation.action && proof.newVersion === operation.newVersion && await this.finish(operation, "committed"))
        return { ...operation, outcome: "committed" };
    } catch { /* Missing/unreachable/replaced state never proves failure or permits deletion. */ }
    return { ...operation, outcome: operation.outcome === "pending" ? "ambiguous" : operation.outcome };
  }
}
