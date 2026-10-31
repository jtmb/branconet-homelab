"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SecretError = void 0;
exports.validateTarget = validateTarget;
exports.nativeAsciiValueSpan = nativeAsciiValueSpan;
exports.parseSecretSummaryPage = parseSecretSummaryPage;
class SecretError extends Error {
    status;
    constructor(status, message) {
        super(message);
        this.status = status;
    }
}
exports.SecretError = SecretError;
const dnsLabel = /^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$/;
const dnsName = /^[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?$/;
function validateTarget(target) {
    if (!target ||
        typeof target.namespace !== "string" ||
        target.namespace.length > 63 ||
        !dnsLabel.test(target.namespace) ||
        typeof target.name !== "string" ||
        target.name.length > 253 ||
        !dnsName.test(target.name) ||
        target.name
            .split(".")
            .some((label) => label.length > 63 || !dnsLabel.test(label)) ||
        typeof target.key !== "string" ||
        target.key.length > 253 ||
        !/^[-._a-zA-Z0-9]+$/.test(target.key)) {
        throw new SecretError(400, "Explicit namespace, Secret name and data key are required");
    }
    return target;
}
// A bounded view of unselected native value bytes; never decode or copy them.
// A quote, escape, raw control or high byte leaves the scalar grammar in charge.
function nativeAsciiValueSpan(chunk, start) {
    if (chunk.length - start < 4096)
        return 0;
    const window = chunk.subarray(start, start + 4096);
    let end = window.indexOf(34);
    if (end < 0)
        end = window.length;
    if (end < 256)
        return 0;
    const escape = window.subarray(0, end).indexOf(92);
    if (escape >= 0)
        end = escape;
    if (end < 256)
        return 0;
    const span = window.subarray(0, end);
    if (!isAscii(span))
        return 0;
    for (let control = 0; control < 32; control++)
        if (span.indexOf(control) >= 0)
            return 0;
    return end;
}
const invalid = () => new SecretError(503, "Invalid Kubernetes Secret summary response");
// Validate the entire bounded JSON document. Only selected metadata and key names
// are decoded; native data/stringData and unknown-field values stay in byte form.
class Reader {
    chunks;
    index = 0;
    offset = 0;
    decoder = new TextDecoder("utf-8", { fatal: true });
    constructor(chunks) {
        this.chunks = chunks;
    }
    peek() {
        while (this.index < this.chunks.length && this.offset === this.chunks[this.index].length) {
            this.index++;
            this.offset = 0;
        }
        return this.index < this.chunks.length ? this.chunks[this.index][this.offset] : -1;
    }
    take() { const byte = this.peek(); if (byte >= 0)
        this.offset++; return byte; }
    expect(byte) { if (this.take() !== byte)
        throw invalid(); }
    space() { while ([32, 9, 10, 13].includes(this.peek()))
        this.take(); }
    hex(byte) { return byte >= 48 && byte <= 57 || byte >= 65 && byte <= 70 || byte >= 97 && byte <= 102; }
    string() {
        this.expect(34);
        let plainAscii = true;
        for (;;) {
            if (this.peek() < 0)
                throw invalid();
            const chunk = this.chunks[this.index];
            while (this.offset + 4 <= chunk.length) {
                const word = chunk.readUInt32LE(this.offset);
                if ((word & 0x80808080) !== 0 || ((word + 0x60606060) & 0x80808080) !== (0x80808080 | 0))
                    break;
                const quote = word ^ 0x22222222, escape = word ^ 0x5c5c5c5c;
                if (((quote - 0x01010101) & ~quote & 0x80808080) !== 0 || ((escape - 0x01010101) & ~escape & 0x80808080) !== 0)
                    break;
                this.offset += 4;
            }
            while (this.offset < chunk.length && chunk[this.offset] >= 32 && chunk[this.offset] < 128 && chunk[this.offset] !== 34 && chunk[this.offset] !== 92)
                this.offset++;
            if (this.offset === chunk.length)
                continue;
            const byte = this.take();
            if (byte === 34)
                return plainAscii;
            if (byte === 92) {
                plainAscii = false;
                const escaped = this.take();
                if (escaped === 117) {
                    for (let i = 0; i < 4; i++)
                        if (!this.hex(this.take()))
                            throw invalid();
                }
                else if (![34, 92, 47, 98, 102, 110, 114, 116].includes(escaped))
                    throw invalid();
            }
            else if (byte >= 128) {
                plainAscii = false;
                const length = byte >= 194 && byte <= 223 ? 1 : byte >= 224 && byte <= 239 ? 2 : byte >= 240 && byte <= 244 ? 3 : -1;
                if (length < 0)
                    throw invalid();
                for (let i = 0; i < length; i++) {
                    const next = this.take();
                    if (next < 128 || next > 191 || i === 0 && (byte === 224 && next < 160 || byte === 237 && next > 159 || byte === 240 && next < 144 || byte === 244 && next > 143))
                        throw invalid();
                }
            }
            else
                throw invalid();
        }
    }
    longString() {
        this.expect(34);
        let plainAscii = true;
        for (;;) {
            if (this.peek() < 0)
                throw invalid();
            const chunk = this.chunks[this.index];
            const advanced = nativeAsciiValueSpan(chunk, this.offset);
            if (advanced) {
                this.offset += advanced;
                continue;
            }
            while (this.offset + 4 <= chunk.length) {
                const word = chunk.readUInt32LE(this.offset);
                if ((word & 0x80808080) !== 0 || ((word + 0x60606060) & 0x80808080) !== (0x80808080 | 0))
                    break;
                const quote = word ^ 0x22222222, escape = word ^ 0x5c5c5c5c;
                if (((quote - 0x01010101) & ~quote & 0x80808080) !== 0 || ((escape - 0x01010101) & ~escape & 0x80808080) !== 0)
                    break;
                this.offset += 4;
            }
            while (this.offset < chunk.length && chunk[this.offset] >= 32 && chunk[this.offset] < 128 && chunk[this.offset] !== 34 && chunk[this.offset] !== 92)
                this.offset++;
            if (this.offset === chunk.length)
                continue;
            const byte = this.take();
            if (byte === 34)
                return plainAscii;
            if (byte === 92) {
                plainAscii = false;
                const escaped = this.take();
                if (escaped === 117) {
                    for (let i = 0; i < 4; i++)
                        if (!this.hex(this.take()))
                            throw invalid();
                }
                else if (![34, 92, 47, 98, 102, 110, 114, 116].includes(escaped))
                    throw invalid();
            }
            else if (byte >= 128) {
                plainAscii = false;
                const length = byte >= 194 && byte <= 223 ? 1 : byte >= 224 && byte <= 239 ? 2 : byte >= 240 && byte <= 244 ? 3 : -1;
                if (length < 0)
                    throw invalid();
                for (let i = 0; i < length; i++) {
                    const next = this.take();
                    if (next < 128 || next > 191 || i === 0 && (byte === 224 && next < 160 || byte === 237 && next > 159 || byte === 240 && next < 144 || byte === 244 && next > 143))
                        throw invalid();
                }
            }
            else
                throw invalid();
        }
    }
    valueString() {
        this.peek();
        const chunk = this.chunks[this.index];
        return chunk && chunk.length - this.offset >= 4096 ? this.longString() : this.string();
    }
    literal(text) { for (let i = 0; i < text.length; i++)
        this.expect(text.charCodeAt(i)); }
    skip(depth = 0, nativeValues = false) {
        if (depth > 32)
            throw invalid();
        this.space();
        let byte = this.peek();
        if (byte === 34) {
            if (nativeValues)
                this.valueString();
            else
                this.string();
            return;
        }
        if (byte === 123 || byte === 91) {
            const object = byte === 123, end = object ? 125 : 93;
            this.take();
            this.space();
            if (this.peek() === end) {
                this.take();
                return;
            }
            for (;;) {
                if (object) {
                    this.string();
                    this.space();
                    this.expect(58);
                }
                this.skip(depth + 1, nativeValues);
                this.space();
                byte = this.take();
                if (byte === end)
                    return;
                if (byte !== 44)
                    throw invalid();
                this.space();
            }
        }
        if (byte === 116) {
            this.literal("true");
            return;
        }
        if (byte === 102) {
            this.literal("false");
            return;
        }
        if (byte === 110) {
            this.literal("null");
            return;
        }
        if (byte === 45) {
            this.take();
            byte = this.peek();
        }
        const digit = (n) => n >= 48 && n <= 57;
        if (byte === 48)
            this.take();
        else if (byte >= 49 && byte <= 57) {
            do {
                this.take();
            } while (digit(this.peek()));
        }
        else
            throw invalid();
        if (this.peek() === 46) {
            this.take();
            if (!digit(this.peek()))
                throw invalid();
            do {
                this.take();
            } while (digit(this.peek()));
        }
        if (this.peek() === 101 || this.peek() === 69) {
            this.take();
            if (this.peek() === 43 || this.peek() === 45)
                this.take();
            if (!digit(this.peek()))
                throw invalid();
            do {
                this.take();
            } while (digit(this.peek()));
        }
    }
    capture(parse, selectedString = false) {
        this.space();
        this.peek();
        const startIndex = this.index, startOffset = this.offset;
        const plainAscii = parse();
        // The complete grammar above already rejected control/invalid bytes. ASCII
        // decoding is safe only for an unescaped selected string in this one chunk.
        if (selectedString && plainAscii === true && startIndex === this.index) {
            return this.chunks[startIndex].toString("ascii", startOffset + 1, this.offset - 1);
        }
        const pieces = [];
        for (let i = startIndex; i <= this.index && i < this.chunks.length; i++) {
            const end = i === this.index ? this.offset : this.chunks[i].length;
            pieces.push(this.chunks[i].subarray(i === startIndex ? startOffset : 0, end));
        }
        const selected = pieces.length === 1 ? pieces[0] : Buffer.concat(pieces);
        return JSON.parse(this.decoder.decode(selected));
    }
    text() { return this.capture(() => this.string(), true); }
    members(member) {
        this.space();
        this.expect(123);
        this.space();
        if (this.peek() === 125) {
            this.take();
            return;
        }
        for (;;) {
            const key = this.text();
            this.space();
            this.expect(58);
            this.space();
            member(key);
            this.space();
            const byte = this.take();
            if (byte === 125)
                return;
            if (byte !== 44)
                throw invalid();
            this.space();
        }
    }
}
function parseSecretSummaryPage(chunks, namespace, limit) {
    try {
        if (!Number.isSafeInteger(limit) || limit < 1 || limit > 200 || chunks.length > 16384 || chunks.reduce((n, b) => n + b.length, 0) > 4 * 1024 * 1024)
            throw invalid();
        const reader = new Reader(chunks), items = [];
        let seen = 0;
        let version, kind, cursor = "", haveItems = false;
        const item = () => {
            let fields = 0;
            let apiVersion, kind, metadata;
            let type = "Opaque", immutable = false;
            const keys = new Set();
            reader.members(key => {
                const bit = key === "apiVersion" ? 1 : key === "kind" ? 2 : key === "metadata" ? 4 : key === "data" ? 8 : key === "stringData" ? 16 : key === "type" ? 32 : key === "immutable" ? 64 : 0;
                if (bit) {
                    if (fields & bit)
                        throw invalid();
                    fields |= bit;
                }
                if (key === "apiVersion")
                    apiVersion = reader.text();
                else if (key === "kind")
                    kind = reader.text();
                else if (key === "type")
                    type = reader.text() || "Opaque";
                else if (key === "immutable") {
                    if (reader.peek() !== 116 && reader.peek() !== 102)
                        throw invalid();
                    const value = reader.capture(() => reader.skip(2));
                    if (typeof value !== "boolean")
                        throw invalid();
                    immutable = value;
                }
                else if (key === "metadata") {
                    if (reader.peek() !== 123)
                        throw invalid();
                    const value = reader.capture(() => reader.skip(2));
                    if (!value || typeof value !== "object" || Array.isArray(value))
                        throw invalid();
                    metadata = value;
                }
                else if (key === "data" || key === "stringData") {
                    reader.members(name => { reader.valueString(); if (key === "data")
                        keys.add(name); });
                }
                else
                    reader.skip(2, true);
            });
            if (apiVersion !== "v1" || kind !== "Secret" || !metadata || metadata.namespace !== namespace || typeof metadata.name !== "string" ||
                metadata.uid !== undefined && typeof metadata.uid !== "string" || metadata.resourceVersion !== undefined && typeof metadata.resourceVersion !== "string")
                throw invalid();
            validateTarget({ namespace, name: metadata.name, key: "validation" });
            return { metadata, type, immutable, keys: [...keys].sort() };
        };
        reader.members(key => {
            const bit = key === "apiVersion" ? 1 : key === "kind" ? 2 : key === "metadata" ? 4 : key === "items" ? 8 : 0;
            if (bit) {
                if (seen & bit)
                    throw invalid();
                seen |= bit;
            }
            if (key === "apiVersion")
                version = reader.text();
            else if (key === "kind")
                kind = reader.text();
            else if (key === "metadata") {
                if (reader.peek() !== 123)
                    throw invalid();
                const value = reader.capture(() => reader.skip(1));
                if (!value || typeof value !== "object" || Array.isArray(value))
                    throw invalid();
                const next = value.continue;
                if (next !== undefined && typeof next !== "string")
                    throw invalid();
                cursor = next || "";
                if (cursor.length > 8192)
                    throw invalid();
            }
            else if (key === "items") {
                haveItems = true;
                reader.expect(91);
                reader.space();
                if (reader.peek() === 93) {
                    reader.take();
                    return;
                }
                for (;;) {
                    if (items.length >= limit)
                        throw invalid();
                    items.push(item());
                    reader.space();
                    const byte = reader.take();
                    if (byte === 93)
                        return;
                    if (byte !== 44)
                        throw invalid();
                    reader.space();
                }
            }
            else
                reader.skip(1, true);
        });
        reader.space();
        if (reader.peek() !== -1 || version !== "v1" || kind !== "SecretList" || !haveItems)
            throw invalid();
        return { items, cursor };
    }
    catch {
        throw invalid();
    }
}
globalThis.Reader = Reader;
globalThis.parse = parseSecretSummaryPage;
