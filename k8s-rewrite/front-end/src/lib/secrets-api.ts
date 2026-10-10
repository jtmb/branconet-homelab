import {
  SecretError,
  type SecretStore,
  type SecretTarget,
} from "./cluster-secrets";
import { secretResponse, secretErrorResponse } from "./secret-http";
type Role = "readonly" | "write" | null;
export function secretHandlers(
  getRole: () => Promise<Role>,
  getStore: () => SecretStore,
) {
  async function authorize(values: boolean) {
    const role = await getRole();
    if (!role) throw new SecretError(401, "Authentication required");
    if (values && role !== "write")
      throw new SecretError(403, "Write access required for Secret values");
  }
  return {
    async GET(request: Request) {
      try {
        const params = new URL(request.url).searchParams;
        const key = params.get("key");
        await authorize(key !== null);
        const store = getStore();
        if (key !== null)
          return secretResponse(
            await store.read({
              namespace: params.get("namespace") || "",
              name: params.get("name") || "",
              key,
            }),
          );
        return secretResponse({
          secrets: await store.list(params.get("namespace") || undefined),
        });
      } catch (error) {
        return secretErrorResponse(error);
      }
    },
    async POST(request: Request) {
      try {
        await authorize(true);
        let body;
        try {
          body = await request.json();
        } catch {
          throw new SecretError(400, "Invalid JSON request");
        }
        if (!body || typeof body !== "object")
          throw new SecretError(400, "Invalid Secret request");
        const result = await getStore().write(
          body as SecretTarget,
          body.value,
          body.mode,
          body.resourceVersion,
          body.type,
        );
        return secretResponse(
          { success: true, secret: result },
          body.mode === "create" ? 201 : 200,
        );
      } catch (error) {
        return secretErrorResponse(error);
      }
    },
    async DELETE(request: Request) {
      try {
        await authorize(true);
        let body;
        try {
          body = await request.json();
        } catch {
          throw new SecretError(400, "Invalid JSON request");
        }
        if (!body || typeof body !== "object")
          throw new SecretError(400, "Invalid Secret request");
        return secretResponse({
          success: true,
          secret: await getStore().deleteKey(body, body.resourceVersion),
        });
      } catch (error) {
        return secretErrorResponse(error);
      }
    },
  };
}
