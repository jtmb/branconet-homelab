// Signing material only: never retain JWTs, accounts, sessions or authorization.
const unavailable = () => new Error("JWT signing key unavailable");
export class HmacKeySlot {
  private cached?: { secret: string; key: CryptoKey };
  private pending?: { secret: string; promise: Promise<CryptoKey> };
  constructor(private readonly readSecret: () => string | undefined,
    private readonly importKey: (bytes: Uint8Array<ArrayBuffer>) => Promise<CryptoKey> = bytes =>
      crypto.subtle.importKey("raw", bytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"])) {}

  async run<T>(operation: (key: CryptoKey) => Promise<T>): Promise<T> {
    const secret = this.readSecret();
    if (!secret) { this.cached = undefined; throw unavailable(); }
    if (this.cached?.secret !== secret) this.cached = undefined;
    const current = () => {
      if (this.readSecret() !== secret) {
        if (this.cached?.secret === secret) this.cached = undefined;
        throw unavailable();
      }
    };
    let key: CryptoKey;
    for (;;) {
      current();
      if (this.cached?.secret === secret) { key = this.cached.key; break; }
      if (this.pending) {
        const active = this.pending;
        try { await active.promise; }
        catch { if (active.secret === secret) throw unavailable(); }
        // A replacement waits for the old import to settle; imports never overlap.
        continue;
      }
      const pending: { secret: string; promise: Promise<CryptoKey> } = { secret, promise: Promise.resolve().then(async () => {
        const bytes = new TextEncoder().encode(secret);
        try { return await this.importKey(bytes); }
        finally { bytes.fill(0); }
      }).then(imported => {
        current(); this.cached = { secret, key: imported }; return imported;
      }).catch(() => { throw unavailable(); }).finally(() => {
        if (this.pending === pending) this.pending = undefined;
      }) };
      this.pending = pending;
    }
    current();
    const result = await operation(key);
    current();
    return result;
  }
}
