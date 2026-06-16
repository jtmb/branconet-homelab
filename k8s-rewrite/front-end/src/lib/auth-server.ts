import crypto from "crypto";
import fs from "fs";
import path from "path";
import prisma from "./db";

/**
 * Ensures a JWT signing secret is available.
 * Priority: env var → DB → generate new + persist to DB and .env.local
 */
export async function ensureJwtSecret(): Promise<void> {
  // 1. Already in env — nothing to do
  if (process.env.BOTRUS_JWT_SECRET) return;

  // 2. Check database
  const existing = await prisma.variable.findUnique({
    where: { key: "system_jwt_secret" },
  });

  if (existing) {
    process.env.BOTRUS_JWT_SECRET = existing.value;
    return;
  }

  // 3. Generate new secret
  const secret = crypto.randomBytes(64).toString("hex");

  // 4. Persist to DB (source of truth)
  await prisma.variable.upsert({
    where: { key: "system_jwt_secret" },
    create: {
      key: "system_jwt_secret",
      value: secret,
      category: "system",
      encrypted: false,
    },
    update: { value: secret },
  });

  // 5. Set in-memory
  process.env.BOTRUS_JWT_SECRET = secret;

  // 6. Write to .env.local so middleware Node.js runtime can read it on next start
  const envPath = path.join(process.cwd(), ".env.local");
  try {
    let content = "";
    if (fs.existsSync(envPath)) {
      content = fs.readFileSync(envPath, "utf-8");
    }
    if (!content.includes("BOTRUS_JWT_SECRET=")) {
      fs.appendFileSync(envPath, `\nBOTRUS_JWT_SECRET=${secret}\n`);
    }
  } catch {
    console.warn(
      "Could not write BOTRUS_JWT_SECRET to .env.local — DB is source of truth"
    );
  }
}
