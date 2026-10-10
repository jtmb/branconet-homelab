import { NextResponse } from "next/server";
import { timingSafeEqual, createHash } from "node:crypto";
import { secretFailure } from "./cluster-secrets";
export const privateHeaders = {
  "Cache-Control": "no-store, private",
  Pragma: "no-cache",
};
export function secretResponse(body: unknown, status = 200) {
  return NextResponse.json(body, { status, headers: privateHeaders });
}
export function secretErrorResponse(error: unknown) {
  const safe = secretFailure(error);
  return secretResponse({ error: safe.message }, safe.status);
}
export function bearerAuthorized(
  header: string | null,
  expected: string | undefined,
): boolean {
  if (!expected || !header?.startsWith("Bearer ")) return false;
  return timingSafeEqual(
    createHash("sha256").update(header.slice(7)).digest(),
    createHash("sha256").update(expected).digest(),
  );
}
