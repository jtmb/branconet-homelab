import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

// Backport https://github.com/vercel/next.js/pull/85418 to pinned Next 15.5.28.
// This runs before build so the standalone traced runtime receives the same fix.
const nextDirectory = process.argv[2] ?? path.resolve("node_modules/next");
const distributions = [
  ["dist/server/next-server.js", "7c97c35f81d4171ef0d5f16e18e3fe1a8e5c0bcaabf6810abdc2e92ce814a104", "2fbb30d01fdbc56632292cc48b27c8c8bdc0b3c310d4e21d3ffd3c96798fbc18"],
  ["dist/esm/server/next-server.js", "9b4c85790b1b7f1020a515d13472bdc56db4de296f78255a2e80fbba9eba6a07", "a2b130c47db4e1922f44e171e1a7378b95b2142be939326da9252d96442ca61c"],
];
const originalLine = "                    requestData.body.finalize();";
const fixedLine = "                    await requestData.body.finalize();";
const hash = (content) => createHash("sha256").update(content).digest("hex");

try {
  const manifest = JSON.parse(readFileSync(path.join(nextDirectory, "package.json"), "utf8"));
  if (manifest.version !== "15.5.28") throw new Error("Unsupported Next version");
  const verified = distributions.map(([file, originalHash, patchedHash]) => {
    const serverPath = path.join(nextDirectory, file);
    const bytes = readFileSync(serverPath);
    const source = bytes.toString("utf8");
    if (hash(bytes) === originalHash && source.split(originalLine).length === 2) {
      const patched = source.replace(originalLine, fixedLine);
      if (hash(patched) !== patchedHash) throw new Error("Unexpected Next patched source");
      return { serverPath, source: patched, changed: true };
    }
    if (hash(bytes) === patchedHash && source.split(fixedLine).length === 2 && hash(source.replace(fixedLine, originalLine)) === originalHash) {
      return { serverPath, source, changed: false };
    }
    throw new Error("Unexpected Next server source");
  });
  // Verify both formats before modifying either file.
  for (const item of verified) {
    if (item.changed) writeFileSync(item.serverPath, item.source);
  }
  console.log("Verified Next 15.5.28 middleware body finalization backport in CJS and ESM");
} catch {
  console.error("Next middleware backport verification failed; installation/build stopped");
  process.exitCode = 1;
}
