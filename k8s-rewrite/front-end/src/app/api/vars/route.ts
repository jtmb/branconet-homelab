import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";

export async function GET() {
  const vars = await prisma.variable.findMany({
    orderBy: { category: "asc" },
  });
  return NextResponse.json(vars);
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, key, value, category, encrypted } = body;

    if (id) {
      // Update existing variable
      const existing = await prisma.variable.findUnique({ where: { id } });
      if (existing) {
        const updated = await prisma.variable.update({
          where: { id },
          data: {
            key: key || existing.key,
            value: value ?? existing.value,
            category: category || existing.category,
            encrypted: encrypted ?? existing.encrypted,
          },
        });
        return NextResponse.json({ success: true, variable: updated });
      }
    }

    // Create new variable
    const created = await prisma.variable.create({
      data: {
        key: key || "new_var",
        value: value || "",
        category: category || "general",
        encrypted: encrypted || false,
      },
    });

    return NextResponse.json({ success: true, variable: created }, { status: 201 });
  } catch (err) {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }
}