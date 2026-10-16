"use client";

import { useCallback, useSyncExternalStore } from "react";
import { EMPTY_QUERY, QueryFailure, QuerySnapshot, QueryStore } from "./query-store";
import { isKvMetadataQuery } from "./kv-metadata-query";
import { isSharedMetadataQuery } from "./metadata-query";
import { configurationList } from "./configuration-response";

export async function requestJson<T = Record<string, unknown>>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store" });
  let data: unknown;
  if (response.status !== 204) {
    try { data = await response.json(); }
    catch {
      if (response.ok) throw new QueryFailure("Server response could not be verified. Any change may already have been saved. Refresh before trying again.", 502);
    }
  }
  if (!response.ok) {
    if (response.status === 401) {
      browserQueries.clear();
      window.dispatchEvent(new Event("bortus-session-ended"));
    }
    if (response.status === 403) browserQueries.invalidate(key => key === "/api/auth/session");
    const error = data && typeof data === "object" && "error" in data ? data.error : undefined;
    throw new QueryFailure(typeof error === "string" ? error : `Request failed (${response.status})`, response.status, data);
  }
  return data as T;
}
const browserQueries = new QueryStore({
  load: async (url, signal) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    const abort = () => controller.abort();
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) controller.abort();
    try {
      const data = await requestJson<{ authenticated?: boolean }>(url, { signal: controller.signal });
      if (url === "/api/vars") return configurationList(data);
      if (url === "/api/auth/session" && data.authenticated === false) {
        browserQueries.clear(key => key !== url);
        window.dispatchEvent(new Event("bortus-session-ended"));
      }
      return data;
    } finally { clearTimeout(timeout); signal.removeEventListener("abort", abort); }
  },
});
let subscribers = 0;
function visibility() { browserQueries.setVisible(document.visibilityState !== "hidden"); }
function focus() { if (document.visibilityState !== "hidden") browserQueries.refreshActive(); }
function retainBrowser() {
  if (subscribers++ === 0) {
    visibility();
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("focus", focus);
  }
  return () => {
    if (--subscribers === 0) {
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("focus", focus);
    }
  };
}
export function useQuery<T>(url: string, interval = 10000): QuerySnapshot<T> & { refetch: () => void } {
  if (!isSharedMetadataQuery(url))
    throw new Error("Shared queries accept only resource and session metadata.");
  const subscribe = useCallback((listener: () => void) => {
    const release = retainBrowser();
    const unsubscribe = browserQueries.subscribe(url, listener, interval);
    return () => { unsubscribe(); release(); };
  }, [url, interval]);
  const getSnapshot = useCallback(() => browserQueries.snapshot<T>(url), [url]);
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, () => EMPTY_QUERY as QuerySnapshot<T>);
  const refetch = useCallback(() => browserQueries.invalidate(key => key === url), [url]);
  return { ...snapshot, refetch };
}
export interface SessionData {
  authenticated: boolean; username?: string; role?: "write" | "readonly"; engineAdmin?: boolean; hasUsers?: boolean; registrationOpen?: boolean;
  capabilities?: { provisioning: boolean; operatorShell: boolean; podExec: boolean };
}
export function useSession() {
  const query = useQuery<SessionData>("/api/auth/session");
  const freshWriter = query.data?.authenticated === true && query.data.role === "write" && !query.error && !query.stale && Date.now() - query.updatedAt < 15000;
  return { ...query, canWrite: freshWriter && query.data?.engineAdmin === true, canKvWrite: freshWriter };
}
export function refetchCluster() { browserQueries.invalidate(url => url.startsWith("/api/cluster/") || url.startsWith("/api/flux/")); }
export function clearQueries() { browserQueries.clear(); }
export function refetchKvMetadata() { browserQueries.invalidate(url => isKvMetadataQuery(url)); }
