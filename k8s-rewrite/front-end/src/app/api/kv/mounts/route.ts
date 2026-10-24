import { kvHuman, kvBody, metadataCursor } from "@/lib/kv-http";
import { mountCreate } from "@/lib/kv-schemas";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const GET = kvHuman((registry, actor, request) => registry.listMounts(actor, metadataCursor(request)));
export const POST = kvHuman(async (registry, actor, request) => registry.createMount(actor, await kvBody(request, mountCreate)), 201);
