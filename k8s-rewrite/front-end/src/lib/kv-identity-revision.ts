import { createHash } from "node:crypto";
import { KvError } from "./kv-contract";

type IdentitySnapshot = {
  id: string; ownerId: string; name: string;
  expiresAt: Date; revokedAt: Date | null; createdAt: Date;
};

/** Opaque public-metadata content revision, not a credential or a schema counter.
 * Identities have no edit/unrevoke API; revocation is their only state transition.
 * Authority (owner/session/role/policy) is checked separately on every use.
 */
export function identityRevision(identity: IdentitySnapshot): string {
  return createHash("sha256").update(JSON.stringify([
    "bortus-identity-revision/v1", identity.id, identity.ownerId, identity.name,
    identity.expiresAt.toISOString(), identity.revokedAt?.toISOString() ?? null,
    identity.createdAt.toISOString(),
  ])).digest("hex");
}

export function expectedIdentityRevision(value: unknown): string {
  if (value === undefined) throw new KvError(428, "Identity revision required");
  if (typeof value !== "string" || !/^[a-f0-9]{64}$/.test(value))
    throw new KvError(400, "Invalid identity revision");
  return value;
}
