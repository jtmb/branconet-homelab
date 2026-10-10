/** Signing material is supplied independently, including via a native Secret env reference. */
export async function ensureJwtSecret(): Promise<void> {
  if (!process.env.BOTRUS_JWT_SECRET)
    throw new Error("BOTRUS_JWT_SECRET must be supplied by the operator");
}
