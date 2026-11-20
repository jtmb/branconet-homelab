import { createHash } from "node:crypto";
import { constants } from "node:fs";
import { chmod, lstat, open, realpath, rm } from "node:fs/promises";
import { isAbsolute, join, resolve } from "node:path";

const sha256Pattern = /^[a-f0-9]{64}$/;

async function copyPinnedFile(source, destination, expectedSHA256, expectedBytes, maximumBytes, mode) {
  if (!sha256Pattern.test(expectedSHA256 ?? "") || !Number.isSafeInteger(expectedBytes) || expectedBytes <= 0 || expectedBytes > maximumBytes) {
    throw Error("Qualified scanner input requires a SHA256 and a bounded exact byte count");
  }
  const before = await lstat(source, { bigint: true });
  if (!before.isFile() || before.isSymbolicLink() || before.size !== BigInt(expectedBytes)) {
    throw Error("Qualified scanner input must be a regular file of the pinned size");
  }
  const input = await open(source, constants.O_RDONLY);
  let output, created = false;
  try {
    const opened = await input.stat({ bigint: true });
    if (opened.dev !== before.dev || opened.ino !== before.ino || opened.size !== before.size || opened.mtimeNs !== before.mtimeNs) {
      throw Error("Qualified scanner input changed before it could be read");
    }
    output = await open(destination, "wx", mode); created = true;
    const buffer = Buffer.allocUnsafe(1024 * 1024), hash = createHash("sha256");
    let bytes = 0;
    for (;;) {
      const { bytesRead } = await input.read(buffer, 0, buffer.length, null);
      if (!bytesRead) break;
      bytes += bytesRead;
      if (bytes > expectedBytes) throw Error("Qualified scanner input exceeds its pinned byte count");
      const chunk = buffer.subarray(0, bytesRead);
      hash.update(chunk); await output.writeFile(chunk);
    }
    const after = await input.stat({ bigint: true }), named = await lstat(source, { bigint: true });
    if (!named.isFile() || named.isSymbolicLink() || named.dev !== opened.dev || named.ino !== opened.ino ||
        after.size !== before.size || after.mtimeNs !== before.mtimeNs || named.size !== before.size || named.mtimeNs !== before.mtimeNs) {
      throw Error("Qualified scanner input changed while it was read");
    }
    const actual = hash.digest("hex");
    if (bytes !== expectedBytes || actual !== expectedSHA256) throw Error("Qualified scanner input digest mismatch");
    await output.sync(); await output.close(); output = undefined;
    await chmod(destination, mode);
    return { bytes, sha256: actual };
  } catch (error) {
    if (output) { await output.close(); output = undefined; }
    if (created) await rm(destination);
    throw error;
  } finally {
    if (output) await output.close();
    await input.close();
  }
}

// The runtime/provider is already qualified. Copying only these pinned files
// keeps the release builder from replacing its maintained scanner.
export async function copyVerifiedScannerBundle(destination, pins, binarySource) {
  if (typeof binarySource !== "string" || !isAbsolute(binarySource)) {
    throw Error("An explicit absolute qualified scanner bundle directory is required");
  }
  const source = resolve(binarySource), directory = await lstat(source);
  if (!directory.isDirectory() || directory.isSymbolicLink() || await realpath(source) !== source) {
    throw Error("Qualified scanner bundle must be a real directory without symlink aliases");
  }
  const target = resolve(destination), created = [];
  try {
    const binary = await copyPinnedFile(join(source, "trivy"), join(target, "trivy"), pins.binarySHA256, pins.binaryBytes, 256 * 1024 * 1024, 0o555);
    created.push(join(target, "trivy"));
    const license = await copyPinnedFile(join(source, "LICENSE"), join(target, "LICENSE"), pins.licenseSHA256, pins.licenseBytes, 1024 * 1024, 0o644);
    created.push(join(target, "LICENSE"));
    return { version: pins.version, binarySHA256: binary.sha256, binaryBytes: binary.bytes, licenseSHA256: license.sha256 };
  } catch (error) {
    for (const path of created.reverse()) await rm(path);
    throw error;
  }
}