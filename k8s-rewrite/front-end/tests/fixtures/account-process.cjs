"use strict";
require("tsx/cjs");
const { PrismaClient } = require("@prisma/client");
const { AccountStore, AccountError } = require("../../src/lib/account-store.ts");
const db = new PrismaClient({ datasources: { db: { url: process.env.BORTUS_PUBLIC_TEST_DB } } });
const store = new AccountStore(db);
process.once("message", async input => {
  let outcome;
  try {
    if (input.action === "delete") await store.delete(input.actor, input.target);
    else await store.update(input.actor, input.target, { role: "readonly" });
    outcome = { kind: "done", success: true, status: null };
  } catch (error) {
    outcome = { kind: "done", success: false, status: error instanceof AccountError ? error.status : null };
  } finally {
    await db.$disconnect();
    process.send(outcome, () => process.disconnect());
  }
});
process.send({ kind: "ready" });
