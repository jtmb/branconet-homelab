import { SecretError } from "./cluster-secrets";
import {
  bearerAuthorized,
  secretResponse,
  secretErrorResponse,
} from "./secret-http";
export function lookupHandler(
  resolve: (key: string) => Promise<string>,
  expected: () => string | undefined,
) {
  return async (request: Request) => {
    try {
      if (!expected())
        throw new SecretError(503, "Lookup authentication is not configured");
      if (!bearerAuthorized(request.headers.get("authorization"), expected()))
        throw new SecretError(401, "Invalid Bearer authentication");
      const key = new URL(request.url).searchParams.get("key");
      if (!key) throw new SecretError(400, "Missing key parameter");
      return secretResponse({ key, value: await resolve(key) });
    } catch (error) {
      return secretErrorResponse(error);
    }
  };
}
