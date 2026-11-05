import type { KvRotation, Prisma } from "@prisma/client";
import { KvError, KvMutationError, metadataRevision, requireGuarded, type KvActor } from "./kv-contract";
import type { KvNativeEngine, NativePrerequisites } from "./kv-native-engine";
import { validateTarget } from "./cluster-secrets";
import type { ConsumerMetadata, RotationConsumerTransport } from "./kv-rotation-consumer";

export type RotationConsumer = { kind: "Deployment" | "StatefulSet" | "DaemonSet"; namespace: string; name: string };
export type RotationPrepare = { pathId: string; pathRevision: number; field: string; consumer: RotationConsumer };
type Client = Prisma.TransactionClient;
const closed = ["acknowledged", "cancelled"];

/** Static native replacements only; every persisted/returned field is workflow metadata. */
export class KvRotations {
  constructor(readonly engine: KvNativeEngine, readonly consumer?: RotationConsumerTransport) {}
  get registry() { return this.engine.registry; }
  async row(actor: KvActor, id: string, client: Client = this.registry.db) {
    const row = await client.kvRotation.findUnique({ where: { id } });
    if (!row) throw new KvError(404, "Rotation intent not found");
    const path = await this.registry.path(row.pathId, client);
    await this.registry.authorize(actor, path, "rotate", client);
    return { row, path };
  }
  async list(actor: KvActor, pathId: string, cursor?: string) {
    const path = await this.registry.path(pathId);
    await this.registry.authorize(actor, path, "list");
    const rows = await this.registry.db.kvRotation.findMany({ where: { pathId, ...(cursor ? { id: { gt: cursor } } : {}) }, orderBy: { id: "asc" }, take: 101 });
    await this.registry.authorize(actor, path, "list");
    return { items: rows.slice(0, 100), nextCursor: rows.length > 100 ? rows[99].id : null, acknowledgement: "explicit operator assertion; consumer consumption is not independently verified" };
  }
  async prepare(actor: KvActor, input: RotationPrepare) {
    requireGuarded(this.registry.config);
    if (!["Deployment", "StatefulSet", "DaemonSet"].includes(input.consumer.kind)) throw new KvError(400, "Unsupported rotation consumer");
    validateTarget({ namespace: input.consumer.namespace, name: input.consumer.name, key: "consumer" });
    return this.registry.serialized(async tx => {
      const path = await this.registry.path(input.pathId, tx);
      await this.registry.authorize(actor, path, "rotate", tx);
      if (metadataRevision(input.pathRevision) !== path.revision) throw new KvError(409, "Path metadata changed; refresh before preparing rotation");
      if (input.consumer.namespace !== path.namespace || !path.fields.some(mapping => mapping.field === input.field)) throw new KvError(400, "Explicit mapped field and same-namespace consumer required");
      if (await tx.kvRotation.findFirst({ where: { pathId: path.id, field: input.field, state: { notIn: closed } } })) throw new KvError(409, "This field has an unfinished rotation; inspect its outcome first");
      if (await tx.kvRotation.count({ where: { pathId: path.id } }) >= 1000) throw new KvError(413, "Rotation metadata limit reached");
      const row = await tx.kvRotation.create({ data: { pathId: path.id, actorId: actor.identityId || actor.id, field: input.field,
        consumerKind: input.consumer.kind, consumerNamespace: input.consumer.namespace, consumerName: input.consumer.name } });
      await this.audit(tx, actor, row, "rotation-prepare", "prepare");
      return row;
    });
  }
  async generate(actor: KvActor, id: string, input: NativePrerequisites & { revision: number; confirmPath: string }) {
    const { row, path } = await this.row(actor, id);
    this.confirm(row, input.revision, input.confirmPath, path.path);
    if (row.state !== "prepare" || row.operationId) throw new KvError(409, "Rotation already attempted; inspect its linked operation instead of regenerating");
    const result = await this.engine.rotate(actor, path.id, { ...input, rotationId: id, field: row.field });
    return { ...result, rotation: (await this.row(actor, id)).row, replacement: "32 random bytes encoded as a static base64url UTF-8 string; value available only through separately authorized native reads" };
  }
  async acknowledge(actor: KvActor, id: string, input: NativePrerequisites & { revision: number; confirmPath: string; confirmConsumer: string; confirmConsumption: true }) {
    const { row, path } = await this.row(actor, id);
    this.confirm(row, input.revision, input.confirmPath, path.path);
    if (!row.operationId || !["awaiting-ack", "reload-requested"].includes(row.state)) throw new KvError(409, "Rotation has no committed replacement awaiting acknowledgement");
    if (input.confirmConsumption !== true || input.confirmConsumer !== this.consumerName(row)) throw new KvError(400, "Exact consumer confirmation and explicit consumption acknowledgement required");
    const proof = await this.engine.rotationProof(actor, path.id, row.operationId, input);
    const rotation = await this.registry.serialized(async tx => {
      const fresh = await this.row(actor, id, tx);
      this.confirm(fresh.row, input.revision, input.confirmPath, fresh.path.path);
      if (!fresh.row.operationId || !["awaiting-ack", "reload-requested"].includes(fresh.row.state)) throw new KvError(409, "Rotation state changed; refresh before acknowledgement");
      const operation = await tx.kvOperation.findUnique({ where: { id: fresh.row.operationId } });
      if (operation?.outcome !== "committed" || operation.newVersion !== proof.head) throw new KvError(409, "Native rotation outcome requires recovery");
      const updated = await tx.kvRotation.update({ where: { id }, data: { state: "acknowledged", revision: { increment: 1 } } });
      await this.audit(tx, actor, updated, "rotation-ack", "operator-acknowledged");
      return updated;
    });
    return { rotation, observedHead: proof.head, acknowledgement: "operator assertion; consumer consumption is not independently verified" };
  }
  async resolve(actor: KvActor, id: string) {
    let { row } = await this.row(actor, id);
    if (row.operationId) await this.engine.resolve(actor, row.operationId, "rotate");
    row = (await this.row(actor, id)).row;
    if (row.state === "reload-pending") {
      await this.registry.admin(actor);
      if (!this.consumer || !row.consumerUid || !row.operationId) throw new KvError(503, "Consumer reload recovery metadata unavailable; intent retained");
      const metadata = await this.consumer.inspect(row);
      if (metadata.uid === row.consumerUid && metadata.rotationId === row.id) await this.reloadFinished(actor, row, metadata);
    }
    return { rotation: (await this.row(actor, id)).row, recovery: "Positive native operation proof only; no regeneration or blind native retry" };
  }
  async consumerPreview(actor: KvActor, id: string) {
    await this.registry.admin(actor);
    const { row } = await this.row(actor, id);
    if (!this.consumer) throw new KvError(501, "Named consumer reload is unavailable");
    const metadata = await this.consumer.inspect(row);
    await this.registry.admin(actor);
    await this.row(actor, id);
    const { rotationId: rotationIdMarker, ...identity } = metadata;
    return { rotationId: id, revision: row.revision, consumer: this.consumerName(row), ...identity, ...(rotationIdMarker ? { rotationIdMarker } : {}), reload: "explicit request only; Flux may reconcile the annotation back" };
  }
  async reload(actor: KvActor, id: string, input: NativePrerequisites & { revision: number; confirmPath: string; confirmConsumer: string; consumerUid: string; consumerResourceVersion: string }, signal?: AbortSignal) {
    requireGuarded(this.registry.config);
    await this.registry.admin(actor);
    const { row, path } = await this.row(actor, id);
    this.confirm(row, input.revision, input.confirmPath, path.path);
    if (!this.consumer) throw new KvError(501, "Named consumer reload is unavailable");
    if (row.state !== "awaiting-ack" || !row.operationId) throw new KvError(409, "Reload requires a committed replacement; pending requests must be inspected instead of retried");
    if (input.confirmConsumer !== this.consumerName(row) || !input.consumerUid || input.consumerUid.length > 128 || !input.consumerResourceVersion || input.consumerResourceVersion.length > 128) throw new KvError(400, "Exact named consumer and displayed UID/resourceVersion required");
    await this.engine.rotationProof(actor, path.id, row.operationId, input);
    const metadata = await this.consumer.inspect(row);
    if (metadata.uid !== input.consumerUid || metadata.resourceVersion !== input.consumerResourceVersion) throw new KvError(409, "Consumer changed; refresh before reload");
    if (signal?.aborted) throw new KvError(408, "Consumer reload stopped before intent reservation");
    const pending = await this.registry.serialized(async tx => {
      await this.registry.admin(actor, tx);
      const fresh = await this.row(actor, id, tx);
      this.confirm(fresh.row, input.revision, input.confirmPath, fresh.path.path);
      if (fresh.row.state !== "awaiting-ack" || fresh.row.operationId !== row.operationId) throw new KvError(409, "Rotation changed; reload was not requested");
      const updated = await tx.kvRotation.update({ where: { id }, data: { state: "reload-pending", consumerUid: input.consumerUid,
        consumerResourceVersion: input.consumerResourceVersion, revision: { increment: 1 } } });
      await this.audit(tx, actor, updated, "rotation-reload", "pending");
      return updated;
    });
    try {
      await this.registry.admin(actor);
      await this.row(actor, id);
      if (signal?.aborted) throw new KvError(408, "Consumer reload stopped after intent reservation");
      const result = await this.consumer.reload(pending, metadata);
      return { rotation: await this.reloadFinished(actor, pending, result), reload: "template annotation requested; workload readiness/consumption is not independently verified" };
    } catch {
      // One positive read-back can resolve a timed-out patch. Never repeat the patch.
      try { await this.registry.admin(actor); await this.row(actor, id); const result = await this.consumer.inspect(pending);
        if (result.uid === pending.consumerUid && result.rotationId === pending.id) return { rotation: await this.reloadFinished(actor, pending, result), reload: "positive consumer marker read-back; consumption is not independently verified" };
      } catch { /* Lost permissions, changed UID, audit outage or missing marker retain intent. */ }
      throw new KvMutationError(503, "Consumer reload outcome requires recovery; inspect rotation before further action", pending.operationId!, "recovery-required");
    }
  }
  private async reloadFinished(actor: KvActor, pending: KvRotation, metadata: ConsumerMetadata) {
    if (metadata.uid !== pending.consumerUid || metadata.rotationId !== pending.id) throw new KvError(503, "Consumer reload marker cannot be verified");
    return this.registry.serialized(async tx => {
      await this.registry.admin(actor, tx);
      const fresh = await this.row(actor, pending.id, tx);
      if (fresh.row.state !== "reload-pending" || fresh.row.revision !== pending.revision || fresh.row.consumerUid !== metadata.uid) throw new KvError(409, "Consumer reload metadata changed; inspect its outcome");
      const updated = await tx.kvRotation.update({ where: { id: pending.id }, data: { state: "reload-requested", revision: { increment: 1 } } });
      await this.audit(tx, actor, updated, "rotation-reload", "marker-verified");
      return updated;
    });
  }
  async cancel(actor: KvActor, id: string, revision: number, confirmPath: string) {
    return this.registry.serialized(async tx => {
      const { row, path } = await this.row(actor, id, tx);
      this.confirm(row, revision, confirmPath, path.path);
      if (row.state !== "prepare" && row.state !== "conflict") throw new KvError(409, "Attempted or committed rotation requires explicit recovery; cancellation cannot undo native values");
      if (row.operationId && (row.state !== "conflict" || (await tx.kvOperation.findUnique({ where: { id: row.operationId } }))?.outcome !== "conflict")) throw new KvError(409, "Rotation outcome is unresolved; intent retained");
      const updated = await tx.kvRotation.update({ where: { id }, data: { state: "cancelled", revision: { increment: 1 } } });
      await this.audit(tx, actor, updated, "rotation-cancel", "cancelled");
      return updated;
    });
  }
  confirm(row: KvRotation, revision: number, confirmPath: string, path: string) {
    if (metadataRevision(revision) !== row.revision) throw new KvError(409, "Rotation metadata changed; refresh before retrying");
    if (confirmPath !== path) throw new KvError(400, "Exact logical path confirmation required");
  }
  consumerName(row: KvRotation) { return `${row.consumerNamespace}/${row.consumerKind}/${row.consumerName}`; }
  async audit(tx: Client, actor: KvActor, row: KvRotation, action: string, outcome: string) {
    const path = await this.registry.path(row.pathId, tx);
    await tx.kvAudit.create({ data: { actorId: actor.identityId || actor.id, operationId: row.operationId, pathId: path.id, mountId: path.mountId, path: path.path,
      namespace: path.namespace, name: path.name, action, outcome } });
  }
}
