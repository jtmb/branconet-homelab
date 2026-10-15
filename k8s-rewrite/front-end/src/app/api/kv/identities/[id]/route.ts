import { kvHuman } from "@/lib/kv-http";
export const runtime = "nodejs";
export const DELETE = kvHuman((registry, actor, _request, { id }) => registry.revokeIdentity(actor, id));
