import { kvBody, kvEngine, kvHuman } from "@/lib/kv-http";
import { importPreviewSchema, KV_TRANSFER_BYTES, KvTransfer } from "@/lib/kv-transfer";
export const runtime="nodejs";
export const POST=kvHuman(async(registry,actor,request)=>new KvTransfer(kvEngine(registry),request.signal).preview(actor,(await kvBody(request,importPreviewSchema,KV_TRANSFER_BYTES+65536)).bundle));
