import type { CachedData } from "./cluster-cache";
import { clusterAvailability, clusterUnavailable } from "./cluster-response";
import { publicClusterMetadata } from "./cluster-metadata";
import { podSummary } from "./pod-query";

type Prefix = { body: Uint8Array; byteLength: number };
const encoder = new TextEncoder();
const decoder = new TextDecoder();
// Copy private bytes only when consumed, without an entity-sized allocation.
const BODY_CHUNK_BYTES = 64 * 1024;
function ownedBody(bytes: Uint8Array, suffix: Uint8Array): ReadableStream<Uint8Array> {
  let prefix: Uint8Array | undefined = bytes;
  let footer: Uint8Array | undefined = suffix;
  const prefixLength = bytes.byteLength;
  const length = prefixLength + suffix.byteLength;
  let offset = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      const end = Math.min(offset + BODY_CHUNK_BYTES, length);
      let chunk: Uint8Array;
      if (prefix && end <= prefixLength) {
        chunk = prefix.slice(offset, end);
      } else {
        chunk = new Uint8Array(end - offset);
        if (prefix && offset < prefixLength) chunk.set(offset === 0 ? prefix : prefix.subarray(offset));
        if (footer && end > prefixLength) {
          const start = Math.max(0, offset - prefixLength), stop = end - prefixLength;
          chunk.set(start === 0 && stop === footer.byteLength ? footer : footer.subarray(start, stop), Math.max(0, prefixLength - offset));
        }
      }
      offset = end;
      if (offset >= prefixLength) prefix = undefined;
      controller.enqueue(chunk);
      if (offset === length) { footer = undefined; controller.close(); }
    },
    cancel() { prefix = undefined; footer = undefined; },
  }, { highWaterMark: 0 });
}
function encodePrefix(text: string): Prefix {
  const bytes = encoder.encode(text);
  return { body: bytes, byteLength: bytes.byteLength };
}
const projections = new WeakMap<CachedData["pods"], Prefix>();

export function podMetadataResponse(data: Pick<CachedData, "pods" | "availability">, predicate: (pod: any) => boolean, filtered: boolean): Response {
  const failure = clusterUnavailable(data, "pods");
  if (failure) return failure;
  let projection = projections.get(data.pods);
  if (!projection) {
    const rows = publicClusterMetadata(data.pods.map(podSummary)) as unknown[];
    projection = encodePrefix(`{"pods":${JSON.stringify(rows)}`);
    projections.set(data.pods, projection);
  }
  // Keep only immutable encoded metadata between requests. Filtering recovers
  // the exact original projection, rather than reprojecting mutable raw rows.
  const prefix = filtered
    ? encodePrefix(`{"pods":${JSON.stringify((JSON.parse(decoder.decode(projection.body) + "}").pods as unknown[]).filter((_, index) => predicate(data.pods[index])))}`)
    : projection;
  const suffixText = `,"availability":${JSON.stringify(clusterAvailability(data))},"privateFieldsOmitted":true}`;
  const suffix = encoder.encode(suffixText);
  const length = prefix.byteLength + suffix.byteLength;
  return new Response(ownedBody(prefix.body, suffix), {
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", Vary: "Accept-Encoding", "Content-Length": String(length),
      ...(data.availability.pods?.state === "stale" ? { Warning: '110 - "Stale cluster snapshot"' } : {}) },
  });
}
