import { createHmac, timingSafeEqual } from "node:crypto";
import type { Hmac } from "node:crypto";
import type { TransformOptions } from "node:stream";
import { base64url, decodeProtectedHeader, UnsecuredJWT } from "jose";
import type { JWTPayload, ProtectedHeaderParameters } from "jose";

// Node22.23.3 supports opaque CryptoKey directly. Retained @types/node22.20.5
// omits that supported input; this declaration has no runtime conversion or export.
declare module "crypto" {
  function createHmac(algorithm: string, key: CryptoKey, options?: TransformOptions): Hmac;
}

const refusal = () => new Error("JWT verification unavailable");
const CLAIMS_ONLY_HEADER = "eyJhbGciOiJub25lIn0";
const text = new TextDecoder();

/** Fixed current-application HS256 profile; unsigned external tokens never authenticate. */
export function verifyHS256Profile(
  input: string | Uint8Array,
  key: CryptoKey
): { payload: JWTPayload; protectedHeader: ProtectedHeaderParameters } {
  let digest: Buffer | undefined;
  try {
    const token = input instanceof Uint8Array ? text.decode(input) : input;
    if (typeof token !== "string") throw refusal();
    const parts = token.split(".");
    if (parts.length !== 3) throw refusal();
    const header = decodeProtectedHeader(token);
    if (header.alg !== "HS256") throw refusal();
    const crit = header.crit;
    if (crit !== undefined) {
      if (!Array.isArray(crit) || crit.length === 0 ||
        crit.some(name => typeof name !== "string" || name.length === 0 || name !== "b64")) throw refusal();
      if (!Object.hasOwn(header, "b64") || typeof header.b64 !== "boolean" || !header.b64) throw refusal();
    }
    if (!key || key.type !== "secret" || key.algorithm?.name !== "HMAC" ||
      (key.algorithm as HmacKeyAlgorithm).hash?.name !== "SHA-256" || !key.usages?.includes("verify")) throw refusal();
    if (/[^\x00-\x7f]/.test(parts[0]) || /[^\x00-\x7f]/.test(parts[1])) throw refusal();
    const signature = base64url.decode(parts[2]);
    digest = createHmac("sha256", key)
      .update(parts[0], "ascii").update(".", "ascii").update(parts[1], "ascii").digest();
    if (signature.byteLength !== digest.byteLength || !timingSafeEqual(digest, signature)) throw refusal();
    // PUBLIC claims validation only after ORIGINAL compact HS256 signature succeeds.
    // Original payload segment remains verbatim; this fixed internal header is not a fallback.
    const { payload } = UnsecuredJWT.decode(CLAIMS_ONLY_HEADER + "." + parts[1] + ".");
    return { payload, protectedHeader: header };
  } catch {
    throw refusal();
  } finally {
    if (digest) digest.fill(0);
  }
}
