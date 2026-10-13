import { SignJWT, jwtVerify } from "jose";
import { directAccountReader } from "./direct-account-reader";
import { HmacKeySlot } from "./jwt-key";

export const AUTH_COOKIE = "botrus_auth_token";

const keyScope = globalThis as typeof globalThis & { __bortusJwtKeySlot?: HmacKeySlot };
const signingKey = keyScope.__bortusJwtKeySlot ??= new HmacKeySlot(() => process.env.BOTRUS_JWT_SECRET);

export async function signJWT(
  payload: { sub: string; username: string; sessionVersion?: number }
): Promise<string> {
  return signingKey.run(key => new SignJWT({ ...payload, sessionVersion: payload.sessionVersion ?? 0 })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("7d")
    .sign(key));
}

export async function verifyJWT(
  token: string
): Promise<{ sub: string; username: string; sessionVersion: number } | null> {
  try {
    const { payload } = await signingKey.run(key => jwtVerify(token, key, { algorithms: ["HS256"] }));
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
  const user = await directAccountReader.readSession(payload.sub);
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

// A fresh handler account snapshot, separate from middleware and transactional checks.
export type SessionAccount = Session & { role: string; engineAdmin: boolean };
async function currentAccount(payload: NonNullable<Awaited<ReturnType<typeof verifyJWT>>>): Promise<SessionAccount | null> {
  const user = await directAccountReader.readAccount(payload.sub);
  if (!user || user.sessionVersion !== payload.sessionVersion) return null;
  return user;
}

export async function getSessionAccount(): Promise<SessionAccount | null> {
  let payload;
  try {
    const { cookies } = await import("next/headers");
    const token = (await cookies()).get(AUTH_COOKIE)?.value;
    if (!token) return null;
    payload = await verifyJWT(token);
  } catch { return null; }
  // Database failure remains an availability error, never an authenticated snapshot.
  return payload ? currentAccount(payload) : null;
}

export async function getSessionAccountFromHeaders(cookieHeader: string | null): Promise<SessionAccount | null> {
  if (!cookieHeader) return null;
  const token = cookieHeader.match(new RegExp(`(?:^|;\\s*)${AUTH_COOKIE}=([^;]*)`))?.[1];
  if (!token) return null;
  const payload = await verifyJWT(token);
  return payload ? currentAccount(payload) : null;
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
