// Standalone public diagnostic, deliberately outside the ordinary *.test.ts glob.
// Output is numeric/fixed metadata only; no rows, subjects, paths or error details.
import assert from "node:assert/strict";
import { isDeepStrictEqual } from "node:util";
import { execFileSync } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { PrismaClient } from "@prisma/client";
import { DirectAccountReader } from "../src/lib/direct-account-reader";

async function main() {
const started = performance.now(), deadline = started + 60000;
const dir = await mkdtemp(path.join(tmpdir(), "bortus-direct-cost-"));
const url = `file:${path.join(dir, "public.db").replaceAll("\\", "/")}`;
const env: NodeJS.ProcessEnv = { ...process.env, DATABASE_URL: url }; delete env.RUST_LOG;
let prisma: PrismaClient | undefined, reader: DirectAccountReader | undefined;
const clients: PrismaClient[] = [], readers: DirectAccountReader[] = [];
const observations: { backend: number; ordinal: number; boundaryPairs: number; elapsedMs: number; cpuUs: number; rssBytes: number; heapUsedBytes: number; timerTicks: number; maxTimerLatenessMs: number; processPeakRssKiB: number }[] = [];
const within = () => assert.ok(performance.now() < deadline, "Public diagnostic60s deadline");
const parity = (a: unknown, b: unknown) => assert.ok(isDeepStrictEqual(a, b), "Original typed row parity");
try {
  assert.equal(process.version, "v22.23.3"); assert.notEqual(process.getuid?.(), 0);
  execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env, stdio: "pipe", timeout: 20000 });
  prisma = new PrismaClient({ datasources: { db: { url } } }); clients.push(prisma);
  reader = new DirectAccountReader(() => url); readers.push(reader);
  const user = await prisma.user.create({ data: { username: "public-cost", passwordHash: "unused-public-fixture", role: "write", engineAdmin: true } });
  const session = () => prisma!.user.findUnique({ where: { id: user.id }, select: { id: true, username: true, sessionVersion: true } });
  const account = () => prisma!.user.findUnique({ where: { id: user.id }, select: { id: true, username: true, sessionVersion: true, role: true, engineAdmin: true } });
  parity(await reader.readSession(user.id), await session()); parity(await reader.readAccount(user.id), await account());
  await prisma.user.update({ where: { id: user.id }, data: { sessionVersion: 1, role: "readonly", engineAdmin: false } });
  parity(await reader.readSession(user.id), await session()); parity(await reader.readAccount(user.id), await account());
  assert.equal(await reader.readAccount("absent-public-subject"), null);
  assert.deepEqual(reader.activity(), { active: 0, queued: 0, closing: false, closeFailed: false });
  let timerTicks = 0, maxTimerLatenessMs = 0, intervalMaxLatenessMs = 0, expected = performance.now() + 5;
  const timer = setInterval(() => { const now = performance.now(); timerTicks++; maxTimerLatenessMs = Math.max(maxTimerLatenessMs, now - expected);
    intervalMaxLatenessMs = Math.max(intervalMaxLatenessMs, now - expected); expected = now + 5; }, 5);
  try {
    for (let pair = 0; pair < 12; pair++) {
      for (const backend of pair % 2 ? [1, 0] : [0, 1]) {
        within(); const before = performance.now(), cpu = process.cpuUsage(), beforeTicks = timerTicks; intervalMaxLatenessMs = 0;
        for (let i = 0; i < 100; i++) {
          within();
          if (backend === 0) { await session(); await account(); }
          else { await reader.readSession(user.id); await reader.readAccount(user.id); }
        }
        const elapsedMs = performance.now() - before, used = process.cpuUsage(cpu), memory = process.memoryUsage();
        observations.push({ backend, ordinal: pair + 1, boundaryPairs: 100, elapsedMs, cpuUs: used.user + used.system, rssBytes: memory.rss, heapUsedBytes: memory.heapUsed,
          timerTicks: timerTicks - beforeTicks, maxTimerLatenessMs: intervalMaxLatenessMs, processPeakRssKiB: process.resourceUsage().maxRSS });
      }
    }
  } finally { clearInterval(timer); }
  within(); assert.equal(observations.length, 24);
  const coldConnections = [];
  for (const backend of [0, 1]) {
    const began = performance.now();
    if (backend === 0) {
      const fresh = new PrismaClient({ datasources: { db: { url } } }); clients.push(fresh);
      await fresh.user.findUnique({ where: { id: user.id }, select: { id: true, username: true, sessionVersion: true } }); await fresh.$disconnect();
    } else {
      const fresh = new DirectAccountReader(() => url); readers.push(fresh); await fresh.readSession(user.id); await fresh.close();
    }
    coldConnections.push({ backend, elapsedMsIncludingClose: performance.now() - began }); within();
  }
  const sorted = (backend: number) => observations.filter(row => row.backend === backend).map(row => row.elapsedMs).sort((a, b) => a - b);
  const median = (rows: number[]) => (rows[5] + rows[6]) / 2;
  const baseline = sorted(0), proposed = sorted(1);
  await Promise.all(readers.map(value => value.close())); await Promise.all(clients.map(value => value.$disconnect()));
  assert.ok(readers.every(value => value.activity().active === 0 && value.activity().queued === 0));
  process.stdout.write(JSON.stringify({ actualExit: 0, complete: true, diagnosticOnly: true, productionAdoption: false,
    controlsPassed: 6, exactNodeVersion: process.version, sqliteExperimental: true, observations,
    coldConnections, coldDefinition: "New connection after controls; module and filesystem already exercised; includes close, not process startup",
    timerTicks, maxTimerLatenessMs, allOwnersDrained: true,
    median100BoundaryPairsMs: { prisma: median(baseline), direct: median(proposed) },
    p95_100BoundaryPairsMs: { prisma: baseline[11], direct: proposed[11] },
    healthyCostGainObserved: median(proposed) < median(baseline),
    acceptanceOrHTTPBenefitClaimed: false, kernelIOHardBoundClaimed: false }) + "\n");
} finally {
  await Promise.all(readers.map(value => value.close())); await Promise.all(clients.map(value => value.$disconnect()));
  if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-direct-cost-")) throw Error("Unsafe public cost fixture cleanup");
  await rm(dir, { recursive: true, force: true });
}
}
void main().catch(() => { process.stdout.write(JSON.stringify({ actualExit: 1, complete: false, diagnosticOnly: true,
  fixedFailure: "PUBLIC_DIRECT_ACCOUNT_DIAGNOSTIC_REFUSED" }) + "\n"); process.exitCode = 1; });
