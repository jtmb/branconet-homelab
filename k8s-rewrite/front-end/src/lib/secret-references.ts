import fs from "node:fs/promises";
import prisma from "./db";
import { SecretError } from "./cluster-secrets";
import { mergeAliases, type SecretAlias } from "./secret-aliases";
export async function listAliases(): Promise<SecretAlias[]> {
  let file: SecretAlias[] = [];
  if (process.env.BORTUS_SECRET_ALIASES_FILE) {
    try {
      file = JSON.parse(
        await fs.readFile(process.env.BORTUS_SECRET_ALIASES_FILE, "utf8"),
      );
      if (!Array.isArray(file)) throw new Error();
    } catch {
      throw new SecretError(
        503,
        "Explicit alias file is unavailable or invalid",
      );
    }
  }
  return mergeAliases([file, await prisma.secretReference.findMany()]);
}
export async function resolveAlias(alias: string) {
  return (await listAliases()).find((ref) => ref.alias === alias) || null;
}
