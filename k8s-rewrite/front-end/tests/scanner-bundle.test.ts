import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, readdir, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

type Pins = { version: string; binarySHA256: string; binaryBytes: number; licenseSHA256: string; licenseBytes: number };
type BundleResult = { version: string; binarySHA256: string; binaryBytes: number; licenseSHA256: string };
const moduleURL = new URL("../scripts/verify-scanner-bundle.mjs", import.meta.url).href;
async function copyVerifiedScannerBundle(destination: string, pins: Pins, source?: string) {
  const bundleModule = await import(moduleURL) as {
    copyVerifiedScannerBundle(destination: string, pins: Pins, source?: string): Promise<BundleResult>;
  };
  return bundleModule.copyVerifiedScannerBundle(destination, pins, source);
}
const digest = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
async function fixture() {
  // The qualification caller puts TMPDIR in its declared disposable output root.
  const root = await mkdtemp(join(tmpdir(), "scanner-bundle-"));
  const source = join(root, "input"), destination = join(root, "output");
  await mkdir(source); await mkdir(destination);
  const binary = Buffer.from([0x7f, 0x45, 0x4c, 0x46, 0, 13, 10, 255]);
  const license = Buffer.from("fixture license\r\nraw bytes\n");
  await writeFile(join(source, "trivy"), binary); await writeFile(join(source, "LICENSE"), license);
  const pins: Pins = { version: "fixture", binarySHA256: digest(binary), binaryBytes: binary.length, licenseSHA256: digest(license), licenseBytes: license.length };
  return { root, source, destination, binary, license, pins };
}
async function sourceUnchanged(f: Awaited<ReturnType<typeof fixture>>) {
  assert.deepEqual(await readFile(join(f.source, "trivy")), f.binary);
  assert.deepEqual(await readFile(join(f.source, "LICENSE")), f.license);
}

test("qualified bundle copies exact binary and license bytes with bounded pins", async () => {
  const f = await fixture();
  const result = await copyVerifiedScannerBundle(f.destination, f.pins, f.source);
  assert.deepEqual(result, { version: "fixture", binarySHA256: f.pins.binarySHA256, binaryBytes: f.binary.length, licenseSHA256: f.pins.licenseSHA256 });
  assert.deepEqual(await readFile(join(f.destination, "trivy")), f.binary);
  assert.deepEqual(await readFile(join(f.destination, "LICENSE")), f.license);
  if (process.platform !== "win32") {
    assert.equal((await stat(join(f.destination, "trivy"))).mode & 0o777, 0o555);
    assert.equal((await stat(join(f.destination, "LICENSE"))).mode & 0o777, 0o644);
  }
  await sourceUnchanged(f);
});
for (const source of [undefined, "relative/provider"]) {
  test(`qualified bundle requires an explicit absolute provider: ${source ?? "missing"}`, async () => {
    const f = await fixture();
    await assert.rejects(copyVerifiedScannerBundle(f.destination, f.pins, source), /explicit absolute/);
    assert.deepEqual(await readdir(f.destination), []); await sourceUnchanged(f);
  });
}
for (const change of ["wrong digest", "wrong size", "unbounded size", "malformed digest"] as const) {
  test(`qualified bundle rejects ${change} without retaining partial output`, async () => {
    const f = await fixture(), pins = { ...f.pins };
    if (change === "wrong digest") pins.binarySHA256 = "0".repeat(64);
    if (change === "wrong size") pins.binaryBytes++;
    if (change === "unbounded size") pins.binaryBytes = 257 * 1024 * 1024;
    if (change === "malformed digest") pins.binarySHA256 = "not-a-sha256";
    await assert.rejects(copyVerifiedScannerBundle(f.destination, pins, f.source), /digest mismatch|pinned size|bounded exact byte count/);
    assert.deepEqual(await readdir(f.destination), []); await sourceUnchanged(f);
  });
}
test("qualified bundle rejects license mismatch and rolls back its new binary", async () => {
  const f = await fixture();
  await assert.rejects(copyVerifiedScannerBundle(f.destination, { ...f.pins, licenseSHA256: "0".repeat(64) }, f.source), /digest mismatch/);
  assert.deepEqual(await readdir(f.destination), []); await sourceUnchanged(f);
});
test("qualified bundle rejects a file in place of the provider directory", async () => {
  const f = await fixture();
  await assert.rejects(copyVerifiedScannerBundle(f.destination, f.pins, join(f.source, "trivy")), /real directory/);
  assert.deepEqual(await readdir(f.destination), []); await sourceUnchanged(f);
});
for (const existing of ["trivy", "LICENSE"]) {
  test(`qualified bundle preserves an existing ${existing} output on refusal`, async () => {
    const f = await fixture(), original = Buffer.from("preexisting output\r\n");
    await writeFile(join(f.destination, existing), original);
    await assert.rejects(copyVerifiedScannerBundle(f.destination, f.pins, f.source), { code: "EEXIST" });
    assert.deepEqual(await readdir(f.destination), [existing]);
    assert.deepEqual(await readFile(join(f.destination, existing)), original); await sourceUnchanged(f);
  });
}