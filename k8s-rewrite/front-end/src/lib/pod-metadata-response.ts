import type { CachedData } from "./cluster-cache";
import { clusterAvailability, clusterUnavailable } from "./cluster-response";
import { publicClusterMetadata } from "./cluster-metadata";
import { podSummary } from "./pod-query";

type Prefix = { body: Uint8Array; byteLength: number };
const encoder = new TextEncoder();
// Copy private bytes only when consumed, without an entity-sized allocation.
const BODY_CHUNK_BYTES = 64 * 1024;
function ownedBody(bytes: Uint8Array, suffix: Uint8Array): ReadableStream<Uint8Array> {
  let prefix: Uint8Array | undefined = bytes;
  let footer: Uint8Array | undefined = suffix;
  let offset = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (prefix && offset < prefix.byteLength) {
        const end = Math.min(offset + BODY_CHUNK_BYTES, prefix.byteLength);
        controller.enqueue(prefix.slice(offset, end));
        offset = end;
        if (offset === prefix.byteLength) prefix = undefined;
      } else {
        if (footer) controller.enqueue(footer);
        footer = undefined;
        controller.close();
      }
    },
    cancel() { prefix = undefined; footer = undefined; },
  }, { highWaterMark: 0 });
}
function encodePrefix(text: string): Prefix {
  const bytes = encoder.encode(text);
  return { body: bytes, byteLength: bytes.byteLength };
}
const projections = new WeakMap<CachedData["pods"], { rows: unknown[]; prefix: Prefix }>();

export function podMetadataResponse(data: Pick<CachedData, "pods" | "availability">, predicate: (pod: any) => boolean, filtered: boolean): Response {
  const failure = clusterUnavailable(data, "pods");
  if (failure) return failure;
  let projection = projections.get(data.pods);
  if (!projection) {
    const rows = publicClusterMetadata(data.pods.map(podSummary)) as unknown[];
    projection = { rows, prefix: encodePrefix(`{"pods":${JSON.stringify(rows)}`) };
    projections.set(data.pods, projection);
  }
  const prefix = filtered
    ? encodePrefix(`{"pods":${JSON.stringify(projection.rows.filter((_, index) => predicate(data.pods[index])))}`)
    : projection.prefix;
  const suffixText = `,"availability":${JSON.stringify(clusterAvailability(data))},"privateFieldsOmitted":true}`;
  const suffix = encoder.encode(suffixText);
  const length = prefix.byteLength + suffix.byteLength;
  return new Response(ownedBody(prefix.body, suffix), {
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", Vary: "Accept-Encoding", "Content-Length": String(length),
      ...(data.availability.pods?.state === "stale" ? { Warning: '110 - "Stale cluster snapshot"' } : {}) },
  });
}
