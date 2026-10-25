import type { CachedData } from "./cluster-cache";
import { clusterAvailability, clusterUnavailable } from "./cluster-response";
import { publicClusterMetadata } from "./cluster-metadata";
import { podSummary } from "./pod-query";

type Prefix = { body: string | Uint8Array; byteLength: number };
const encoder = new TextEncoder();
// Bound retained text and avoid a manual stream for small immutable entities.
// Larger encoded prefixes stay private and are copied into each owned body.
const INLINE_PREFIX_BYTES = 16 * 1024;
function encodePrefix(text: string): Prefix {
  const bytes = encoder.encode(text);
  return { body: bytes.byteLength <= INLINE_PREFIX_BYTES ? text : bytes, byteLength: bytes.byteLength };
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
  let responseBody: string | ReadableStream<Uint8Array>;
  if (typeof prefix.body === "string") {
    responseBody = prefix.body + suffixText;
  } else {
    const body = new Uint8Array(length);
    body.set(prefix.body);
    body.set(suffix, prefix.byteLength);
    // Response retains this fresh owned stream without a BufferSource copy.
    responseBody = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(body);
        controller.close();
      },
    });
  }
  return new Response(responseBody, {
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", Vary: "Accept-Encoding", "Content-Length": String(length),
      ...(data.availability.pods?.state === "stale" ? { Warning: '110 - "Stale cluster snapshot"' } : {}) },
  });
}
