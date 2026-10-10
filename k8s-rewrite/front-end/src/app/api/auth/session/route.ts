import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { getSession } from "@/lib/auth";
import { ensureJwtSecret } from "@/lib/auth-server";

export async function GET() {
  try {
    await ensureJwtSecret();

    const session = await getSession();
    const userCount = await prisma.user.count();

    let registrationOpen = userCount === 0 || process.env.ALLOW_REGISTRATION === "true";
    if (!registrationOpen) {
      const dbSetting = await prisma.appSetting.findUnique({
        where: { key: "allow_registration" },
      });
      if (dbSetting?.value === "true") registrationOpen = true;
    }

    if (session) {
      const user = await prisma.user.findUnique({ where: { id: session.id } });
      return NextResponse.json({
        authenticated: true,
        username: session.username,
        role: user?.role || "readonly",
        hasUsers: userCount > 0,
        registrationOpen,
      });
    }

    return NextResponse.json({
      authenticated: false,
      hasUsers: userCount > 0,
      registrationOpen,
    });
  } catch (err) {
    console.error("Session error:", err);
    return NextResponse.json(
      { authenticated: false, error: "Internal server error" },
      { status: 500 }
    );
  }
}
