import { NextRequest, NextResponse } from "next/server";
import prisma from "@/lib/db";

/**
 * Botrus Secrets Engine — Lookup API
 *
 * GET /api/vars/lookup?key=<variable_key>
 * Authorization: Bearer <BOTRUS_SECRETS_KEY>
 *
 * Returns the decrypted value of a variable from the secrets database.
 * Used by the Ansible botrus_secret lookup plugin — no DB access from Ansible itself.
 *
 * Security:
 *   - Requires a valid Bearer token matching the BOTRUS_SECRETS_KEY env var
 *   - Returns 401 if token is missing or invalid
 *   - Returns 404 if the variable key doesn't exist
 *   - Only returns value — no metadata, no DB schema exposure
 */
export async function GET(request: NextRequest) {
  // ── Auth check ──
  const authHeader = request.headers.get("authorization");
  const expectedToken = process.env.BOTRUS_SECRETS_KEY;

  if (!expectedToken) {
    return NextResponse.json(
      { error: "Server not configured — BOTRUS_SECRETS_KEY not set" },
      { status: 500 }
    );
  }

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return NextResponse.json(
      { error: "Missing or invalid Authorization header" },
      { status: 401 }
    );
  }

  const token = authHeader.slice(7);
  if (token !== expectedToken) {
    return NextResponse.json(
      { error: "Invalid token" },
      { status: 401 }
    );
  }

  // ── Lookup ──
  const { searchParams } = new URL(request.url);
  const key = searchParams.get("key");

  if (!key) {
    return NextResponse.json(
      { error: "Missing ?key= parameter" },
      { status: 400 }
    );
  }

  try {
    const variable = await prisma.variable.findUnique({
      where: { key },
      select: { key: true, value: true },
    });

    if (!variable) {
      return NextResponse.json(
        { error: `Variable not found: ${key}` },
        { status: 404 }
      );
    }

    return NextResponse.json({
      key: variable.key,
      value: variable.value,
    });
  } catch (err) {
    console.error("[secrets-lookup] DB error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
