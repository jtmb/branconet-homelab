export const LOG_TAIL_CHARS = 65536;
/** Keep only an in-memory text tail; ANSI controls do not become DOM nodes. */
export function appendLogTail(previous: string, chunk: string) {
  const combined = (previous + chunk).replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "");
  let output = combined.slice(-LOG_TAIL_CHARS);
  if (/^[\uDC00-\uDFFF]/.test(output)) output = output.slice(1);
  return { output, truncated: combined.length > LOG_TAIL_CHARS };
}
