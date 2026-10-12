import { lstatSync } from "node:fs";
import path from "node:path";
import { SecretError, type FlatNativeSecretSummary } from "./cluster-secrets";
import { parsePortableFlatSecretSummaryPage } from "./secret-summary-json";

export interface FlatSummaryPage { items: FlatNativeSecretSummary[]; cursor: string }
export interface FlatSummarySelector {
  flat(chunks: Buffer[], limit: number, namespace: string): FlatSummaryPage;
}

const unavailable = () => new SecretError(503, "Invalid Kubernetes Secret summary response");
export function createNativeSelectorLoader(file: string,
  probe: (file: string) => { isFile(): boolean } = lstatSync,
  // Obtain Node's built-in loader at runtime; webpack must not replace this
  // absolute native require with a bundled module/context lookup.
  load: (file: string) => unknown = file => process.getBuiltinModule("module").createRequire(path.join(process.cwd(), "package.json"))(file)) {
  // Only executable code is shared. No response, credential or authority is cached.
  let loaded = false;
  let selector: FlatSummarySelector | undefined;
  return () => {
    if (loaded) return selector;
    let stat: { isFile(): boolean };
    try { stat = probe(file); }
    catch (error) {
      if ((error as NodeJS.ErrnoException)?.code === "ENOENT") { loaded = true; return undefined; }
      throw unavailable();
    }
    try {
      if (!stat.isFile()) throw Error();
      const addon = load(file) as FlatSummarySelector | null;
      if (!addon || typeof addon.flat !== "function") throw Error();
      selector = addon; loaded = true;
      return selector;
    } catch { throw unavailable(); }
  };
}
const nativeSelector = createNativeSelectorLoader(path.join(process.cwd(), "native", "secret-flat-selector.node"));

export const nativeFlatSummaryAvailable = () => Boolean(nativeSelector());

export function createFlatSummaryParser(addon?: FlatSummarySelector) {
  return (chunks: Buffer[], namespace: string, limit: number): FlatSummaryPage => {
    try {
      if (addon) return addon.flat(chunks, limit, namespace);
      return parsePortableFlatSecretSummaryPage(chunks, namespace, limit);
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
