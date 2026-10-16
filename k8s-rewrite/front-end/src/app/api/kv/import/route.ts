import { kvBody, kvEngine, kvHuman } from "@/lib/kv-http";
import { importSchema, KV_TRANSFER_BYTES, KvTransfer } from "@/lib/kv-transfer";
export const runtime="nodejs";
export const POST=kvHuman(async(registry,actor,request)=>new KvTransfer(kvEngine(registry),request.signal).import(actor,await kvBody(request,importSchema,KV_TRANSFER_BYTES+65536)));
