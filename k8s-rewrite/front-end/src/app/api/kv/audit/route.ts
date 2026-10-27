import { z } from "zod/v3";
import { kvHuman, metadataCursor } from "@/lib/kv-http";
import { KvError } from "@/lib/kv-contract";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const filters = z.object({ pathId: z.string().uuid().optional(), operationId: z.string().uuid().optional() }).strict();
export const GET = kvHuman(async (registry, actor, request) => {
  const query = new URL(request.url).searchParams;
  if ([...query.keys()].some(key => !["pathId", "operationId", "cursor"].includes(key)) || [...query.keys()].some(key => query.getAll(key).length !== 1))
    throw new KvError(400, "Invalid audit filters");
  const parsed = filters.safeParse({ pathId: query.get("pathId") ?? undefined, operationId: query.get("operationId") ?? undefined });
  if (!parsed.success) throw new KvError(400, "Invalid audit filters");
  return registry.listAudit(actor, { ...parsed.data, cursor: metadataCursor(request) });
});
