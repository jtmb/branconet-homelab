import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
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
export async function requireWrite(): Promise<
  { id: string; username: string } | NextResponse
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
    select: { role: true },
  });

  if (!user || user.role !== "write") {
    return NextResponse.json(
      { error: "Forbidden — write access required" },
      { status: 403 }
    );
  }

  return session;
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

  return (user?.role as "readonly" | "write") || null;
}
