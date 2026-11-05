"use strict";
require("tsx/cjs");
const { PrismaClient } = require("@prisma/client");
const { AccountStore, AccountError } = require("../../src/lib/account-store.ts");
const db = new PrismaClient({ datasources: { db: { url: process.env.BORTUS_PUBLIC_TEST_DB } } });
let started = false, released = false, countCalls = 0, reportedCount = null, release;
const barrier = new Promise(resolve => { release = resolve; });
const send = message => new Promise((resolve, reject) => process.send(message, error => error ? reject(error) : resolve()));
const observed = db.$extends({ query: { user: { async count({ args, query }) {
  // Forward the supplied transaction-aware query/args exactly once; never substitute a count.
  const value = await query(args);
  if (args.where && Object.keys(args.where).length === 1 && args.where.role === "write") {
    if (++countCalls !== 1 || !Number.isInteger(value)) throw Error("Count protocol refused");
    reportedCount = value;
    await send({ kind: "final-count", value });
    await barrier;
  }
  return value;
} } } });
async function execute(input) {
  let success = false, status = null;
  try {
    await new AccountStore(observed).update(input.actor, input.target, { role: "readonly" });
    success = true;
  } catch (error) { status = error instanceof AccountError ? error.status : null; }
  await db.$disconnect();
  await send({ kind: "done", success, status, countCalls, reportedCount });
  process.disconnect();
}
async function main() {
  process.on("message", input => {
    if (input?.kind === "release" && started && countCalls === 1 && !released) {
      released = true; release(); return;
    }
    if (input?.kind === "start" && !started && input.actor && typeof input.actor.id === "string" && Number.isInteger(input.actor.sessionVersion) && typeof input.target === "string") {
      started = true;
      void execute(input).catch(() => { process.exitCode = 1; if (process.connected) process.disconnect(); });
      return;
    }
    process.exitCode = 1; if (process.connected) process.disconnect();
  });
  await db.$connect();
  await send({ kind: "ready" });
}
void main().catch(() => { process.exitCode = 1; if (process.connected) process.disconnect(); });
