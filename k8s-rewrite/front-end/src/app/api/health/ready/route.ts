import prisma from "@/lib/db";
import { nativeSecrets } from "@/lib/secret-client";
import { secretResponse } from "@/lib/secret-http";
import { listAliases } from "@/lib/secret-references";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export async function GET() {
  try {
    if (!process.env.BOTRUS_JWT_SECRET || !process.env.BOTRUS_SECRETS_KEY)
      return secretResponse(
        { status: "unready", dependency: "configuration" },
        503,
      );
    await prisma.user.count();
    await listAliases();
    await nativeSecrets().list();
    return secretResponse({ status: "ready" });
  } catch {
    return secretResponse(
      { status: "unready", dependency: "database or Kubernetes Secrets" },
      503,
    );
  }
}
