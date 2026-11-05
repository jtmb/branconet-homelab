import { kvHuman, kvEngine, kvBody } from "@/lib/kv-http";
import { nativeAdopt } from "@/lib/kv-schemas";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const GET = kvHuman(async (registry, actor, _request, { id }) => kvEngine(registry).adoptionPreview(actor, id));
export const POST = kvHuman(async (registry, actor, request, { id }) => kvEngine(registry).adopt(actor, id, await kvBody(request, nativeAdopt)));
