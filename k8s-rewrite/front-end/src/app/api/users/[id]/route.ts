import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { requireWrite } from "@/lib/permissions";
import bcrypt from "bcryptjs";
import { z } from "zod";

const updateUserSchema = z.object({
  role: z.enum(["readonly", "write"]).optional(),
  password: z.string().min(8, "Password must be at least 8 characters").optional(),
});

/**
 * PATCH /api/users/[id] — update user role or reset password (write-only)
 * Cannot change own role or demote the last write user.
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  const { id } = await params;

  // Can't change own role
  if (auth.id === id) {
    return NextResponse.json(
      { error: "You cannot change your own role via this API" },
      { status: 403 }
    );
  }

  try {
    const body = await request.json();
    const parsed = updateUserSchema.safeParse(body);

    if (!parsed.success) {
      return NextResponse.json(
        { error: parsed.error.issues[0]?.message ?? "Invalid input" },
        { status: 400 }
      );
    }

    const { role, password } = parsed.data;

    // Ensure at least one field to update
    if (!role && !password) {
      return NextResponse.json(
        { error: "Provide 'role' or 'password' to update" },
        { status: 400 }
      );
    }

    const target = await prisma.user.findUnique({ where: { id } });
    if (!target) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    // If demoting a write user, ensure it's not the last one
    if (role === "readonly" && target.role === "write") {
      const writeCount = await prisma.user.count({ where: { role: "write" } });
      if (writeCount <= 1) {
        return NextResponse.json(
          { error: "Cannot demote the last write user" },
          { status: 403 }
        );
      }
    }

    const updateData: { role?: string; passwordHash?: string } = {};
    if (role) updateData.role = role;
    if (password) updateData.passwordHash = await bcrypt.hash(password, 12);

    const updated = await prisma.user.update({
      where: { id },
      data: updateData,
      select: {
        id: true,
        username: true,
        role: true,
        createdAt: true,
      },
    });

    return NextResponse.json(updated);
  } catch (err) {
    console.error("[users] PATCH error:", err);
    return NextResponse.json(
      { error: "Failed to update user" },
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/users/[id] — delete a user (write-only)
 * Cannot delete self or the last write user.
 */
export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  const { id } = await params;

  // Can't delete yourself
  if (auth.id === id) {
    return NextResponse.json(
      { error: "You cannot delete yourself" },
      { status: 403 }
    );
  }

  const target = await prisma.user.findUnique({ where: { id } });
  if (!target) {
    return NextResponse.json({ error: "User not found" }, { status: 404 });
  }

  // If deleting a write user, ensure it's not the last one
  if (target.role === "write") {
    const writeCount = await prisma.user.count({ where: { role: "write" } });
    if (writeCount <= 1) {
      return NextResponse.json(
        { error: "Cannot delete the last write user" },
        { status: 403 }
      );
    }
  }

  await prisma.user.delete({ where: { id } });

  return NextResponse.json({ success: true });
}
