import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { getSession } from "@/lib/auth";
import { ensureJwtSecret } from "@/lib/auth-server";

export async function GET() {
  try {
    await ensureJwtSecret();

    const session = await getSession();
    const userCount = await prisma.user.count();

    if (session) {
      return NextResponse.json({
        authenticated: true,
        username: session.username,
        hasUsers: userCount > 0,
        registrationOpen:
          userCount === 0 || process.env.ALLOW_REGISTRATION === "true",
      });
    }

    return NextResponse.json({
      authenticated: false,
      hasUsers: userCount > 0,
      registrationOpen:
        userCount === 0 || process.env.ALLOW_REGISTRATION === "true",
    });
  } catch (err) {
    console.error("Session error:", err);
    return NextResponse.json(
      { authenticated: false, error: "Internal server error" },
      { status: 500 }
    );
  }
}
