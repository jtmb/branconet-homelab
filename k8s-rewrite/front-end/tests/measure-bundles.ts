import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gzipSync, brotliCompressSync } from "node:zlib";

async function main() {
  const input = path.resolve(process.argv[2]);
  const observed = JSON.parse(await readFile(input, "utf8")) as { stages: Record<string, string[]>; [key: string]: unknown };
  const build = path.resolve(".next");
  const compressed: Record<string, { files: number; rawBytes: number; gzipBytes: number; brotliBytes: number }> = {};
  for (const [stage, scripts] of Object.entries(observed.stages)) {
    const counts = { files: 0, rawBytes: 0, gzipBytes: 0, brotliBytes: 0 };
    for (const source of new Set(scripts)) {
      if (!source.startsWith("/_next/static/") || !source.endsWith(".js")) throw new Error("Expected observed static script");
      const file = path.resolve(build, source.slice("/_next/".length));
      if (!file.startsWith(build + path.sep)) throw new Error("Invalid script path");
      const bytes = await readFile(file);
      counts.files++; counts.rawBytes += bytes.length;
      counts.gzipBytes += gzipSync(bytes).length;
      counts.brotliBytes += brotliCompressSync(bytes).length;
    }
    compressed[stage] = counts;
  }
  await writeFile(input, JSON.stringify({ ...observed, compressed, compressionLimits: "Offline gzip/default Brotli byte estimates of observed local files; gateway does not compress. Not transfer timing, parse/execute, CPU, LCP, or image acceptance." }, null, 2) + "\n");
  console.log(JSON.stringify(compressed));
}
void main().catch(error => { console.error(error instanceof Error ? error.message : "Bundle measurement failed"); process.exitCode = 1; });
