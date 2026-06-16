import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { signJWT, AUTH_COOKIE } from "@/lib/auth";
import { ensureJwtSecret } from "@/lib/auth-server";
import bcrypt from "bcryptjs";
import { z } from "zod";

const registerSchema = z.object({
  username: z
    .string()
    .min(3, "Username must be at least 3 characters")
    .max(30, "Username must be at most 30 characters")
    .regex(/^[a-zA-Z0-9_-]+$/, "Username can only contain letters, numbers, hyphens, and underscores"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

export async function POST(req: Request) {
  try {
    await ensureJwtSecret();

    // First-user-only gate unless ALLOW_REGISTRATION is explicitly "true"
    const userCount = await prisma.user.count();
    if (userCount > 0 && process.env.ALLOW_REGISTRATION !== "true") {
      return NextResponse.json(
        { error: "Registration is locked. Set ALLOW_REGISTRATION=true to enable." },
        { status: 403 }
      );
    }

    const body = await req.json();
    const parsed = registerSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json(
        { error: parsed.error.issues[0]?.message ?? "Invalid input" },
        { status: 400 }
      );
    }

    const { username, password } = parsed.data;

    // Check uniqueness
    const existing = await prisma.user.findUnique({ where: { username } });
    if (existing) {
      return NextResponse.json(
        { error: "Username already taken" },
        { status: 409 }
      );
    }

    const passwordHash = await bcrypt.hash(password, 12);

    const user = await prisma.user.create({
      data: { username, passwordHash },
    });

    const token = await signJWT({ sub: user.id, username: user.username });

    const response = NextResponse.json(
      { id: user.id, username: user.username },
      { status: 201 }
    );

    response.cookies.set(AUTH_COOKIE, token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 7, // 7 days
    });

    return response;
  } catch (err) {
    console.error("Register error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
