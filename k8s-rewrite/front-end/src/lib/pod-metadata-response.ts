import type { CachedData } from "./cluster-cache";
import { clusterAvailability, clusterUnavailable } from "./cluster-response";
import { publicClusterMetadata } from "./cluster-metadata";
import { podSummary } from "./pod-query";

type Prefix = { body: Uint8Array; byteLength: number };
const encoder = new TextEncoder();
const decoder = new TextDecoder();
// Copy private bytes only when consumed, without an entity-sized allocation.
const BODY_CHUNK_BYTES = 64 * 1024;
// Each response owns its cursors and copies; shared methods avoid per-response closures.
class OwnedPodBody {
  private prefix: Uint8Array | undefined;
  private footer: Uint8Array | undefined;
  private readonly prefixLength: number;
  private readonly length: number;
  private offset = 0;
  constructor(bytes: Uint8Array, suffix: Uint8Array) {
    this.prefix = bytes; this.footer = suffix;
    this.prefixLength = bytes.byteLength; this.length = bytes.byteLength + suffix.byteLength;
  }
  pull(controller: ReadableStreamDefaultController<Uint8Array>) {
    const end = Math.min(this.offset + BODY_CHUNK_BYTES, this.length);
    let chunk: Uint8Array;
    if (this.prefix && end <= this.prefixLength) {
      chunk = this.prefix.slice(this.offset, end);
    } else {
      chunk = new Uint8Array(end - this.offset);
      if (this.prefix && this.offset < this.prefixLength) chunk.set(this.offset === 0 ? this.prefix : this.prefix.subarray(this.offset));
      if (this.footer && end > this.prefixLength) {
        const start = Math.max(0, this.offset - this.prefixLength), stop = end - this.prefixLength;
        chunk.set(start === 0 && stop === this.footer.byteLength ? this.footer : this.footer.subarray(start, stop), Math.max(0, this.prefixLength - this.offset));
      }
    }
    this.offset = end;
    if (this.offset >= this.prefixLength) this.prefix = undefined;
    controller.enqueue(chunk);
    if (this.offset === this.length) { this.footer = undefined; controller.close(); }
  }
  cancel() { this.prefix = undefined; this.footer = undefined; }
}
const bodyStrategy = { highWaterMark: 0 };
function ownedBody(bytes: Uint8Array, suffix: Uint8Array): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>(new OwnedPodBody(bytes, suffix), bodyStrategy);
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
