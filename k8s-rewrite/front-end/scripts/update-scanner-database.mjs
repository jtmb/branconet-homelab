import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

/** Pure validation for an operator-proposed official DB snapshot. No image or cluster inventory. */
export function databaseCandidate(pins, bytes, now = new Date()) {
  if (bytes.length > 65536) throw Error("Database manifest exceeds limit");
  const manifest = JSON.parse(bytes.toString("utf8")), layer = manifest.layers?.[0];
  if (pins.databaseRepository !== "aquasecurity/trivy-db" || manifest.schemaVersion !== 2 || manifest.layers?.length !== 1 ||
    !/^sha256:[a-f0-9]{64}$/.test(layer?.digest) || !Number.isSafeInteger(layer?.size) || layer.size < 1 || layer.size > 256 * 1024 * 1024 ||
    layer.mediaType !== "application/vnd.aquasec.trivy.db.layer.v1.tar+gzip") throw Error("Unexpected official database manifest shape");
  return { ...pins, databaseManifest: "sha256:" + createHash("sha256").update(bytes).digest("hex"),
    databaseLayer: layer.digest, databaseLayerBytes: layer.size,
    source: `Official aquasecurity/trivy v${pins.version} release and ghcr.io/aquasecurity/trivy-db:2; DB candidate observed ${now.toISOString()}. Review diff and run provision-scanner.mjs before committing.` };
}
async function bounded(url, headers) {
  const response = await fetch(url, { headers, signal: AbortSignal.timeout(20000) });
  if (!response.ok) throw Error(`Official registry metadata unavailable: HTTP ${response.status}`);
  const chunks = []; let size = 0;
  for await (const chunk of response.body) { size += chunk.length; if (size > 65536) throw Error("Registry metadata exceeds limit"); chunks.push(chunk); }
  return Buffer.concat(chunks);
}
export async function proposeDatabase(pins) {
  if (pins.databaseRepository !== "aquasecurity/trivy-db") throw Error("Only the official configured DB repository is supported");
  const token = JSON.parse((await bounded("https://ghcr.io/token?scope=repository:aquasecurity/trivy-db:pull")).toString("utf8"));
  if (typeof token.token !== "string") throw Error("Public registry token unavailable");
  const bytes = await bounded("https://ghcr.io/v2/aquasecurity/trivy-db/manifests/2", { Authorization: `Bearer ${token.token}`, Accept: "application/vnd.oci.image.manifest.v1+json" });
  return databaseCandidate(pins, bytes);
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  if (args.length && (args.length !== 1 || args[0] !== "--write")) throw Error("Use no arguments for a proposal, or --write to update the repository lock for review");
  const file = new URL("scanner-inputs.json", import.meta.url), pins = JSON.parse(await readFile(file, "utf8"));
  const candidate = await proposeDatabase(pins), output = JSON.stringify(candidate, null, 2) + "\n";
  if (args[0] === "--write") await writeFile(file, output);
  else process.stdout.write(output);
}
