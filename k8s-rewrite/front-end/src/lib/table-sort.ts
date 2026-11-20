export type SortKind = "text" | "number" | "quantity" | "date" | "age" | "count";
const natural = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
const decimal: Record<string, number> = { n: 1e-9, u: 1e-6, m: 1e-3, k: 1e3, K: 1e3, M: 1e6, G: 1e9, T: 1e12, P: 1e15, E: 1e18 };
export function quantityNumber(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  const match = value.match(/^([+-]?(?:\d+(?:\.\d*)?|\.\d+))([eE][+-]?\d+|[KMGTPE]i|[numkKMGTPE])?$/);
  if (!match) return null;
  const suffix = match[2] ?? "";
  const factor = !suffix ? 1 : /^[eE]/.test(suffix) && suffix.length > 1 && suffix[1] !== "i" ? 10 ** Number(suffix.slice(1)) : suffix.endsWith("i") ? 1024 ** ("KMGTPE".indexOf(suffix[0]) + 1) : decimal[suffix];
  const result = Number(match[1]) * factor;
  return Number.isFinite(result) ? result : null;
}
function scalar(value: unknown, kind: SortKind): string | number | number[] | null {
  if (value === null || value === undefined || value === "" || value === "-" || value === "unknown") return null;
  if (kind === "quantity") return quantityNumber(value);
  if (kind === "date") { const result = Date.parse(String(value)); return Number.isFinite(result) ? result : null; }
  if (kind === "number") { const result = Number(value); return Number.isFinite(result) ? result : null; }
  if (kind === "age") {
    const match = String(value).match(/^(\d+)(s|m|h|d|y)$/);
    return match ? Number(match[1]) * ({ s: 1, m: 60, h: 3600, d: 86400, y: 31536000 }[match[2]] ?? 1) : null;
  }
  if (kind === "count") {
    const match = String(value).match(/^(\d+)\/(\d+)$/);
    return match ? [Number(match[1]), Number(match[2])] : null;
  }
  return String(value);
}
export function compareValues(a: unknown, b: unknown, kind: SortKind = "text", direction: "asc" | "desc" = "asc") {
  const first = scalar(a, kind), second = scalar(b, kind);
  if (first === null || second === null) return first === second ? 0 : first === null ? 1 : -1;
  const order = Array.isArray(first) && Array.isArray(second) ? first[0] - second[0] || first[1] - second[1]
    : typeof first === "number" && typeof second === "number" ? first - second : natural.compare(String(first), String(second));
  return direction === "asc" ? order : -order;
}
export function elapsedAge(value: unknown) {
  const time = Date.parse(String(value));
  if (!Number.isFinite(time)) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - time) / 1000));
  for (const [unit, size] of [["y", 31536000], ["d", 86400], ["h", 3600], ["m", 60]] as const)
    if (seconds >= size) return `${Math.floor(seconds / size)}${unit}`;
  return `${seconds}s`;
}
