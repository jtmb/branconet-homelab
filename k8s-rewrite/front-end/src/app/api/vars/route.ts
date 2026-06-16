import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";
import { parseSecretKey, syncSecretToCluster } from "@/lib/cluster-secrets";
import { requireWrite } from "@/lib/permissions";

export async function GET() {
  const vars = await prisma.variable.findMany({
    orderBy: { category: "asc" },
  });
  return NextResponse.json(vars);
}

export async function POST(request: NextRequest) {
  const auth = await requireWrite();
  if (auth instanceof NextResponse) return auth;

  try {
    const body = await request.json();
    const { id, key, value, category, encrypted } = body;

    let variable;

    if (id) {
      const existing = await prisma.variable.findUnique({ where: { id } });
      if (existing) {
        variable = await prisma.variable.update({
          where: { id },
          data: {
            key: key || existing.key,
            value: value ?? existing.value,
            category: category || existing.category,
            encrypted: encrypted ?? existing.encrypted,
          },
        });
      }
    }

    if (!variable && key) {
      variable = await prisma.variable.upsert({
        where: { key },
        update: {
          value: value ?? "",
          category: category || "general",
          encrypted: encrypted ?? false,
        },
        create: {
          key,
          value: value || "",
          category: category || "general",
          encrypted: encrypted ?? false,
        },
      });
    }

    if (!variable) {
      return NextResponse.json(
        { error: "Either id (update) or key (create/upsert) is required" },
        { status: 400 }
      );
    }

    // Sync to K8s if this is a secret_* variable
    const parsed = parseSecretKey(variable.key);
    if (parsed && variable.category === "secret") {
      syncSecretToCluster(parsed.namespace, parsed.name).catch((err) =>
        console.error("[vars] K8s sync error:", err)
      );
    }

    const isNew = !id && body.key &&
      (await prisma.variable.count({ where: { key: variable.key } })) <= 1;

    return NextResponse.json(
      { success: true, variable },
      { status: isNew ? 201 : 200 }
    );
  } catch (err) {
    console.error("[vars] POST error:", err);
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }
}