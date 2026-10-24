import { NextRequest, NextResponse } from "next/server";
import { requireWrite } from "@/lib/permissions";
import { accounts, accountFailure } from "@/lib/accounts";
import bcrypt from "bcryptjs";
import { z } from "zod";

const updateUserSchema = z.object({
  role: z.enum(["readonly", "write"]).optional(),
  engineAdmin: z.boolean().optional(),
  password: z.string().min(8, "Password must be at least 8 characters").optional(),
}).refine(data => data.role !== undefined || data.password !== undefined || data.engineAdmin !== undefined, "Provide role, password or engineAdmin");

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;
  const { id } = await params;
  try {
    const parsed = updateUserSchema.safeParse(await request.json());
    if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message }, { status: 400 });
    const { role, password, engineAdmin } = parsed.data;
    // Hash outside the lock; recheck actor and invariants in the transaction.
    const passwordHash = password === undefined ? undefined : await bcrypt.hash(password, 12);
    return NextResponse.json(await accounts.update(auth, id, { role, passwordHash, engineAdmin }));
  } catch (error) { return accountFailure(error); }
}

export async function DELETE(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;
  const { id } = await params;
  try {
    await accounts.delete(auth, id);
    return NextResponse.json({ success: true });
  } catch (error) { return accountFailure(error); }
}
