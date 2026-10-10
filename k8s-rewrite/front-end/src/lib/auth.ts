import { SignJWT, jwtVerify } from "jose";
import prisma from "./db";

export const AUTH_COOKIE = "botrus_auth_token";

function getSecretKey(): Uint8Array {
  const secret = process.env.BOTRUS_JWT_SECRET;
  if (!secret)
    throw new Error("BOTRUS_JWT_SECRET not configured. Call ensureJwtSecret() first.");
  return new TextEncoder().encode(secret);
}

export async function signJWT(
  payload: { sub: string; username: string; sessionVersion?: number }
): Promise<string> {
  return new SignJWT({ ...payload, sessionVersion: payload.sessionVersion ?? 0 })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("7d")
    .sign(getSecretKey());
}

export async function verifyJWT(
  token: string
): Promise<{ sub: string; username: string; sessionVersion: number } | null> {
  try {
    const { payload } = await jwtVerify(token, getSecretKey(), { algorithms: ["HS256"] });
    const sessionVersion = payload.sessionVersion ?? 0;
    if (typeof payload.sub !== "string" || !payload.sub || typeof payload.username !== "string" ||
      typeof sessionVersion !== "number" || !Number.isSafeInteger(sessionVersion) || sessionVersion < 0) return null;
    return { sub: payload.sub, username: payload.username, sessionVersion };
  } catch {
    return null;
  }
}

/** Server-side session from cookies — for API routes & server components */
export type Session = { id: string; username: string; sessionVersion: number };

async function currentSession(payload: NonNullable<Awaited<ReturnType<typeof verifyJWT>>>): Promise<Session | null> {
  const user = await prisma.user.findUnique({ where: { id: payload.sub }, select: { id: true, username: true, sessionVersion: true } });
  if (!user || user.sessionVersion !== payload.sessionVersion) return null;
  return { id: user.id, username: user.username, sessionVersion: user.sessionVersion };
}

export async function getSession(): Promise<Session | null> {
  try {
    const { cookies } = await import("next/headers");
    const cookieStore = await cookies();
    const token = cookieStore.get(AUTH_COOKIE)?.value;
    if (!token) return null;
    const payload = await verifyJWT(token);
    if (!payload) return null;
    return await currentSession(payload);
  } catch {
    return null;
  }
}

/** Middleware helper — parse auth cookie from raw request header string */
export async function getSessionFromHeaders(
  cookieHeader: string | null
): Promise<Session | null> {
  if (!cookieHeader) return null;
  const match = cookieHeader.match(
    new RegExp(`(?:^|;\\s*)${AUTH_COOKIE}=([^;]*)`)
  );
  const token = match?.[1];
  if (!token) return null;
  const payload = await verifyJWT(token);
  if (!payload) return null;
  return currentSession(payload);
}
