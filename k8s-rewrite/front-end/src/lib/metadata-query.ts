import { isKvMetadataQuery } from "./kv-metadata-query";

/** Admit shared metadata by resolved route, including paths normalized by the browser. */
export function isSharedMetadataQuery(url: string): boolean {
  if (!url.startsWith("/api/")) return false;
  const parsed = new URL(url, "https://bortus.invalid");
  let path: string;
  try { path = decodeURIComponent(parsed.pathname); } catch { return false; }
  if (path.startsWith("/api/kv/")) return isKvMetadataQuery(url);
  if (!path.startsWith("/api/cluster/") && !path.startsWith("/api/flux/") &&
      !["/api/auth/session", "/api/nodes", "/api/users", "/api/settings", "/api/vars", "/api/secret-references", "/api/secrets", "/api/deploy/history"].includes(path)) return false;
  return !/\/(yaml|logs|exec)(?:\/|$)/.test(path) && !(path === "/api/secrets" && parsed.searchParams.has("key")) &&
    !(path === "/api/deploy/history" && parsed.searchParams.has("jobId"));
}
