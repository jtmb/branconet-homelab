import { NextResponse } from "next/server";
import { getSession, getSessionFromHeaders, type Session } from "@/lib/auth";
import prisma from "@/lib/db";

/**
 * Require write permission for the current user.
 * Returns a 403 JSON response if the user is not authenticated or has role !== "write".
 * Returns the session object if the user has write access.
 *
 * Usage in API routes:
 *   const session = await requireWrite();
 *   // session.id, session.username are available
 */
async function requireAccess(operator: boolean): Promise<
  Session | NextResponse
> {
  const session = await getSession();
  if (!session) {
    return NextResponse.json(
      { error: "Authentication required" },
      { status: 401 }
    );
  }

  const user = await prisma.user.findUnique({
    where: { id: session.id },
    select: { role: true, engineAdmin: true, sessionVersion: true },
  });

  if (!user || user.sessionVersion !== session.sessionVersion || user.role !== "write" || operator && !user.engineAdmin) {
    return NextResponse.json(
      { error: operator ? "Engine administration required for infrastructure and identity operations" : "Write access required" },
      { status: 403 }
    );
  }

  return session;
}

/** Scoped KV writers cannot use infrastructure/identity tools to bypass policy. */
export function requireOperator() { return requireAccess(true); }
/** Write role alone is used only for scoped/self-service operations. */
export function requireWrite() { return requireAccess(false); }

export async function isOperatorFromHeaders(cookie: string | null): Promise<boolean> {
  const session = await getSessionFromHeaders(cookie);
  if (!session) return false;
  const user = await prisma.user.findUnique({ where: { id: session.id }, select: { role: true, engineAdmin: true, sessionVersion: true } });
  return !!user && user.sessionVersion === session.sessionVersion && user.role === "write" && user.engineAdmin;
}

export async function getOperatorRole(): Promise<"readonly" | "write" | null> {
  const session = await getSession();
  if (!session) return null;
  const user = await prisma.user.findUnique({ where: { id: session.id }, select: { role: true, engineAdmin: true, sessionVersion: true } });
  if (!user || user.sessionVersion !== session.sessionVersion) return null;
  return user.role === "write" && user.engineAdmin ? "write" : "readonly";
}

/**
 * Get the current user's role without enforcing permissions.
 * Returns null if not authenticated.
 */
export async function getCurrentRole(): Promise<"readonly" | "write" | null> {
  const session = await getSession();
  if (!session) return null;

  const user = await prisma.user.findUnique({
    where: { id: session.id },
    select: { role: true },
  });

  return user?.role === "readonly" || user?.role === "write" ? user.role : null;
}
