import { copyVerifiedScannerBundle } from "./verify-scanner-bundle.mjs";
import { createHash } from "node:crypto";
import { createWriteStream } from "node:fs";
import { readFile, mkdir, mkdtemp, rm, copyFile, writeFile, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { once } from "node:events";

const pins = JSON.parse(await readFile(new URL("scanner-inputs.json", import.meta.url), "utf8"));
const digest = data => "sha256:" + createHash("sha256").update(data).digest("hex");
async function request(url, maximum, headers = {}) {
  const response = await fetch(url, { headers, signal: AbortSignal.timeout(120000), redirect: "follow" });
  if (!response.ok) throw Error(`Official scanner input download failed: HTTP ${response.status}`);
  if (Number(response.headers.get("content-length")) > maximum) throw Error("Scanner input exceeds limit");
  return response;
}
async function download(url, output, maximum, expected, headers) {
  const response = await request(url, maximum, headers), hash = createHash("sha256"), stream = createWriteStream(output, { flags: "wx" });
  let bytes = 0;
  try {
    for await (const chunk of response.body) {
      bytes += chunk.length; if (bytes > maximum) throw Error("Scanner input exceeds limit");
      hash.update(chunk); if (!stream.write(chunk)) await once(stream, "drain");
    }
    stream.end(); await once(stream, "finish");
    if ("sha256:" + hash.digest("hex") !== expected) throw Error("Scanner input digest mismatch");
    return bytes;
  } finally { stream.destroy(); }
}
async function ghcrHeaders() {
  const response = await request(`https://ghcr.io/token?scope=repository:${pins.databaseRepository}:pull`, 65536);
  const data = await response.json();
  if (typeof data.token !== "string") throw Error("Public registry token unavailable");
  return { Authorization: `Bearer ${data.token}`, Accept: "application/vnd.oci.image.manifest.v1+json" };
}
export async function provisionScanner(destination, { databaseOnly = false, binarySource = process.env.BORTUS_SCANNER_BUNDLE } = {}) {
  if (!databaseOnly && (process.platform !== "linux" || process.arch !== "x64")) throw Error("The owned production build supports linux/amd64; database-only qualification is portable");
  const target = resolve(destination); await mkdir(target, { recursive: true });
  const staging = await mkdtemp(join(target, ".provision-"));
  try {
    if (!databaseOnly) {
      await copyVerifiedScannerBundle(staging, pins, binarySource);
      for (const file of ["trivy", "LICENSE"]) await copyFile(join(staging, file), join(target, file));
    }
    const headers = await ghcrHeaders();
    const response = await request(`https://ghcr.io/v2/${pins.databaseRepository}/manifests/${pins.databaseManifest}`, 65536, headers);
    const bytes = Buffer.from(await response.arrayBuffer());
    if (bytes.length > 65536 || digest(bytes) !== pins.databaseManifest) throw Error("Database manifest digest mismatch");
    const manifest = JSON.parse(bytes);
    if (manifest.schemaVersion !== 2 || manifest.layers?.length !== 1 || manifest.layers[0].digest !== pins.databaseLayer || manifest.layers[0].size !== pins.databaseLayerBytes) throw Error("Database layer identity mismatch");
    const archive = join(staging, "database.tar.gz");
    await download(`https://ghcr.io/v2/${pins.databaseRepository}/blobs/${pins.databaseLayer}`, archive, pins.databaseLayerBytes, pins.databaseLayer, headers);
    const listing = execFileSync("tar", ["-tvzf", archive], { timeout: 30000, maxBuffer: 65536, encoding: "utf8" });
    console.log(JSON.stringify({ pinnedDatabaseArchive: listing.trim() }));
    execFileSync("tar", ["-xzf", archive, "-C", staging, "metadata.json", "trivy.db"], { timeout: 60000, maxBuffer: 65536 });
    const databaseBytes = (await stat(join(staging, "trivy.db"))).size;
    if (databaseBytes > 3 * 1024 * 1024 * 1024) throw Error("Expanded database exceeds 3GiB limit");
    const db = JSON.parse(await readFile(join(staging, "metadata.json"), "utf8"));
    if (db.Version !== 2 || !Number.isFinite(Date.parse(db.UpdatedAt)) || !Number.isFinite(Date.parse(db.NextUpdate))) throw Error("Database metadata invalid");
    await mkdir(join(target, "cache", "db"), { recursive: true });
    for (const file of ["metadata.json", "trivy.db"]) await copyFile(join(staging, file), join(target, "cache", "db", file));
    await writeFile(join(target, "provenance.json"), JSON.stringify({ ...pins, databaseUpdatedAt: db.UpdatedAt, databaseNextUpdate: db.NextUpdate }, null, 2) + "\n");
    return { version: pins.version, databaseManifest: pins.databaseManifest, databaseBytes, databaseUpdatedAt: db.UpdatedAt, databaseNextUpdate: db.NextUpdate };
  } finally {
    if (dirname(staging) !== target || !staging.startsWith(join(target, ".provision-"))) throw Error("Owned scanner staging cleanup refused");
    await rm(staging, { recursive: true, force: true });
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  let databaseOnly = false, binarySource, output;
  for (let index = 0; index < args.length; index++) {
    const argument = args[index];
    if (argument === "--database-only") databaseOnly = true;
    else if (argument === "--binary-source") {
      binarySource = args[++index];
      if (!binarySource || binarySource.startsWith("--")) throw Error("--binary-source requires an absolute bundle directory");
    } else if (argument.startsWith("--") || output !== undefined) throw Error("Unknown scanner provisioning argument");
    else output = argument;
  }
  console.log(JSON.stringify(await provisionScanner(output ?? ".scanner", { databaseOnly, binarySource })));
}
