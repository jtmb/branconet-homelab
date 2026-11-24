import test from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import { spawnSync } from "node:child_process"
import { fileURLToPath } from "node:url"

test("ConfigMap-like symlink starts CLI and fails closed on absent enrollment, not silent exit0", () => {
  assert.equal(fs.existsSync("/controller/enrollment.json"), false)
  const root = process.env.BORTUS_ROTATION_TEST_TMP
  assert.ok(root?.startsWith("/mnt/h/AgentArtifacts/projects/branconet/"))
  const dir = fs.mkdtempSync(path.join(root, "entrypoint-"))
  const link = path.join(dir, "controller.mjs")
  try {
    fs.symlinkSync(fileURLToPath(new URL("./controller.mjs", import.meta.url)), link)
    const child = spawnSync(process.execPath, [link], { encoding: "utf8", timeout: 10000,
      env: { ...process.env, NODE_DISABLE_COMPILE_CACHE: "1" } })
    assert.equal(child.status, 1)
    assert.deepEqual(JSON.parse(child.stdout), {
      state: "attention", reason: "observation_or_mutation_unknown",
    })
  } finally {
    assert.equal(fs.lstatSync(link).isSymbolicLink(), true)
    fs.unlinkSync(link)
    fs.rmdirSync(dir)
  }
})
