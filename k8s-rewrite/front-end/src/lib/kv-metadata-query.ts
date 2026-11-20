/** Only named read-only KV metadata routes may enter the shared browser cache. */
export function isKvMetadataQuery(url: string): boolean {
  if (!url.startsWith("/api/kv/")) return false;
  const parsed = new URL(url, "https://bortus.invalid");
  if (url.split(/[?#]/, 1)[0] !== parsed.pathname) return false;
  if (parsed.hash) return false;
  const collectionKeys: Record<string, string[]> = {
    "/api/kv/mounts": ["cursor"], "/api/kv/paths": ["cursor", "mountId"],
    "/api/kv/policies": ["cursor"], "/api/kv/identities": ["cursor"],
    "/api/kv/audit": ["cursor", "pathId", "operationId"],
  };
  const keys = collectionKeys[parsed.pathname];
  if (keys) return [...parsed.searchParams.keys()].every(key => keys.includes(key) && parsed.searchParams.getAll(key).length === 1);
  return /^\/api\/kv\/paths\/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}(?:\/(?:capabilities|status|versions))?$/i.test(parsed.pathname)
    && [...parsed.searchParams].length === 0;
}
