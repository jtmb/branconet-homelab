import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import path from "node:path";
import { SecretError, type FlatNativeSecretSummary } from "./cluster-secrets";
import { parseSecretSummaryPage } from "./secret-summary-json";

export interface FlatSummaryPage { items: FlatNativeSecretSummary[]; cursor: string }
export interface FlatSummarySelector {
  flat(chunks: Buffer[], limit: number, namespace: string): FlatSummaryPage;
}

// Only executable code is shared. No response, credential or authority is cached.
let loaded = false;
let selector: FlatSummarySelector | undefined;
function nativeSelector() {
  if (loaded) return selector;
  const file = path.join(process.cwd(), "native", "secret-flat-selector.node");
  if (!existsSync(file)) { loaded = true; return undefined; }
  const addon = createRequire(path.join(process.cwd(), "package.json"))(file) as FlatSummarySelector;
  if (!addon || typeof addon.flat !== "function") throw Error();
  selector = addon; loaded = true;
  return selector;
}

export const nativeFlatSummaryAvailable = () => Boolean(nativeSelector());

export function createFlatSummaryParser(addon?: FlatSummarySelector) {
  return (chunks: Buffer[], namespace: string, limit: number): FlatSummaryPage => {
    try {
      if (addon) return addon.flat(chunks, limit, namespace);
      const page = parseSecretSummaryPage(chunks, namespace, limit);
      return { items: page.items.map(summary => ({ namespace: summary.metadata.namespace,
        name: summary.metadata.name, resourceVersion: summary.metadata.resourceVersion,
        type: summary.type, immutable: summary.immutable, keys: summary.keys })), cursor: page.cursor };
    } catch {
      // A native fault must never cause a second parse or a weakened fallback.
      throw new SecretError(503, "Invalid Kubernetes Secret summary response");
    }
  };
}

export function parseFlatSecretSummaryPage(chunks: Buffer[], namespace: string, limit: number): FlatSummaryPage {
  try { return createFlatSummaryParser(nativeSelector())(chunks, namespace, limit); }
  catch { throw new SecretError(503, "Invalid Kubernetes Secret summary response"); }
}
