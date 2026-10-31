import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";

const patcher = path.resolve("scripts/patch-next-body-finalize.mjs");
const oldLine = "                    requestData.body.finalize();";
const newLine = "                    await requestData.body.finalize();";
const installed = readFileSync("node_modules/next/dist/server/next-server.js", "utf8");
const original = installed.replace(newLine, oldLine);
const originalEsm = readFileSync("node_modules/next/dist/esm/server/next-server.js", "utf8").replace(newLine, oldLine);
const hash = (text: string) => createHash("sha256").update(text).digest("hex");

function fixture(version = "15.5.28", source = original) {
  const directory = mkdtempSync(path.join(tmpdir(), "bortus-next-backport-"));
  mkdirSync(path.join(directory, "dist/server"), { recursive: true });
  mkdirSync(path.join(directory, "dist/esm/server"), { recursive: true });
  writeFileSync(path.join(directory, "package.json"), JSON.stringify({ version }));
  const server = path.join(directory, "dist/server/next-server.js");
  writeFileSync(server, source);
  const esm = path.join(directory, "dist/esm/server/next-server.js");
  writeFileSync(esm, originalEsm);
  return { directory, server, esm };
}

test("pinned Next middleware finalization backport changes exactly one await and is idempotent", () => {
  assert.equal(hash(original), "7c97c35f81d4171ef0d5f16e18e3fe1a8e5c0bcaabf6810abdc2e92ce814a104");
  assert.equal(hash(originalEsm), "9b4c85790b1b7f1020a515d13472bdc56db4de296f78255a2e80fbba9eba6a07");
  const item = fixture();
  try {
    execFileSync(process.execPath, [patcher, item.directory]);
    const patched = readFileSync(item.server, "utf8");
    assert.equal(patched, original.replace(oldLine, newLine));
    assert.equal(hash(patched), "2fbb30d01fdbc56632292cc48b27c8c8bdc0b3c310d4e21d3ffd3c96798fbc18");
    assert.equal(readFileSync(item.esm, "utf8"), originalEsm.replace(oldLine, newLine));
    assert.equal(hash(readFileSync(item.esm, "utf8")), "a2b130c47db4e1922f44e171e1a7378b95b2142be939326da9252d96442ca61c");
    execFileSync(process.execPath, [patcher, item.directory]);
    assert.equal(readFileSync(item.server, "utf8"), patched);
    assert.equal(readFileSync(item.esm, "utf8"), originalEsm.replace(oldLine, newLine));
  } finally { rmSync(item.directory, { recursive: true, force: true }); }
});

test("drift in the ESM distribution refuses the whole patch before modifying CJS", () => {
  const item = fixture();
  try {
    writeFileSync(item.esm, originalEsm + "\n// drift");
    assert.equal(spawnSync(process.execPath, [patcher, item.directory]).status, 1);
    assert.equal(readFileSync(item.server, "utf8"), original);
    assert.equal(readFileSync(item.esm, "utf8"), originalEsm + "\n// drift");
  } finally { rmSync(item.directory, { recursive: true, force: true }); }
});

test("Next backport refuses other versions and unrecognized source without modifying either", () => {
  for (const [version, source] of [["15.5.27", original], ["15.5.29", original], ["15.5.28", original + "\n// source drift"], ["15.5.28", original.replace(oldLine, newLine) + "\n// patched source drift"]]) {
    const item = fixture(version, source);
    try {
      const result = spawnSync(process.execPath, [patcher, item.directory], { encoding: "utf8" });
      assert.equal(result.status, 1);
      assert.equal(readFileSync(item.server, "utf8"), source);
      assert.equal(readFileSync(item.esm, "utf8"), originalEsm);
      assert.match(result.stderr, /verification failed/);
    } finally { rmSync(item.directory, { recursive: true, force: true }); }
  }
});
