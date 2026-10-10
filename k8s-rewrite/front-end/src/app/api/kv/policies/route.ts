import { kvHuman, kvBody, metadataCursor } from "@/lib/kv-http";
import { policyFields } from "@/lib/kv-schemas";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const GET = kvHuman((registry, actor, request) => registry.listPolicies(actor, metadataCursor(request)));
export const POST = kvHuman(async (registry, actor, request) => registry.savePolicy(actor, await kvBody(request, policyFields)), 201);
