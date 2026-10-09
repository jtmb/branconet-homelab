import { getCurrentRole } from "@/lib/permissions";
import { nativeSecrets } from "@/lib/secret-client";
import { secretHandlers } from "@/lib/secrets-api";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const handlers = secretHandlers(getCurrentRole, nativeSecrets);
export const GET = handlers.GET;
export const POST = handlers.POST;
export const DELETE = handlers.DELETE;
