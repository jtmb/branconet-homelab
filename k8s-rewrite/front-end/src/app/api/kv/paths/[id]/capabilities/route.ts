import { kvHuman } from "@/lib/kv-http";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const GET = kvHuman(async (registry, actor, _request, { id }) => registry.capabilities(actor, id));
