import { isAscii } from "node:buffer";

// A bounded view of unselected native value bytes; never decode or copy them.
// A quote, escape, raw control or high byte leaves the scalar grammar in charge.
export function nativeAsciiValueSpan(chunk: Buffer, start: number): number {
  if (chunk.length - start < 4096) return 0;
  const window = chunk.subarray(start, start + 4096);
  let end = window.indexOf(34);
  if (end < 0) end = window.length;
  if (end < 256) return 0;
  const escape = window.subarray(0, end).indexOf(92);
  if (escape >= 0) end = escape;
  if (end < 256) return 0;
  const span = window.subarray(0, end);
  if (!isAscii(span)) return 0;
  for (let control = 0; control < 32; control++) if (span.indexOf(control) >= 0) return 0;
  return end;
}
