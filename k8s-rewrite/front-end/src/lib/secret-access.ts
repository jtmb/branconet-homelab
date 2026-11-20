import { KvError, policyAllows, type KvActor } from "./kv-contract";
import { KvRegistry } from "./kv-registry";
import type { NativeSecretTransport } from "./secret-client";
import type { FlatSecretGuard } from "./cluster-secrets";
import { equalValues, historyValues, ownedPath, parseState, selectedValues } from "./kv-native-state";
import type { Prisma } from "@prisma/client";

export async function requireLegacyPrincipal(registry: KvRegistry, client: Pick<Prisma.TransactionClient,"kvServicePrincipal"> = registry.db) {
  const principal = await client.kvServicePrincipal.findUnique({ where: { id: "legacy-lookup" } });
  if (!principal?.enabled) throw new KvError(403, "Legacy lookup principal is disabled");
}

export function flatSecretGuard(registry: KvRegistry, transport: NativeSecretTransport, actor: () => Promise<KvActor | null>, legacyAlias?: string): FlatSecretGuard {
  return async (action, target, secret) => {
    if (target.namespace === registry.config.historyNamespace) throw new KvError(403, "Engine history requires an explicit authorized KV endpoint");
    const human = legacyAlias === undefined ? await actor() : null;
    if (legacyAlias === undefined) {
      if (!human) throw new KvError(401, "Authentication required");
      await registry.admin(human);
    } else {
      if (action !== "read") throw new KvError(403, "Legacy lookup has current-read audience only");
      await requireLegacyPrincipal(registry);
    }
    const mapping = await registry.db.kvField.findUnique({ where: { namespace_name_key: { namespace: target.namespace, name: target.name, key: target.key } } });
    const nativeOwner = secret && parseState(secret).paths.find(p => p.fields.some(f => f.key === target.key));
    // Unadopted references retain the old contract. Native markers cannot disappear into DB fallback.
    if (!nativeOwner) {
      if (mapping && await registry.db.kvOperation.count({ where: { pathId: mapping.pathId, outcome: "committed" } }))
        throw new KvError(409, "Native KV ownership marker is missing; explicit recovery required");
      return;
    }
    if (!mapping || mapping.pathId !== nativeOwner.id) throw new KvError(503, "Native KV mapping metadata unavailable; restore metadata before access");
    const path = await registry.path(mapping.pathId), current = ownedPath(secret!, path)!;
    if (legacyAlias !== undefined) {
      const grant = await registry.db.kvLegacyGrant.findUnique({ where: { pathId_alias: { pathId: path.id, alias: legacyAlias } } });
      if (!grant || grant.namespace !== target.namespace || grant.name !== target.name || grant.key !== target.key)
        throw new KvError(403, "Legacy alias has no exact adopted-key grant");
      const rules = await registry.rules("legacy-lookup");
      if (!policyAllows([{ mountId: path.mountId, prefix: path.path, effect: "allow", actions: '["read"]' }, ...rules], path, "read"))
        throw new KvError(403, "Legacy lookup policy denies this adopted path");
    } else await registry.authorize(human!, path, action === "read" ? "read" : action === "delete" ? "delete" : "update");
    if (action !== "read") throw new KvError(409, "Adopted native keys require the versioned KV mutation endpoint");
    const ref = current.versions.find(v => v.version === current.head);
    const headValues = ref ? historyValues(await transport.read(registry.config.historyNamespace, ref.name), path, current.sourceUid, ref) : {};
    if (!equalValues(headValues, selectedValues(secret!, path))) throw new KvError(409, "Selected native values changed externally; reconcile explicitly");
    await registry.serialized(async tx => {
    if (legacyAlias !== undefined) {
      await requireLegacyPrincipal(registry,tx);
      // Recheck exact grants/denies after the native read, before returning any value.
      const grant = await tx.kvLegacyGrant.findUnique({ where: { pathId_alias: { pathId: path.id, alias: legacyAlias } } });
      if (!grant || grant.namespace !== target.namespace || grant.name !== target.name || grant.key !== target.key ||
        !policyAllows([{ mountId: path.mountId, prefix: path.path, effect: "allow", actions: '["read"]' }, ...await registry.rules("legacy-lookup",tx)], path, "read"))
        throw new KvError(403, "Legacy lookup grant revoked");
    } else { await registry.admin(human!,tx); await registry.authorize(human!, path, "read",tx); }
    await tx.kvAudit.create({data:{actorId:legacyAlias===undefined ? human!.id : "legacy-lookup",pathId:path.id,mountId:path.mountId,path:path.path,namespace:path.namespace,name:path.name,action:legacyAlias===undefined ? "flat-read" : "legacy-read",previousVersion:current.head,newVersion:current.head,outcome:"authorized"}});
    });
  };
}
