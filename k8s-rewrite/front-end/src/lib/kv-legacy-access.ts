import { createHash } from "node:crypto";
import type { Prisma, KvPolicy } from "@prisma/client";
import type { KvRegistry, PolicyInput } from "./kv-registry";
import { KvError, metadataRevision, policyAllows, type KvActor } from "./kv-contract";
import { MAX_ALIASES, readAliasFile } from "./alias-catalog";
import { mergeAliases, validateAlias, type SecretAlias } from "./secret-aliases";

type Client = Prisma.TransactionClient;
export type LegacyAcknowledgement = { fingerprint: string; aliases: string[]; confirmLegacyImpact: true; confirmConfigurationImpact?: true };
export type LegacyChange =
  | { kind: "principal"; enabled: boolean; revision?: number }
  | { kind: "grant"; pathId: string; pathRevision?: number; alias: string; revision?: number }
  | { kind: "revoke"; grantId: string; revision?: number }
  | { kind: "policy"; input: PolicyInput | null; previous: KvPolicy | null };
type Binding = { pathId: string; mountId: string; path: string; revision: number; mountRevision: number; scopeAllowed: boolean };
type Grant = { id: string; pathId: string; alias: string; namespace: string; name: string; key: string };
const grantSelect = { id: true, pathId: true, alias: true, namespace: true, name: true, key: true } as const;

export async function readLegacyAliases(client: Client): Promise<SecretAlias[]> {
  const controller = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const file = await Promise.race([readAliasFile(process.env.BORTUS_SECRET_ALIASES_FILE || "", controller.signal), new Promise<never>((_, reject) => {
      timer = setTimeout(() => { controller.abort(); reject(new KvError(503, "Legacy alias metadata timed out")); }, 5000);
    })]);
    clearTimeout(timer);
    const rows = await client.secretReference.findMany({ take: MAX_ALIASES + 1, select: { alias: true, namespace: true, name: true, key: true } });
    if (rows.length > MAX_ALIASES) throw Error();
    const aliases = mergeAliases([file, rows]);
    if (aliases.length > MAX_ALIASES) throw Error();
    return aliases;
  } catch { throw new KvError(503, "Legacy alias metadata is unavailable or invalid"); }
  finally { clearTimeout(timer); controller.abort(); }
}

const tuple = (ref: SecretAlias) => JSON.stringify([ref.namespace, ref.name, ref.key]);
const grantId = (pathId: string, alias: string) => JSON.stringify([pathId, alias]);
const matches = (grant: Grant | undefined, ref: SecretAlias) => !!grant && grant.namespace === ref.namespace && grant.name === ref.name && grant.key === ref.key;
const targets = (rule: Pick<PolicyInput, "principal" | "mountId" | "prefix"> & { actions: readonly string[] }, binding: Binding) => rule.principal === "legacy-lookup" && rule.actions.includes("read") &&
  (!rule.mountId || rule.mountId === binding.mountId) && (!rule.prefix || binding.path === rule.prefix || binding.path.startsWith(rule.prefix + "/"));
const policyMetadata = (rule: KvPolicy | null) => rule && ({ id: rule.id, principal: rule.principal, mountId: rule.mountId, prefix: rule.prefix, effect: rule.effect, actions: rule.actions, revision: rule.revision });

export async function legacyImpact(registry: KvRegistry, client: Client, change: LegacyChange) {
  const principal = await client.kvServicePrincipal.findUnique({ where: { id: "legacy-lookup" } });
  if (!principal) throw new KvError(503, "Legacy principal metadata unavailable");
  if (change.kind !== "policy" && principal.revision !== metadataRevision(change.revision)) throw new KvError(409, "Legacy principal changed; refresh before editing");
  if (change.kind === "principal" && (typeof change.enabled !== "boolean" || change.enabled === principal.enabled)) throw new KvError(400, "Choose a changed legacy principal state");
  const rawAliases = await registry.legacyAliases(client);
  if (!Array.isArray(rawAliases) || rawAliases.length > MAX_ALIASES) throw new KvError(503, "Legacy alias metadata exceeds the limit");
  const aliases = mergeAliases([rawAliases.map(validateAlias)]).sort((a, b) => a.alias < b.alias ? -1 : a.alias > b.alias ? 1 : 0);
  const bindings = new Map<string, Binding>(), grants = new Map<string, Grant>();
  const mounts = new Map<string, { id: string; revision: number; namespaces: string[] }>();
  const scoped = aliases.filter(ref => registry.namespaces.includes(ref.namespace) && ref.namespace !== registry.config.historyNamespace);
  const uniqueTargets = [...new Map(scoped.map(ref => [tuple(ref), ref])).values()];
  // Small exact indexed batches avoid both a global field scan and SQLite parameter overflow.
  for (let offset = 0; offset < uniqueTargets.length; offset += 100) {
    const rows = await client.kvField.findMany({ where: { OR: uniqueTargets.slice(offset, offset + 100).map(({ namespace, name, key }) => ({ namespace, name, key })) },
      select: { namespace: true, name: true, key: true, path: { select: { id: true, mountId: true, path: true, revision: true, namespace: true, name: true,
        mount: { select: { revision: true, namespaces: true } } } } }, take: 101 });
    if (rows.length > 100) throw new KvError(503, "Legacy mapping metadata exceeds the limit");
    for (const row of rows) {
      if (row.path.namespace !== row.namespace || row.path.name !== row.name) throw new KvError(503, "Legacy mapping metadata unavailable");
      const namespaces = registry.allowedNamespaces(JSON.parse(row.path.mount.namespaces)).sort();
      mounts.set(row.path.mountId, { id: row.path.mountId, revision: row.path.mount.revision, namespaces });
      bindings.set(tuple({ ...row, alias: "validation" }), { pathId: row.path.id, mountId: row.path.mountId, path: row.path.path, revision: row.path.revision,
        mountRevision: row.path.mount.revision, scopeAllowed: namespaces.includes(row.namespace) });
    }
  }
  const requested = scoped.flatMap(ref => { const binding = bindings.get(tuple(ref)); return binding ? [{ pathId: binding.pathId, alias: ref.alias }] : []; });
  for (let offset = 0; offset < requested.length; offset += 100) {
    const rows = await client.kvLegacyGrant.findMany({ where: { OR: requested.slice(offset, offset + 100) }, select: grantSelect, take: 101 });
    if (rows.length > 100) throw new KvError(503, "Legacy grant metadata exceeds the limit");
    for (const row of rows) grants.set(grantId(row.pathId, row.alias), row);
  }
  let selectedGrant: Grant | null = null, grantBinding: Binding | undefined;
  if (change.kind === "grant") {
    const path = await registry.path(change.pathId, client), ref = aliases.find(ref => ref.alias === change.alias);
    if (path.revision !== metadataRevision(change.pathRevision)) throw new KvError(409, "KV path changed; refresh before granting access");
    if (!ref || ref.namespace !== path.namespace || ref.name !== path.name || !path.fields.some(field => field.key === ref.key)) throw new KvError(409, "Alias must resolve to an exact registered path key");
    if (!await client.kvOperation.findFirst({ where: { pathId: path.id, outcome: "committed" }, select: { id: true } })) throw new KvError(409, "Legacy grants require a previously committed native path");
    if (grants.has(grantId(path.id, ref.alias))) throw new KvError(409, "Legacy grant already exists; revoke it explicitly before replacement");
    selectedGrant = { id: "new-grant", pathId: path.id, ...ref }; grantBinding = bindings.get(tuple(ref));
  } else if (change.kind === "revoke") {
    selectedGrant = await client.kvLegacyGrant.findUnique({ where: { id: change.grantId }, select: grantSelect });
    if (!selectedGrant) throw new KvError(404, "Legacy grant not found");
  }
  const beforeRules = await registry.rules("legacy-lookup", client), afterRules = beforeRules.filter(rule => change.kind !== "policy" || (rule as KvPolicy).id !== change.previous?.id);
  if (change.kind === "policy" && change.input?.principal === "legacy-lookup") afterRules.push({ ...change.input, actions: JSON.stringify(change.input.actions) });
  const afterEnabled = change.kind === "principal" ? change.enabled : principal.enabled;
  const rows = aliases.map(ref => {
    const binding = bindings.get(tuple(ref)), existing = binding ? grants.get(grantId(binding.pathId, ref.alias)) : undefined;
    const allowedScope = registry.namespaces.includes(ref.namespace) && ref.namespace !== registry.config.historyNamespace && (!binding || binding.scopeAllowed);
    const policyBefore = !binding || policyAllows([{ mountId: binding.mountId, prefix: binding.path, effect: "allow", actions: '["read"]' }, ...beforeRules], { mountId: binding.mountId, path: binding.path }, "read");
    const policyAfter = !binding || policyAllows([{ mountId: binding.mountId, prefix: binding.path, effect: "allow", actions: '["read"]' }, ...afterRules], { mountId: binding.mountId, path: binding.path }, "read");
    const exactBefore = !binding || matches(existing, ref);
    const exactAfter = change.kind === "grant" && selectedGrant?.alias === ref.alias ? matches(selectedGrant, ref) :
      change.kind === "revoke" && existing?.id === selectedGrant?.id ? false : exactBefore;
    return { ...ref, pathId: binding?.pathId ?? null, path: binding?.path ?? null, pathRevision: binding?.revision ?? null, mountRevision: binding?.mountRevision ?? null, grantId: existing?.id ?? null,
      basis: !allowedScope ? "outside-scope" : !binding ? "unregistered-alias" : "registered-path-metadata",
      beforeAllowed: allowedScope && principal.enabled && exactBefore && policyBefore,
      afterAllowed: allowedScope && afterEnabled && exactAfter && policyAfter };
  });
  let affected = rows.filter(row => {
    if (change.kind === "principal") return true;
    if (change.kind === "grant" || change.kind === "revoke") return row.alias === selectedGrant?.alias;
    const binding = bindings.get(tuple(row)); if (!binding) return false;
    return !!change.input && targets(change.input, binding) || !!change.previous && targets({ ...change.previous, actions: JSON.parse(change.previous.actions) }, binding);
  });
  if (change.kind === "revoke" && selectedGrant && !affected.length) affected = [{ alias: selectedGrant.alias, namespace: selectedGrant.namespace, name: selectedGrant.name, key: selectedGrant.key,
    pathId: selectedGrant.pathId, path: null, pathRevision: null, mountRevision: null, grantId: selectedGrant.id, basis: "unresolved-alias", beforeAllowed: false, afterAllowed: false }];
  const normalized = change.kind === "policy" ? { kind: change.kind, input: change.input && { principal: change.input.principal, mountId: change.input.mountId,
    prefix: change.input.prefix, effect: change.input.effect, actions: [...change.input.actions].sort() }, previous: policyMetadata(change.previous) } :
    change.kind === "principal" ? { kind: change.kind, enabled: change.enabled, revision: change.revision } :
    change.kind === "grant" ? { kind: change.kind, pathId: change.pathId, pathRevision: change.pathRevision, alias: change.alias, revision: change.revision } :
    { kind: change.kind, grantId: change.grantId, revision: change.revision };
  // This digest covers authorization metadata only; no native request/value/digest enters it.
  const fingerprint = createHash("sha256").update(JSON.stringify({ change: normalized, principal, rules: beforeRules.map(rule => policyMetadata(rule as KvPolicy)).sort((a, b) => a!.id.localeCompare(b!.id)),
    mounts: [...mounts.values()].sort((a, b) => a.id.localeCompare(b.id)), rows, selectedGrant, grantBinding })).digest("hex");
  return { fingerprint, principal, affected, selectedGrant, nonsecretConfigurationAffected: change.kind === "principal",
    boundary: "Authorization metadata preview only; native ownership, head, drift, key presence, alias/config collisions and availability are checked independently at lookup. External alias-file changes cannot be transacted with SQLite." };
}

export function legacyImpactPage(impact: Awaited<ReturnType<typeof legacyImpact>>, cursor?: string) {
  if (cursor !== undefined && !/^[a-zA-Z0-9_.:/-]{1,253}$/.test(cursor)) throw new KvError(400, "Invalid legacy impact cursor");
  const rows = impact.affected.filter(row => cursor === undefined || row.alias > cursor);
  return { required: true as const, fingerprint: impact.fingerprint, revision: impact.principal.revision, affectedAliasCount: impact.affected.length,
    items: rows.slice(0, 100), nextCursor: rows.length > 100 ? rows[99].alias : null,
    selectedGrant: impact.selectedGrant && { ...impact.selectedGrant, id: impact.selectedGrant.id === "new-grant" ? null : impact.selectedGrant.id },
    nonsecretConfigurationAffected: impact.nonsecretConfigurationAffected, boundary: impact.boundary };
}

export function acknowledgeLegacyImpact(impact: Awaited<ReturnType<typeof legacyImpact>>, acknowledgement?: LegacyAcknowledgement) {
  if (!acknowledgement) throw new KvError(428, "Preview and acknowledge the exact legacy alias impact before changing access");
  if (acknowledgement.confirmLegacyImpact !== true || !Array.isArray(acknowledgement.aliases) || acknowledgement.aliases.length > MAX_ALIASES ||
    new Set(acknowledgement.aliases).size !== acknowledgement.aliases.length || !/^[a-f0-9]{64}$/.test(acknowledgement.fingerprint)) throw new KvError(400, "Invalid legacy impact acknowledgement");
  if (impact.nonsecretConfigurationAffected && acknowledgement.confirmConfigurationImpact !== true) throw new KvError(400, "Acknowledge that the principal controls nonsecret legacy lookup too");
  const selected = [...acknowledgement.aliases].sort();
  if (acknowledgement.fingerprint !== impact.fingerprint || selected.length !== impact.affected.length || impact.affected.some((row, index) => row.alias !== selected[index]))
    throw new KvError(409, "Legacy alias impact changed; preview and acknowledge again");
}

export class KvLegacyAccess {
  constructor(readonly registry: KvRegistry) {}
  state(actor: KvActor) { return this.registry.serialized(async tx => {
    await this.registry.admin(actor, tx); const principal = await tx.kvServicePrincipal.findUnique({ where: { id: "legacy-lookup" } });
    if (!principal) throw new KvError(503, "Legacy principal metadata unavailable");
    return { ...principal, grantCount: await tx.kvLegacyGrant.count(), audience: "legacy current lookup only", includesNonsecretConfiguration: true };
  }); }
  grants(actor: KvActor, cursor?: string) { return this.registry.serialized(async tx => {
    await this.registry.admin(actor, tx);
    const rows = await tx.kvLegacyGrant.findMany({ where: cursor ? { id: { gt: cursor } } : {}, orderBy: { id: "asc" }, select: grantSelect, take: 101 });
    return { items: rows.slice(0, 100), nextCursor: rows.length > 100 ? rows[99].id : null };
  }); }
  preview(actor: KvActor, change: Exclude<LegacyChange, { kind: "policy" }>, cursor?: string) { return this.registry.serialized(async tx => {
    await this.registry.admin(actor, tx); return legacyImpactPage(await legacyImpact(this.registry, tx, change), cursor);
  }); }
  commit(actor: KvActor, change: Exclude<LegacyChange, { kind: "policy" }>, acknowledgement?: LegacyAcknowledgement) { return this.registry.serialized(async tx => {
    await this.registry.admin(actor, tx);
    const impact = await legacyImpact(this.registry, tx, change); acknowledgeLegacyImpact(impact, acknowledgement);
    let grant = impact.selectedGrant;
    if (change.kind === "principal") await tx.kvServicePrincipal.update({ where: { id: "legacy-lookup" }, data: { enabled: change.enabled } });
    else if (change.kind === "grant") { const { id: _id, ...data } = impact.selectedGrant!; grant = await tx.kvLegacyGrant.create({ data, select: grantSelect }); }
    else await tx.kvLegacyGrant.delete({ where: { id: change.grantId } });
    const principal = await tx.kvServicePrincipal.update({ where: { id: "legacy-lookup" }, data: { revision: { increment: 1 } } });
    await tx.kvAudit.create({ data: { actorId: actor.id, action: "legacy-" + change.kind, pathId: impact.selectedGrant?.pathId ?? null,
      namespace: impact.selectedGrant?.namespace ?? null, name: impact.selectedGrant?.name ?? null, principal: "legacy-lookup",
      alias: impact.selectedGrant?.alias ?? null, key: impact.selectedGrant?.key ?? null, outcome: "committed" } });
    return { success: true, principal, grant, affectedAliasCount: impact.affected.length };
  }); }
}
