import { createReadStream } from "node:fs";
import fs from "node:fs/promises";
import { SecretError } from "./cluster-secrets";
import { MetadataCache } from "./metadata-cache";
import { mergeAliases, type SecretAlias } from "./secret-aliases";

export const MAX_ALIASES = 10000;
export const ALIAS_FILE_BYTES = 1024 * 1024;
export async function readAliasFile(path: string, signal: AbortSignal): Promise<SecretAlias[]> {
  if (!path) return [];
  try {
    const stat = await fs.stat(path);
    if (signal.aborted || !stat.isFile() || stat.size > ALIAS_FILE_BYTES) throw Error();
    const stream = createReadStream(path, { highWaterMark: 65536, signal }), chunks: Buffer[] = [];
    let bytes = 0;
    try {
      for await (const chunk of stream) {
        bytes += chunk.length;
        if (bytes > ALIAS_FILE_BYTES) throw Error();
        chunks.push(chunk as Buffer);
      }
    } finally { stream.destroy(); }
    const rows = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks)));
    if (!Array.isArray(rows) || rows.length > MAX_ALIASES) throw Error();
    return rows;
  } catch { throw new SecretError(503, "Explicit alias file is unavailable, invalid or exceeds its limit"); }
}

export class AliasCatalog {
  readonly cache: MetadataCache<{ rows: SecretAlias[]; index: Map<string, SecretAlias> }>;
  constructor(load: (key: string, signal: AbortSignal) => Promise<SecretAlias[][]>, now: () => number = Date.now) {
    this.cache = new MetadataCache(async (key, signal) => {
      const groups = await load(key, signal);
      if (groups.some(group => !Array.isArray(group) || group.length > MAX_ALIASES)) throw new SecretError(503, "Alias metadata exceeds the limit");
      let rows: SecretAlias[];
      try { rows = mergeAliases(groups); }
      catch (error) { if (error instanceof SecretError && error.status === 409) throw error; throw new SecretError(503, "Explicit alias metadata is invalid"); }
      if (rows.length > MAX_ALIASES) throw new SecretError(503, "Alias metadata exceeds the limit");
      rows.sort((a, b) => a.alias < b.alias ? -1 : a.alias > b.alias ? 1 : 0);
      return { rows, index: new Map(rows.map(ref => [ref.alias, ref])) };
    }, 10000, 5000, now);
  }
  invalidate() { this.cache.invalidate(); }
  async list(key: string) { return (await this.cache.get(key)).rows.map(ref => ({ ...ref })); }
  async resolve(key: string, alias: string) { const ref = (await this.cache.get(key)).index.get(alias); return ref ? { ...ref } : null; }
}
