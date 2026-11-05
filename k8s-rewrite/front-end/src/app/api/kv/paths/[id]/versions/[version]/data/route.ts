import { kvHuman, kvEngine, historyVersion } from "@/lib/kv-http";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const GET = kvHuman(async (registry, actor, _request, { id, version }) => kvEngine(registry).read(actor, id, historyVersion(version)));
