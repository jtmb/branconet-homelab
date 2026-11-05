"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.rejectedSecretListItemCount = rejectedSecretListItemCount;
function advanceAscii(chunk, start) { const window = chunk.subarray(start, Math.min(chunk.length, start + 4096)); let end = window.indexOf(34); if (end < 0)
    end = window.length; if (end < 256)
    return 0; const escape = window.subarray(0, end).indexOf(92); if (escape >= 0)
    end = escape; if (end < 256)
    return 0; const span = window.subarray(0, end); if (!isAscii(span))
    return 0; for (let control = 0; control < 32; control++)
    if (span.indexOf(control) >= 0)
        return 0; return end; }
const invalid = () => new Error("Invalid summary");
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
            if (chunk.length - this.offset >= 16384) {
                const advanced = advanceAscii(chunk, this.offset);
                if (advanced) {
                    this.offset += advanced;
                    continue;
                }
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
    valueString() { this.peek(); const chunk = this.chunks[this.index]; return chunk && chunk.length - this.offset >= 16384 ? this.longString() : this.string(); }
    literal(text) { for (let i = 0; i < text.length; i++)
        this.expect(text.charCodeAt(i)); }
    skip(depth = 0) {
        if (depth > 32)
            throw invalid();
        this.space();
        let byte = this.peek();
        if (byte === 34) {
            this.valueString();
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
                this.skip(depth + 1);
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
function rejectedSecretListItemCount(chunks, limit) {
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 200)
        return;
    let length = 0;
    if (chunks.length > 16384)
        return;
    for (const chunk of chunks) {
        length += chunk.length;
        if (length > 4 * 1024 * 1024)
            return;
    }
    let chunkIndex = 0, offset = 0;
    const peek = () => {
        while (chunkIndex < chunks.length && offset === chunks[chunkIndex].length) {
            chunkIndex++;
            offset = 0;
        }
        return chunkIndex < chunks.length ? chunks[chunkIndex][offset] : -1;
    };
    const take = () => { const byte = peek(); if (byte >= 0)
        offset++; return byte; };
    const space = () => { for (;;) {
        const byte = peek();
        if (byte !== 32 && byte !== 9 && byte !== 10 && byte !== 13)
            return;
        take();
    } };
    const hex = (byte) => byte >= 48 && byte <= 57 || byte >= 65 && byte <= 70 || byte >= 97 && byte <= 102;
    // 1 complete, 0 valid unfinished prefix, -1 malformed/unavailable.
    const string = () => {
        if (take() !== 34)
            return -1;
        for (;;) {
            let byte = peek();
            if (byte < 0)
                return 0;
            // Large native base64 strings usually stay in this direct, allocation-free ASCII loop.
            const chunk = chunks[chunkIndex];
            // Skip four unescaped ASCII string bytes at a time without decoding or
            // copying them. Zero-byte detection may stop early through a borrow, but
            // never skips a quote/backslash; the scalar grammar remains authoritative.
            while (offset + 4 <= chunk.length) {
                const word = chunk.readUInt32LE(offset);
                if ((word & 0x80808080) !== 0 || ((word + 0x60606060) & 0x80808080) !== (0x80808080 | 0))
                    break;
                const quote = word ^ 0x22222222, escape = word ^ 0x5c5c5c5c;
                if (((quote - 0x01010101) & ~quote & 0x80808080) !== 0 ||
                    ((escape - 0x01010101) & ~escape & 0x80808080) !== 0)
                    break;
                offset += 4;
            }
            while (offset < chunk.length && chunk[offset] >= 32 && chunk[offset] < 128 && chunk[offset] !== 34 && chunk[offset] !== 92)
                offset++;
            if (offset === chunk.length)
                continue;
            byte = take();
            if (byte < 0)
                return 0;
            if (byte === 34)
                return 1;
            if (byte === 92) {
                const escaped = take();
                if (escaped < 0)
                    return 0;
                if (escaped === 117) {
                    for (let i = 0; i < 4; i++) {
                        const digit = take();
                        if (digit < 0)
                            return 0;
                        if (!hex(digit))
                            return -1;
                    }
                }
                else if (escaped !== 34 && escaped !== 92 && escaped !== 47 && escaped !== 98 && escaped !== 102 && escaped !== 110 && escaped !== 114 && escaped !== 116)
                    return -1;
            }
            else if (byte >= 128) {
                const length = byte >= 194 && byte <= 223 ? 1 : byte >= 224 && byte <= 239 ? 2 : byte >= 240 && byte <= 244 ? 3 : -1;
                if (length < 0)
                    return -1;
                for (let i = 0; i < length; i++) {
                    const next = take();
                    if (next < 0)
                        return 0;
                    if (next < 128 || next > 191 || i === 0 && (byte === 224 && next < 160 || byte === 237 && next > 159 || byte === 240 && next < 144 || byte === 244 && next > 143))
                        return -1;
                }
            }
            else
                return -1;
        }
    };
    const longString = () => {
        if (take() !== 34)
            return -1;
        for (;;) {
            let byte = peek();
            if (byte < 0)
                return 0;
            // Large native base64 strings usually stay in this direct, allocation-free ASCII loop.
            const chunk = chunks[chunkIndex];
            if (chunk.length - offset >= 16384) {
                const advanced = advanceAscii(chunk, offset);
                if (advanced) {
                    offset += advanced;
                    continue;
                }
            }
            // Skip four unescaped ASCII string bytes at a time without decoding or
            // copying them. Zero-byte detection may stop early through a borrow, but
            // never skips a quote/backslash; the scalar grammar remains authoritative.
            while (offset + 4 <= chunk.length) {
                const word = chunk.readUInt32LE(offset);
                if ((word & 0x80808080) !== 0 || ((word + 0x60606060) & 0x80808080) !== (0x80808080 | 0))
                    break;
                const quote = word ^ 0x22222222, escape = word ^ 0x5c5c5c5c;
                if (((quote - 0x01010101) & ~quote & 0x80808080) !== 0 ||
                    ((escape - 0x01010101) & ~escape & 0x80808080) !== 0)
                    break;
                offset += 4;
            }
            while (offset < chunk.length && chunk[offset] >= 32 && chunk[offset] < 128 && chunk[offset] !== 34 && chunk[offset] !== 92)
                offset++;
            if (offset === chunk.length)
                continue;
            byte = take();
            if (byte < 0)
                return 0;
            if (byte === 34)
                return 1;
            if (byte === 92) {
                const escaped = take();
                if (escaped < 0)
                    return 0;
                if (escaped === 117) {
                    for (let i = 0; i < 4; i++) {
                        const digit = take();
                        if (digit < 0)
                            return 0;
                        if (!hex(digit))
                            return -1;
                    }
                }
                else if (escaped !== 34 && escaped !== 92 && escaped !== 47 && escaped !== 98 && escaped !== 102 && escaped !== 110 && escaped !== 114 && escaped !== 116)
                    return -1;
            }
            else if (byte >= 128) {
                const length = byte >= 194 && byte <= 223 ? 1 : byte >= 224 && byte <= 239 ? 2 : byte >= 240 && byte <= 244 ? 3 : -1;
                if (length < 0)
                    return -1;
                for (let i = 0; i < length; i++) {
                    const next = take();
                    if (next < 0)
                        return 0;
                    if (next < 128 || next > 191 || i === 0 && (byte === 224 && next < 160 || byte === 237 && next > 159 || byte === 240 && next < 144 || byte === 244 && next > 143))
                        return -1;
                }
            }
            else
                return -1;
        }
    };
    const literal = (expected) => {
        for (let i = 0; i < expected.length; i++) {
            const byte = take();
            if (byte < 0)
                return 0;
            if (byte !== expected.charCodeAt(i))
                return -1;
        }
        return 1;
    };
    const digit = (byte) => byte >= 48 && byte <= 57;
    const value = (depth) => {
        if (depth > 32)
            return -1;
        space();
        let byte = peek();
        if (byte < 0)
            return 0;
        if (byte === 34)
            return chunks[chunkIndex].length - offset >= 16384 ? longString() : string();
        if (byte === 123 || byte === 91) {
            const object = byte === 123, end = object ? 125 : 93;
            take();
            space();
            if (peek() === end) {
                take();
                return 1;
            }
            for (;;) {
                if (peek() < 0)
                    return 0;
                if (object) {
                    const status = string();
                    if (status !== 1)
                        return status;
                    space();
                    byte = take();
                    if (byte < 0)
                        return 0;
                    if (byte !== 58)
                        return -1;
                }
                const status = value(depth + 1);
                if (status !== 1)
                    return status;
                space();
                byte = take();
                if (byte < 0)
                    return 0;
                if (byte === end)
                    return 1;
                if (byte !== 44)
                    return -1;
                space();
            }
        }
        if (byte === 116)
            return literal("true");
        if (byte === 102)
            return literal("false");
        if (byte === 110)
            return literal("null");
        if (byte === 45) {
            take();
            byte = peek();
            if (byte < 0)
                return 0;
        }
        if (!digit(byte))
            return -1;
        take();
        if (byte !== 48)
            while (digit(peek()))
                take();
        if (peek() === 46) {
            take();
            if (peek() < 0)
                return 0;
            if (!digit(peek()))
                return -1;
            while (digit(peek()))
                take();
        }
        if (peek() === 101 || peek() === 69) {
            take();
            if (peek() === 43 || peek() === 45)
                take();
            if (peek() < 0)
                return 0;
            if (!digit(peek()))
                return -1;
            while (digit(peek()))
                take();
        }
        return 1;
    };
    space();
    if (take() !== 123)
        return;
    let seen = 0;
    for (;;) {
        space();
        if (take() !== 34)
            return;
        // These constant public header names are the only strings compared or retained.
        let candidates = 15, length = 0;
        for (;;) {
            const byte = take();
            if (byte === 34)
                break;
            if (byte < 0 || byte === 92)
                return;
            if ("apiVersion".charCodeAt(length) !== byte)
                candidates &= ~1;
            if ("kind".charCodeAt(length) !== byte)
                candidates &= ~2;
            if ("metadata".charCodeAt(length) !== byte)
                candidates &= ~4;
            if ("items".charCodeAt(length) !== byte)
                candidates &= ~8;
            if (!candidates)
                return;
            length++;
        }
        const key = length === 10 && candidates & 1 ? 1 : length === 4 && candidates & 2 ? 2 : length === 8 && candidates & 4 ? 4 : length === 5 && candidates & 8 ? 8 : 0;
        if (!key || seen & key)
            return;
        seen |= key;
        space();
        if (take() !== 58)
            return;
        space();
        if (key === 8) {
            if ((seen & 3) !== 3 || take() !== 91)
                return;
            let count = 0;
            for (;;) {
                space();
                const byte = peek();
                if (byte < 0)
                    return count > 0 ? count : undefined;
                if (byte !== 123 || count >= limit)
                    return;
                const status = value(1);
                if (status !== 1)
                    return status === 0 && count > 0 ? count : undefined;
                count++;
                space();
                const next = take();
                if (next < 0)
                    return count;
                if (next !== 44)
                    return;
            }
        }
        const status = key === 1 ? literal('"v1"') : key === 2 ? literal('"SecretList"') : peek() === 123 ? value(1) : -1;
        if (status !== 1)
            return;
        space();
        if (take() !== 44)
            return;
    }
}
globalThis.Reader = Reader;
globalThis.prefix = rejectedSecretListItemCount;
