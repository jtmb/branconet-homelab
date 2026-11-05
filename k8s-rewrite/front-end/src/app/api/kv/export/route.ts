import { kvBody, kvEngine, kvHuman } from "@/lib/kv-http";
import { exportSchema, KvTransfer } from "@/lib/kv-transfer";
export const runtime="nodejs";
export const POST=kvHuman(async(registry,actor,request)=>new KvTransfer(kvEngine(registry),request.signal).export(actor,await kvBody(request,exportSchema)));
