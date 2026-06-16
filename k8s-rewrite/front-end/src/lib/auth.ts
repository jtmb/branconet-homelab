import { SignJWT, jwtVerify } from "jose";

export const AUTH_COOKIE = "botrus_auth_token";

function getSecretKey(): Uint8Array {
  const secret = process.env.BOTRUS_JWT_SECRET;
  if (!secret)
    throw new Error("BOTRUS_JWT_SECRET not configured. Call ensureJwtSecret() first.");
  return new TextEncoder().encode(secret);
}

export async function signJWT(
  payload: { sub: string; username: string }
): Promise<string> {
  return new SignJWT(payload)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("7d")
    .sign(getSecretKey());
}

export async function verifyJWT(
  token: string
): Promise<{ sub: string; username: string } | null> {
  try {
    const { payload } = await jwtVerify(token, getSecretKey());
    return { sub: payload.sub as string, username: payload.username as string };
  } catch {
    return null;
  }
}

/** Server-side session from cookies — for API routes & server components */
export async function getSession(): Promise<{ id: string; username: string } | null> {
  try {
    const { cookies } = await import("next/headers");
    const cookieStore = await cookies();
    const token = cookieStore.get(AUTH_COOKIE)?.value;
    if (!token) return null;
    const payload = await verifyJWT(token);
    if (!payload) return null;
    return { id: payload.sub, username: payload.username };
  } catch {
    return null;
  }
}

/** Middleware helper — parse auth cookie from raw request header string */
export async function getSessionFromHeaders(
  cookieHeader: string | null
): Promise<{ id: string; username: string } | null> {
  if (!cookieHeader) return null;
  const match = cookieHeader.match(
    new RegExp(`(?:^|;\\s*)${AUTH_COOKIE}=([^;]*)`)
  );
  const token = match?.[1];
  if (!token) return null;
  const payload = await verifyJWT(token);
  if (!payload) return null;
  return { id: payload.sub, username: payload.username };
}
