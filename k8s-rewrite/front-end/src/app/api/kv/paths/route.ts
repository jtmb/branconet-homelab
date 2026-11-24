import { kvHuman, kvBody, metadataCursor } from "@/lib/kv-http";
import { pathCreate } from "@/lib/kv-schemas";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const GET = kvHuman((registry, actor, request) => registry.listPaths(actor, new URL(request.url).searchParams.get("mountId") || undefined, metadataCursor(request)));
export const POST = kvHuman(async (registry, actor, request) => registry.registerPath(actor, await kvBody(request, pathCreate)), 201);
