import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

test("Prisma 6 config loading, validation and forward deploy work with the scoped merger override", { timeout: 90000 }, async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-prisma-config-"));
  const database = `file:${path.join(dir, "fixture.db").replaceAll("\\", "/")}`;
  const env: NodeJS.ProcessEnv = { ...process.env, DATABASE_URL: database };
  delete env.RUST_LOG;
  try {
    const localRequire = createRequire(path.resolve("package.json"));
    const configEntry = localRequire.resolve("@prisma/config");
    const configRequire = createRequire(configEntry);
    const mergerEntry = configRequire.resolve("deepmerge-ts");
    const merger = JSON.parse(await readFile(path.join(path.dirname(mergerEntry), "../package.json"), "utf8"));
    assert.equal(merger.version, "8.0.0");
    const configPath = path.join(dir, "prisma.config.cjs");
    await writeFile(configPath, `const { defineConfig } = require(${JSON.stringify(configEntry)});\nmodule.exports = defineConfig({ schema: ${JSON.stringify(path.resolve("prisma/schema.prisma"))}, migrations: { path: ${JSON.stringify(path.resolve("prisma/migrations"))} } });\n`);
    const cli = path.resolve("node_modules/prisma/build/index.js");
    const run = (args: string[]) => execFileSync(process.execPath, [cli, ...args, "--config", configPath], { env, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    assert.match(run(["validate"]), /is valid/);
    assert.match(run(["migrate", "deploy"]), /All migrations have been successfully applied/);
    assert.match(run(["migrate", "deploy"]), /No pending migrations/);
    assert.match(run(["migrate", "diff", "--from-url", database, "--to-schema-datamodel", path.resolve("prisma/schema.prisma"), "--script"]), /empty migration/i);
  } finally {
    assert.equal(path.dirname(path.resolve(dir)), path.resolve(tmpdir()));
    assert(path.basename(dir).startsWith("bortus-prisma-config-"));
    await rm(dir, { recursive: true, force: true });
  }
});
