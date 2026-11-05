import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { PrismaClient } from "@prisma/client";
import { readJobSlice, readJobTail } from "../src/lib/job-output";

test("SQLite returns bounded Unicode slices/tails from a two-MiB captured job without loading the full field", async context => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-job-test-"));
  const database = "file:" + path.join(dir, "job.db").replaceAll("\\", "/");
  const env: NodeJS.ProcessEnv = { ...process.env, DATABASE_URL: database }; delete env.RUST_LOG;
  let client: PrismaClient | undefined;
  try {
    execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe" });
    client = new PrismaClient({ datasources: { db: { url: database } } });
    let output = "🌍x\n".repeat(350000);
    const sourceBytes = Buffer.byteLength(output), totalChars = Array.from(output).length;
    const job = await client.job.create({ data: { playbook: "fixture.yml", status: "success", output }, select: { id: true } });
    output = "";
    const start = performance.now();
    const first = await readJobSlice(job.id, 129, client);
    const firstMs = performance.now() - start;
    assert(first); assert.equal(first.nextOffset, 129 + 4096); assert.equal(first.total, totalChars);
    assert.equal(Array.from(first.output).length, 4096); assert(first.output.startsWith("🌍x\n")); assert(Buffer.byteLength(first.output) <= 32768);
    const nearEndStart = performance.now();
    const last = await readJobSlice(job.id, totalChars - 4096, client);
    const nearEndMs = performance.now() - nearEndStart;
    assert.equal(last?.nextOffset, totalChars); assert.equal(Array.from(last!.output).length, 4096);
    const tail = await readJobTail(job.id, 7, client);
    assert(tail?.truncated); assert.equal(tail.cursor, totalChars); assert.equal(Array.from(tail.output).length, 7);
    const evidence = { capturedAt: new Date().toISOString(), node: process.version, platform: process.platform, sourceBytes, sourceCodePoints: totalChars,
      returnedFirstBytes: Buffer.byteLength(first.output), returnedLastBytes: Buffer.byteLength(last!.output), firstMs, nearEndMs,
      limitations: ["Disposable SQLite/synthetic Unicode log, no real runner/image", "Single uncontrolled observations, not latency/CPU/RSS acceptance", "No content/values recorded"] };
    context.diagnostic(JSON.stringify(evidence));
    if (process.env.BORTUS_JOB_EVIDENCE_PATH) await writeFile(path.resolve(process.env.BORTUS_JOB_EVIDENCE_PATH), JSON.stringify(evidence, null, 2) + "\n");
  } finally {
    await client?.$disconnect();
    if (!path.resolve(dir).startsWith(path.resolve(tmpdir()) + path.sep) || !path.basename(dir).startsWith("bortus-job-test-")) throw new Error("Unsafe job test cleanup target");
    await rm(dir, { recursive: true, force: true });
  }
});
