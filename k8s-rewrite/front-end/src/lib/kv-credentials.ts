import { createHash, randomBytes, randomUUID, timingSafeEqual } from "node:crypto";

export function credentialHash(credential: string): string {
  return createHash("sha256").update(credential).digest("hex");
}
export function issueCredential() {
  const id = randomUUID();
  const credential = `bortus_kv_v1_${id}_${randomBytes(32).toString("base64url")}`;
  return { id, credential, hash: credentialHash(credential) };
}
export function presentedCredential(header: string | null): { id: string; hash: string } | null {
  const match = header?.match(/^Bearer (bortus_kv_v1_([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})_[A-Za-z0-9_-]{43})$/);
  return match ? { id: match[2], hash: credentialHash(match[1]) } : null;
}
export function hashMatches(a: string, b: string): boolean {
  return /^[a-f0-9]{64}$/.test(a) && /^[a-f0-9]{64}$/.test(b) && timingSafeEqual(Buffer.from(a, "hex"), Buffer.from(b, "hex"));
}
