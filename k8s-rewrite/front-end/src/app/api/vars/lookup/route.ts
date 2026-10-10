import prisma from "@/lib/db";
import { resolveAlias } from "@/lib/secret-references";
import { nativeSecrets } from "@/lib/secret-client";
import { SecretError } from "@/lib/cluster-secrets";
import { isSensitiveVariable } from "@/lib/variable-policy";
import { lookupHandler } from "@/lib/lookup-api";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const GET = lookupHandler(
  async (key) => {
    const target = await resolveAlias(key);
    const variable = await prisma.variable.findUnique({
      where: { key },
      select: { key: true, category: true, encrypted: true },
    });
    if (target) {
      if (variable && !isSensitiveVariable(variable))
        throw new SecretError(
          409,
          "Alias collides with nonsecret configuration",
        );
      return (await nativeSecrets().read(target)).value;
    }
    if (!variable || isSensitiveVariable(variable))
      throw new SecretError(
        404,
        "Lookup key not found; sensitive keys require an explicit native Secret alias",
      );
    const config = await prisma.variable.findUnique({ where: { key } });
    if (!config || isSensitiveVariable(config))
      throw new SecretError(404, "Nonsecret configuration not found");
    return config.value;
  },
  () => process.env.BOTRUS_SECRETS_KEY,
);
