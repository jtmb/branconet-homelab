import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import path from "node:path";

// Truthful Zod 3.25.76 maintained root/v3 and v4 backport; no version spoof or scanner waiver.
// Preserve early bounds/default 10000 admission. Share a default budget across one parse:
// 1000 issue append operations, 100000 schema entries/collection slots, 128 synchronous frames.
// Abort the complete parse on exhaustion; ordinary branches/callbacks remain within budget.
// Hash-verify EVERY known source/CJS/ESM input before any write, including new helper paths.
const directory = process.argv[2] ?? path.resolve("node_modules/zod");
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const files = [
  {
    "path": "src/bortus-budget.ts",
    "sha256": "dd819453413b495da99b90a0f978d9ba6ac9381938a779b3e10a8ab643f7619c",
    "variants": {
      "93c0f537071e80f2af3f49cc30fc529788acac2a441d1a8360205ca93ddd9ec6": [
        [
          108,
          198,
          "const key = Symbol.for(\"bortus.zod32576.parse-budget.v1\");\nconst carry = Symbol.for(\"bortus.zod32576.inherit-budget.v1\");\n"
        ]
      ]
    },
    "create": "// BORTUS maintained default limits. Internal state belongs to one parse, never a schema or caller context.\nconst key = Symbol.for(\"bortus.zod32576.parse-budget.v1\");\nconst carry = Symbol.for(\"bortus.zod32576.inherit-budget.v1\");\nconst MAX_ISSUES = 1000, MAX_RUNS = 100000, MAX_SLOTS = 100000, MAX_DEPTH = 128;\ninterface Budget {\n  issues: number; runs: number; slots: number; depth: number; reason: string;\n  arrays: WeakSet<object>; payloads: WeakSet<object>;\n}\nfunction fresh(): Budget { return { issues: 0, runs: 0, slots: 0, depth: 0, reason: \"\", arrays: new WeakSet(), payloads: new WeakSet() }; }\nfunction state(ctx: any): Budget { return ctx[key] ??= fresh(); }\nexport function seed(params: any): any { return { [key]: params?.[carry] ?? fresh() }; }\nexport function inherit(ctx: any): any { return { [carry]: state(ctx) }; }\nexport function scope(ctx: any, async: boolean): any { return { ...ctx, async, ...seed(ctx) }; }\nexport function exhausted(ctx: any): boolean { return !!ctx && !!state(ctx).reason; }\nexport function issue(path: (string | number)[] = []): any {\n  return { code: \"custom\", message: \"BORTUS validation budget exceeded\", path, fatal: true, continue: false };\n}\nfunction consume(b: Budget, field: \"issues\" | \"runs\" | \"slots\", amount: number, maximum: number): boolean {\n  if (b.reason) return false;\n  if (amount > maximum - b[field]) { b.reason = field; return false; }\n  b[field] += amount; return true;\n}\nexport function allowIssue(ctx: any): boolean {\n  const b = state(ctx);\n  if (!b.reason && b.issues >= MAX_ISSUES) b.reason = \"issues\";\n  return !b.reason;\n}\nexport function admit(ctx: any, size: number): boolean { return consume(state(ctx), \"slots\", size, MAX_SLOTS); }\nfunction array(ctx: any, values: any[]): any[] {\n  const b = state(ctx);\n  if (b.arrays.has(values)) return values;\n  b.arrays.add(values);\n  if (!consume(b, \"issues\", values.length, MAX_ISSUES)) values = [];\n  Object.defineProperty(values, \"push\", { configurable: true, writable: true, value(...items: any[]) {\n    if (!consume(b, \"issues\", items.length, MAX_ISSUES)) return this.length;\n    return Array.prototype.push.apply(this, items);\n  } });\n  return values;\n}\nexport function prepareV4(value: any, ctx: any): void {\n  const b = state(ctx);\n  if (b.payloads.has(value)) return;\n  b.payloads.add(value);\n  let issues = array(ctx, value.issues);\n  Object.defineProperty(value, \"issues\", { configurable: true, enumerable: true,\n    get() { return issues; }, set(next) { issues = array(ctx, next); } });\n}\nfunction enter(ctx: any): boolean {\n  const b = state(ctx);\n  if (!consume(b, \"runs\", 1, MAX_RUNS)) return false;\n  if (b.depth >= MAX_DEPTH) { b.reason = \"depth\"; return false; }\n  b.depth++; return true;\n}\nexport function finishV4<T extends { value: any; issues: any[] }>(value: T, ctx: any): T {\n  return (exhausted(ctx) ? { value: value.value, issues: [issue()] } : value) as T;\n}\nexport function wrapV4(parse: any, kind: string): any {\n  return function (this: any, value: any, ctx: any) {\n    prepareV4(value, ctx);\n    if (kind === \"tuple\" && Array.isArray(value.value) && !admit(ctx, value.value.length)) return finishV4(value, ctx);\n    if (!enter(ctx)) return finishV4(value, ctx);\n    let result;\n    try { result = parse.call(this, value, ctx); } finally { state(ctx).depth--; }\n    return result instanceof Promise ? result.then(r => finishV4(r, ctx)) : finishV4(result, ctx);\n  };\n}\nfunction finishV3(result: any, ctx: any, path: (string | number)[]): any {\n  if (!exhausted(ctx)) return result;\n  Array.prototype.splice.call(ctx.issues, 0, ctx.issues.length, issue(path));\n  return { status: \"aborted\" };\n}\nexport function wrapV3(parse: any): any {\n  return function (this: any, input: any) {\n    const ctx = input.parent.common;\n    ctx.issues = array(ctx, ctx.issues);\n    if (this._def.typeName === \"ZodTuple\" && Array.isArray(input.data) && !admit(ctx, input.data.length)) return finishV3(null, ctx, input.path);\n    if (!enter(ctx)) return finishV3(null, ctx, input.path);\n    let result;\n    try { result = parse.call(this, input); } finally { state(ctx).depth--; }\n    return result instanceof Promise ? result.then(r => finishV3(r, ctx, input.path)) : finishV3(result, ctx, input.path);\n  };\n}"
  },
  {
    "path": "bortus-budget.js",
    "sha256": "400c65329ff2cd5ff8ef9cf761d08e10daa3d9251c9db0fee3205dd87f7ed60b",
    "variants": {
      "eaaa20fe7f7107a06655998256b91a0829848af4c8605027e8799b574b7130b2": [
        [
          108,
          198,
          "const key = Symbol.for(\"bortus.zod32576.parse-budget.v1\");\nconst carry = Symbol.for(\"bortus.zod32576.inherit-budget.v1\");\n"
        ]
      ]
    },
    "create": "// BORTUS maintained default limits. Internal state belongs to one parse, never a schema or caller context.\nconst key = Symbol.for(\"bortus.zod32576.parse-budget.v1\");\nconst carry = Symbol.for(\"bortus.zod32576.inherit-budget.v1\");\nconst MAX_ISSUES = 1000, MAX_RUNS = 100000, MAX_SLOTS = 100000, MAX_DEPTH = 128;\nfunction fresh() { return { issues: 0, runs: 0, slots: 0, depth: 0, reason: \"\", arrays: new WeakSet(), payloads: new WeakSet() }; }\nfunction state(ctx) { return ctx[key] ??= fresh(); }\nexport function seed(params) { return { [key]: params?.[carry] ?? fresh() }; }\nexport function inherit(ctx) { return { [carry]: state(ctx) }; }\nexport function scope(ctx, async) { return { ...ctx, async, ...seed(ctx) }; }\nexport function exhausted(ctx) { return !!ctx && !!state(ctx).reason; }\nexport function issue(path = []) {\n    return { code: \"custom\", message: \"BORTUS validation budget exceeded\", path, fatal: true, continue: false };\n}\nfunction consume(b, field, amount, maximum) {\n    if (b.reason)\n        return false;\n    if (amount > maximum - b[field]) {\n        b.reason = field;\n        return false;\n    }\n    b[field] += amount;\n    return true;\n}\nexport function allowIssue(ctx) {\n    const b = state(ctx);\n    if (!b.reason && b.issues >= MAX_ISSUES)\n        b.reason = \"issues\";\n    return !b.reason;\n}\nexport function admit(ctx, size) { return consume(state(ctx), \"slots\", size, MAX_SLOTS); }\nfunction array(ctx, values) {\n    const b = state(ctx);\n    if (b.arrays.has(values))\n        return values;\n    b.arrays.add(values);\n    if (!consume(b, \"issues\", values.length, MAX_ISSUES))\n        values = [];\n    Object.defineProperty(values, \"push\", { configurable: true, writable: true, value(...items) {\n            if (!consume(b, \"issues\", items.length, MAX_ISSUES))\n                return this.length;\n            return Array.prototype.push.apply(this, items);\n        } });\n    return values;\n}\nexport function prepareV4(value, ctx) {\n    const b = state(ctx);\n    if (b.payloads.has(value))\n        return;\n    b.payloads.add(value);\n    let issues = array(ctx, value.issues);\n    Object.defineProperty(value, \"issues\", { configurable: true, enumerable: true,\n        get() { return issues; }, set(next) { issues = array(ctx, next); } });\n}\nfunction enter(ctx) {\n    const b = state(ctx);\n    if (!consume(b, \"runs\", 1, MAX_RUNS))\n        return false;\n    if (b.depth >= MAX_DEPTH) {\n        b.reason = \"depth\";\n        return false;\n    }\n    b.depth++;\n    return true;\n}\nexport function finishV4(value, ctx) {\n    return (exhausted(ctx) ? { value: value.value, issues: [issue()] } : value);\n}\nexport function wrapV4(parse, kind) {\n    return function (value, ctx) {\n        prepareV4(value, ctx);\n        if (kind === \"tuple\" && Array.isArray(value.value) && !admit(ctx, value.value.length))\n            return finishV4(value, ctx);\n        if (!enter(ctx))\n            return finishV4(value, ctx);\n        let result;\n        try {\n            result = parse.call(this, value, ctx);\n        }\n        finally {\n            state(ctx).depth--;\n        }\n        return result instanceof Promise ? result.then(r => finishV4(r, ctx)) : finishV4(result, ctx);\n    };\n}\nfunction finishV3(result, ctx, path) {\n    if (!exhausted(ctx))\n        return result;\n    Array.prototype.splice.call(ctx.issues, 0, ctx.issues.length, issue(path));\n    return { status: \"aborted\" };\n}\nexport function wrapV3(parse) {\n    return function (input) {\n        const ctx = input.parent.common;\n        ctx.issues = array(ctx, ctx.issues);\n        if (this._def.typeName === \"ZodTuple\" && Array.isArray(input.data) && !admit(ctx, input.data.length))\n            return finishV3(null, ctx, input.path);\n        if (!enter(ctx))\n            return finishV3(null, ctx, input.path);\n        let result;\n        try {\n            result = parse.call(this, input);\n        }\n        finally {\n            state(ctx).depth--;\n        }\n        return result instanceof Promise ? result.then(r => finishV3(r, ctx, input.path)) : finishV3(result, ctx, input.path);\n    };\n}\n"
  },
  {
    "path": "bortus-budget.cjs",
    "sha256": "18e084f1d48dc41e28f1c95ec6498f434b74ed40b2dccba416a1a570ccf74257",
    "variants": {
      "0d3cb9f92c3662125b5644b7ff8b790d64983c57083094a2a347197bb12c43be": [
        [
          476,
          566,
          "const key = Symbol.for(\"bortus.zod32576.parse-budget.v1\");\nconst carry = Symbol.for(\"bortus.zod32576.inherit-budget.v1\");\n"
        ]
      ]
    },
    "create": "\"use strict\";\nObject.defineProperty(exports, \"__esModule\", { value: true });\nexports.seed = seed;\nexports.inherit = inherit;\nexports.scope = scope;\nexports.exhausted = exhausted;\nexports.issue = issue;\nexports.allowIssue = allowIssue;\nexports.admit = admit;\nexports.prepareV4 = prepareV4;\nexports.finishV4 = finishV4;\nexports.wrapV4 = wrapV4;\nexports.wrapV3 = wrapV3;\n// BORTUS maintained default limits. Internal state belongs to one parse, never a schema or caller context.\nconst key = Symbol.for(\"bortus.zod32576.parse-budget.v1\");\nconst carry = Symbol.for(\"bortus.zod32576.inherit-budget.v1\");\nconst MAX_ISSUES = 1000, MAX_RUNS = 100000, MAX_SLOTS = 100000, MAX_DEPTH = 128;\nfunction fresh() { return { issues: 0, runs: 0, slots: 0, depth: 0, reason: \"\", arrays: new WeakSet(), payloads: new WeakSet() }; }\nfunction state(ctx) { return ctx[key] ??= fresh(); }\nfunction seed(params) { return { [key]: params?.[carry] ?? fresh() }; }\nfunction inherit(ctx) { return { [carry]: state(ctx) }; }\nfunction scope(ctx, async) { return { ...ctx, async, ...seed(ctx) }; }\nfunction exhausted(ctx) { return !!ctx && !!state(ctx).reason; }\nfunction issue(path = []) {\n    return { code: \"custom\", message: \"BORTUS validation budget exceeded\", path, fatal: true, continue: false };\n}\nfunction consume(b, field, amount, maximum) {\n    if (b.reason)\n        return false;\n    if (amount > maximum - b[field]) {\n        b.reason = field;\n        return false;\n    }\n    b[field] += amount;\n    return true;\n}\nfunction allowIssue(ctx) {\n    const b = state(ctx);\n    if (!b.reason && b.issues >= MAX_ISSUES)\n        b.reason = \"issues\";\n    return !b.reason;\n}\nfunction admit(ctx, size) { return consume(state(ctx), \"slots\", size, MAX_SLOTS); }\nfunction array(ctx, values) {\n    const b = state(ctx);\n    if (b.arrays.has(values))\n        return values;\n    b.arrays.add(values);\n    if (!consume(b, \"issues\", values.length, MAX_ISSUES))\n        values = [];\n    Object.defineProperty(values, \"push\", { configurable: true, writable: true, value(...items) {\n            if (!consume(b, \"issues\", items.length, MAX_ISSUES))\n                return this.length;\n            return Array.prototype.push.apply(this, items);\n        } });\n    return values;\n}\nfunction prepareV4(value, ctx) {\n    const b = state(ctx);\n    if (b.payloads.has(value))\n        return;\n    b.payloads.add(value);\n    let issues = array(ctx, value.issues);\n    Object.defineProperty(value, \"issues\", { configurable: true, enumerable: true,\n        get() { return issues; }, set(next) { issues = array(ctx, next); } });\n}\nfunction enter(ctx) {\n    const b = state(ctx);\n    if (!consume(b, \"runs\", 1, MAX_RUNS))\n        return false;\n    if (b.depth >= MAX_DEPTH) {\n        b.reason = \"depth\";\n        return false;\n    }\n    b.depth++;\n    return true;\n}\nfunction finishV4(value, ctx) {\n    return (exhausted(ctx) ? { value: value.value, issues: [issue()] } : value);\n}\nfunction wrapV4(parse, kind) {\n    return function (value, ctx) {\n        prepareV4(value, ctx);\n        if (kind === \"tuple\" && Array.isArray(value.value) && !admit(ctx, value.value.length))\n            return finishV4(value, ctx);\n        if (!enter(ctx))\n            return finishV4(value, ctx);\n        let result;\n        try {\n            result = parse.call(this, value, ctx);\n        }\n        finally {\n            state(ctx).depth--;\n        }\n        return result instanceof Promise ? result.then(r => finishV4(r, ctx)) : finishV4(result, ctx);\n    };\n}\nfunction finishV3(result, ctx, path) {\n    if (!exhausted(ctx))\n        return result;\n    Array.prototype.splice.call(ctx.issues, 0, ctx.issues.length, issue(path));\n    return { status: \"aborted\" };\n}\nfunction wrapV3(parse) {\n    return function (input) {\n        const ctx = input.parent.common;\n        ctx.issues = array(ctx, ctx.issues);\n        if (this._def.typeName === \"ZodTuple\" && Array.isArray(input.data) && !admit(ctx, input.data.length))\n            return finishV3(null, ctx, input.path);\n        if (!enter(ctx))\n            return finishV3(null, ctx, input.path);\n        let result;\n        try {\n            result = parse.call(this, input);\n        }\n        finally {\n            state(ctx).depth--;\n        }\n        return result instanceof Promise ? result.then(r => finishV3(r, ctx, input.path)) : finishV3(result, ctx, input.path);\n    };\n}\n"
  },
  {
    "path": "src/v3/types.ts",
    "sha256": "ab21b87c1b0f5561d8a248df04b0611702228d72cd8c6190a5df690c9a1ba277",
    "variants": {
      "70309a0877c35d036842e291fe7c8a4439d5db49411d233f8a22bf8a59c41419": [
        [
          0,
          0,
          "import * as bortusBudget from \"../bortus-budget.js\";\n"
        ],
        [
          3005,
          3060,
          "        const error = new ZodError(ctx.common.issues.slice());\n"
        ],
        [
          6719,
          6719,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          7714,
          7755,
          "              issues: ctx.common.issues.slice(),\n"
        ],
        [
          8209,
          8248,
          "            issues: ctx.common.issues.slice(),\n"
        ],
        [
          8689,
          8689,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          12363,
          12363,
          "        this._parse = bortusBudget.wrapV3(this._parse);\n"
        ],
        [
          73448,
          73448,
          "        if (tooBig) return INVALID;\n"
        ],
        [
          74180,
          74204,
          "        return INVALID;\n"
        ],
        [
          74219,
          74247,
          "    // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n    if (ctx.data.length > 10000) {\n      addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"array\", inclusive: true, exact: false });\n      return INVALID;\n    }\n    if (!bortusBudget.admit(ctx.common, ctx.data.length)) return INVALID;\n        if (ctx.common.async) {\n"
        ],
        [
          94162,
          94253,
          "      const unionErrors = results.map((result) => new ZodError(result.ctx.common.issues.slice()));\n"
        ],
        [
          95825,
          95897,
          "      const unionErrors = issues.map((issues) => new ZodError(issues.slice()));\n"
        ],
        [
          111473,
          111473,
          "        if (bortusBudget.exhausted(ctx.common)) break;\n"
        ],
        [
          113886,
          113925,
          "    // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n    if (ctx.data.size > 10000) {\n      addIssueToContext(ctx, { code: ZodIssueCode.custom, message: \"Map exceeds the BORTUS 10000-entry validation limit\", fatal: true });\n      return INVALID;\n    }\n    if (!bortusBudget.admit(ctx.common, ctx.data.size)) return INVALID;\n        const keyType = this._def.keyType;\n"
        ],
        [
          117528,
          117552,
          "        return INVALID;\n"
        ],
        [
          117567,
          117610,
          "    // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n    if (ctx.data.size > 10000) {\n      addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"set\", inclusive: true, exact: false });\n      return INVALID;\n    }\n    if (!bortusBudget.admit(ctx.common, ctx.data.size)) return INVALID;\n        const valueType = this._def.valueType;\n"
        ],
        [
          134419,
          134474,
          "    const validated = promisified.then((data: any) => {\n"
        ],
        [
          134600,
          134600,
          "          ...bortusBudget.inherit(ctx.common),\n"
        ],
        [
          134612,
          134628,
          "      });\n    // Observe rejection even if an exhausted enclosing parse discards this deferred value.\n    validated.catch(() => {});\n    return OK(validated);\n"
        ],
        [
          138076,
          138076,
          "        if (bortusBudget.exhausted(ctx.common)) return ctx.common.async ? Promise.resolve(acc) : acc;\n"
        ],
        [
          146426,
          146489,
          "                    return new ZodError(newCtx.common.issues.slice());\n"
        ],
        [
          146787,
          146848,
          "                  return new ZodError(newCtx.common.issues.slice());\n"
        ]
      ],
      "311ca5077ac866abbaa9fee38c98fb931c3e74b347f3d5dd219d16309790be20": [
        [
          0,
          0,
          "import * as bortusBudget from \"../bortus-budget.js\";\n"
        ],
        [
          3005,
          3060,
          "        const error = new ZodError(ctx.common.issues.slice());\n"
        ],
        [
          6719,
          6719,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          7714,
          7755,
          "              issues: ctx.common.issues.slice(),\n"
        ],
        [
          8209,
          8248,
          "            issues: ctx.common.issues.slice(),\n"
        ],
        [
          8689,
          8689,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          12363,
          12363,
          "        this._parse = bortusBudget.wrapV3(this._parse);\n"
        ],
        [
          74524,
          74552,
          "    if (!bortusBudget.admit(ctx.common, ctx.data.length)) return INVALID;\n        if (ctx.common.async) {\n"
        ],
        [
          94467,
          94558,
          "      const unionErrors = results.map((result) => new ZodError(result.ctx.common.issues.slice()));\n"
        ],
        [
          96130,
          96202,
          "      const unionErrors = issues.map((issues) => new ZodError(issues.slice()));\n"
        ],
        [
          111778,
          111778,
          "        if (bortusBudget.exhausted(ctx.common)) break;\n"
        ],
        [
          114472,
          114511,
          "    if (!bortusBudget.admit(ctx.common, ctx.data.size)) return INVALID;\n        const keyType = this._def.keyType;\n"
        ],
        [
          118418,
          118461,
          "    if (!bortusBudget.admit(ctx.common, ctx.data.size)) return INVALID;\n        const valueType = this._def.valueType;\n"
        ],
        [
          135270,
          135325,
          "    const validated = promisified.then((data: any) => {\n"
        ],
        [
          135451,
          135451,
          "          ...bortusBudget.inherit(ctx.common),\n"
        ],
        [
          135463,
          135479,
          "      });\n    // Observe rejection even if an exhausted enclosing parse discards this deferred value.\n    validated.catch(() => {});\n    return OK(validated);\n"
        ],
        [
          138927,
          138927,
          "        if (bortusBudget.exhausted(ctx.common)) return ctx.common.async ? Promise.resolve(acc) : acc;\n"
        ],
        [
          147277,
          147340,
          "                    return new ZodError(newCtx.common.issues.slice());\n"
        ],
        [
          147638,
          147699,
          "                  return new ZodError(newCtx.common.issues.slice());\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v3/types.js",
    "sha256": "b2a27cdf3c8e56b6e1f521d5b1f1b697d50d208764d56ab58cba0502e53c45d7",
    "variants": {
      "9763a2938f0e7f983363ef4bf6530e7583e3f2d54f8a4a6684efad58febc6e8e": [
        [
          0,
          0,
          "import * as bortusBudget from \"../bortus-budget.js\";\n"
        ],
        [
          1340,
          1403,
          "                const error = new ZodError(ctx.common.issues.slice());\n"
        ],
        [
          3920,
          3920,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          5001,
          5052,
          "                        issues: ctx.common.issues.slice(),\n"
        ],
        [
          5581,
          5624,
          "                issues: ctx.common.issues.slice(),\n"
        ],
        [
          5926,
          5926,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          8446,
          8446,
          "        this._parse = bortusBudget.wrapV3(this._parse);\n"
        ],
        [
          64806,
          64806,
          "                if (tooBig) return INVALID;\n"
        ],
        [
          65744,
          65776,
          "                return INVALID;\n"
        ],
        [
          65800,
          65800,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.length > 10000) {\n            addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"array\", inclusive: true, exact: false });\n            return INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.length)) return INVALID;\n"
        ],
        [
          81610,
          81707,
          "            const unionErrors = results.map((result) => new ZodError(result.ctx.common.issues.slice()));\n"
        ],
        [
          83618,
          83696,
          "            const unionErrors = issues.map((issues) => new ZodError(issues.slice()));\n"
        ],
        [
          95083,
          95083,
          "        if (bortusBudget.exhausted(ctx.common)) break;\n"
        ],
        [
          96694,
          96694,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            addIssueToContext(ctx, { code: ZodIssueCode.custom, message: \"Map exceeds the BORTUS 10000-entry validation limit\", fatal: true });\n            return INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.size)) return INVALID;\n"
        ],
        [
          99918,
          99950,
          "                return INVALID;\n"
        ],
        [
          99974,
          99974,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"set\", inclusive: true, exact: false });\n            return INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.size)) return INVALID;\n"
        ],
        [
          111155,
          111202,
          "        const validated = promisified.then((data) => {\n"
        ],
        [
          111344,
          111344,
          "          ...bortusBudget.inherit(ctx.common),\n"
        ],
        [
          111360,
          111373,
          "        });\n    // Observe rejection even if an exhausted enclosing parse discards this deferred value.\n    validated.catch(() => {});\n    return OK(validated);\n"
        ],
        [
          114034,
          114099,
          "                if (bortusBudget.exhausted(ctx.common)) return ctx.common.async ? Promise.resolve(acc) : acc;\n        const result = effect.refinement(acc, checkCtx);\n"
        ],
        [
          119947,
          120022,
          "                                return new ZodError(newCtx.common.issues.slice());\n"
        ],
        [
          120410,
          120481,
          "                            return new ZodError(newCtx.common.issues.slice());\n"
        ]
      ],
      "100470f7b530b15c8aec05fc6c17a1810286654ff83f877d1e638b08d382a07b": [
        [
          0,
          0,
          "import * as bortusBudget from \"../bortus-budget.js\";\n"
        ],
        [
          1340,
          1403,
          "                const error = new ZodError(ctx.common.issues.slice());\n"
        ],
        [
          3920,
          3920,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          5001,
          5052,
          "                        issues: ctx.common.issues.slice(),\n"
        ],
        [
          5581,
          5624,
          "                issues: ctx.common.issues.slice(),\n"
        ],
        [
          5926,
          5926,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          8446,
          8446,
          "        this._parse = bortusBudget.wrapV3(this._parse);\n"
        ],
        [
          66137,
          66137,
          "        if (!bortusBudget.admit(ctx.common, ctx.data.length)) return INVALID;\n"
        ],
        [
          81947,
          82044,
          "            const unionErrors = results.map((result) => new ZodError(result.ctx.common.issues.slice()));\n"
        ],
        [
          83955,
          84033,
          "            const unionErrors = issues.map((issues) => new ZodError(issues.slice()));\n"
        ],
        [
          95420,
          95420,
          "        if (bortusBudget.exhausted(ctx.common)) break;\n"
        ],
        [
          97336,
          97336,
          "        if (!bortusBudget.admit(ctx.common, ctx.data.size)) return INVALID;\n"
        ],
        [
          100905,
          100905,
          "        if (!bortusBudget.admit(ctx.common, ctx.data.size)) return INVALID;\n"
        ],
        [
          112086,
          112133,
          "        const validated = promisified.then((data) => {\n"
        ],
        [
          112275,
          112275,
          "          ...bortusBudget.inherit(ctx.common),\n"
        ],
        [
          112291,
          112304,
          "        });\n    // Observe rejection even if an exhausted enclosing parse discards this deferred value.\n    validated.catch(() => {});\n    return OK(validated);\n"
        ],
        [
          114965,
          115030,
          "                if (bortusBudget.exhausted(ctx.common)) return ctx.common.async ? Promise.resolve(acc) : acc;\n        const result = effect.refinement(acc, checkCtx);\n"
        ],
        [
          120878,
          120953,
          "                                return new ZodError(newCtx.common.issues.slice());\n"
        ],
        [
          121341,
          121412,
          "                            return new ZodError(newCtx.common.issues.slice());\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v3/types.cjs",
    "sha256": "fc313651ad784cfc65bd9a589c06063ad472a9e464fe41547373294313ecc589",
    "variants": {
      "06487cc05ed45c5dd29789bf0aa75734d1ce06592a7f2665ba4ca90a68e8a3e1": [
        [
          14,
          14,
          "const bortusBudget = require(\"../bortus-budget.cjs\");\n"
        ],
        [
          3002,
          3079,
          "                const error = new ZodError_js_1.ZodError(ctx.common.issues.slice());\n"
        ],
        [
          5669,
          5669,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          6800,
          6851,
          "                        issues: ctx.common.issues.slice(),\n"
        ],
        [
          7400,
          7443,
          "                issues: ctx.common.issues.slice(),\n"
        ],
        [
          7745,
          7745,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          10314,
          10314,
          "        this._parse = bortusBudget.wrapV3(this._parse);\n"
        ],
        [
          70095,
          70095,
          "                if (tooBig) return parseUtil_js_1.INVALID;\n"
        ],
        [
          71101,
          71133,
          "                return parseUtil_js_1.INVALID;\n"
        ],
        [
          71157,
          71157,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.length > 10000) {\n            (0, parseUtil_js_1.addIssueToContext)(ctx, { code: ZodError_js_1.ZodIssueCode.too_big, maximum: 10000, type: \"array\", inclusive: true, exact: false });\n            return parseUtil_js_1.INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.length)) return parseUtil_js_1.INVALID;\n"
        ],
        [
          87311,
          87422,
          "            const unionErrors = results.map((result) => new ZodError_js_1.ZodError(result.ctx.common.issues.slice()));\n"
        ],
        [
          89382,
          89474,
          "            const unionErrors = issues.map((issues) => new ZodError_js_1.ZodError(issues.slice()));\n"
        ],
        [
          101671,
          101671,
          "        if (bortusBudget.exhausted(ctx.common)) break;\n"
        ],
        [
          103405,
          103405,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            (0, parseUtil_js_1.addIssueToContext)(ctx, { code: ZodError_js_1.ZodIssueCode.custom, message: \"Map exceeds the BORTUS 10000-entry validation limit\", fatal: true });\n            return parseUtil_js_1.INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.size)) return parseUtil_js_1.INVALID;\n"
        ],
        [
          106814,
          106846,
          "                return parseUtil_js_1.INVALID;\n"
        ],
        [
          106870,
          106870,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            (0, parseUtil_js_1.addIssueToContext)(ctx, { code: ZodError_js_1.ZodIssueCode.too_big, maximum: 10000, type: \"set\", inclusive: true, exact: false });\n            return parseUtil_js_1.INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.size)) return parseUtil_js_1.INVALID;\n"
        ],
        [
          118961,
          119028,
          "        const validated = promisified.then((data) => {\n"
        ],
        [
          119170,
          119170,
          "          ...bortusBudget.inherit(ctx.common),\n"
        ],
        [
          119186,
          119199,
          "        });\n    // Observe rejection even if an exhausted enclosing parse discards this deferred value.\n    validated.catch(() => {});\n    return parseUtil_js_1.OK(validated);\n"
        ],
        [
          122046,
          122111,
          "                if (bortusBudget.exhausted(ctx.common)) return ctx.common.async ? Promise.resolve(acc) : acc;\n        const result = effect.refinement(acc, checkCtx);\n"
        ],
        [
          128263,
          128352,
          "                                return new ZodError_js_1.ZodError(newCtx.common.issues.slice());\n"
        ],
        [
          128740,
          128825,
          "                            return new ZodError_js_1.ZodError(newCtx.common.issues.slice());\n"
        ]
      ],
      "5b3f72231f98fc63d8ff6cc661893fc4aa05736bb574b8d1718db2456a3fc1d5": [
        [
          14,
          14,
          "const bortusBudget = require(\"../bortus-budget.cjs\");\n"
        ],
        [
          3002,
          3079,
          "                const error = new ZodError_js_1.ZodError(ctx.common.issues.slice());\n"
        ],
        [
          5669,
          5669,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          6800,
          6851,
          "                        issues: ctx.common.issues.slice(),\n"
        ],
        [
          7400,
          7443,
          "                issues: ctx.common.issues.slice(),\n"
        ],
        [
          7745,
          7745,
          "        ...bortusBudget.seed(params),\n"
        ],
        [
          10314,
          10314,
          "        this._parse = bortusBudget.wrapV3(this._parse);\n"
        ],
        [
          71573,
          71573,
          "        if (!bortusBudget.admit(ctx.common, ctx.data.length)) return parseUtil_js_1.INVALID;\n"
        ],
        [
          87727,
          87838,
          "            const unionErrors = results.map((result) => new ZodError_js_1.ZodError(result.ctx.common.issues.slice()));\n"
        ],
        [
          89798,
          89890,
          "            const unionErrors = issues.map((issues) => new ZodError_js_1.ZodError(issues.slice()));\n"
        ],
        [
          102087,
          102087,
          "        if (bortusBudget.exhausted(ctx.common)) break;\n"
        ],
        [
          104175,
          104175,
          "        if (!bortusBudget.admit(ctx.common, ctx.data.size)) return parseUtil_js_1.INVALID;\n"
        ],
        [
          107993,
          107993,
          "        if (!bortusBudget.admit(ctx.common, ctx.data.size)) return parseUtil_js_1.INVALID;\n"
        ],
        [
          120084,
          120151,
          "        const validated = promisified.then((data) => {\n"
        ],
        [
          120293,
          120293,
          "          ...bortusBudget.inherit(ctx.common),\n"
        ],
        [
          120309,
          120322,
          "        });\n    // Observe rejection even if an exhausted enclosing parse discards this deferred value.\n    validated.catch(() => {});\n    return parseUtil_js_1.OK(validated);\n"
        ],
        [
          123169,
          123234,
          "                if (bortusBudget.exhausted(ctx.common)) return ctx.common.async ? Promise.resolve(acc) : acc;\n        const result = effect.refinement(acc, checkCtx);\n"
        ],
        [
          129386,
          129475,
          "                                return new ZodError_js_1.ZodError(newCtx.common.issues.slice());\n"
        ],
        [
          129863,
          129948,
          "                            return new ZodError_js_1.ZodError(newCtx.common.issues.slice());\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "src/v3/helpers/parseUtil.ts",
    "sha256": "a4a4a278508d08dea829fe28ab1166f4b3bad8bb459e606ddbd1ce10129b1937",
    "variants": {
      "cb94690c02dce392b98ca364de0d4b24f42db715fbb1759a08bcfb7fa6674645": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          1768,
          1768,
          "    if (!bortusBudget.allowIssue(ctx.common)) return;\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v3/helpers/parseUtil.js",
    "sha256": "e0c7605c4c346c32eedc79e14bc5da1d1a125234e32e83ee8267852d52e36336",
    "variants": {
      "b57484013bb360bac2e334d58fcd5f6cbfa63ffcc7d8ff3dbbb3380ca659b956": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          917,
          917,
          "    if (!bortusBudget.allowIssue(ctx.common)) return;\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v3/helpers/parseUtil.cjs",
    "sha256": "052167ba1ded3591a2cc88df74eb8eaea237a9fcdfdf498229200fcfadafe28f",
    "variants": {
      "40aaa18765f13ae1a933c6f215ecceb6d3afee89eaa23bb080997e08c30a5b00": [
        [
          14,
          14,
          "const bortusBudget = require(\"../../bortus-budget.cjs\");\n"
        ],
        [
          1401,
          1401,
          "    if (!bortusBudget.allowIssue(ctx.common)) return;\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "src/v4/core/core.ts",
    "sha256": "a43c120cb445203376e3541019da4e15d9c3a8b65c1ea64911f22d805d1c92af",
    "variants": {
      "a4ab07ede271305f79ecd230a5005e31dd11366e326c4c598203a4408ec38c0a": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          1542,
          1542,
          "    if (inst._zod.parse) inst._zod.parse = bortusBudget.wrapV4(inst._zod.parse, (def as any).type);\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/core.js",
    "sha256": "2ee7616514225af5531cf0de4933bd57c490c24247099845c0bcc63796a557b9",
    "variants": {
      "c2d3947a2b138becd65fbe6d7e5826dcbbfecb11d7c84311a8de684a06b6c435": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          1106,
          1106,
          "    if (inst._zod.parse) inst._zod.parse = bortusBudget.wrapV4(inst._zod.parse, def.type);\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/core.cjs",
    "sha256": "0cb809492755a0605c474edfd6134db030e1632d2139e79aa96264f793fe5728",
    "variants": {
      "0e4bf3bbd3f0d732dc3063141e6580e1d657fda139fc76f0c40fc84ac6316da3": [
        [
          14,
          14,
          "const bortusBudget = require(\"../../bortus-budget.cjs\");\n"
        ],
        [
          1297,
          1297,
          "    if (inst._zod.parse) inst._zod.parse = bortusBudget.wrapV4(inst._zod.parse, def.type);\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "src/v4/core/schemas.ts",
    "sha256": "75e98918d1b8d7004d437863a34971bcb4e67605dbc7237c889ff94e2692bec6",
    "variants": {
      "5910d2a181b6570189730578df0ff7c90bd7b2cda6ae1064026d236a47fb687d": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          5933,
          5972,
          "      inst._zod.run = (def.type === \"array\" || def.type === \"map\" || def.type === \"set\") ? ((payload, ctx) => {\n        if (bortusCollectionIssue(inst, payload, ctx)) return payload;\n        return inst._zod.parse(payload, ctx);\n      }) : inst._zod.parse;\n"
        ],
        [
          6305,
          6305,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          7436,
          7436,
          "      if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload, ctx)) return payload;\n"
        ],
        [
          44158,
          44158,
          "// BORTUS: cap collection work before traversal; only leading size checks may reject early.\n// A preceding refinement/overwrite remains a barrier. The default cap is always enforced.\nfunction bortusCollectionIssue(inst: $ZodType, payload: ParsePayload, ctx: ParseContextInternal): boolean {\n  bortusBudget.prepareV4(payload, ctx);\n  if (bortusBudget.exhausted(ctx)) return true;\n  const input = payload.value;\n  const kind = inst._zod.def.type;\n  const size = kind === \"array\" ? (Array.isArray(input) ? input.length : -1)\n    : kind === \"map\" ? (input instanceof Map ? input.size : -1)\n    : kind === \"set\" ? (input instanceof Set ? input.size : -1) : -1;\n  if (size < 0) return false;\n  for (const check of inst._zod.def.checks ?? []) {\n    const def = check._zod.def as checks.$ZodCheckDef & { maximum?: number; length?: number; size?: number };\n    if (![\"min_length\", \"max_length\", \"length_equals\", \"min_size\", \"max_size\", \"size_equals\"].includes(def.check)) break;\n    const maximum = def.maximum ?? def.length ?? def.size;\n    if (typeof maximum !== \"number\" || size <= maximum || Number.isNaN(maximum)) continue;\n    if (def.when && !def.when(payload)) continue;\n    const start = payload.issues.length;\n    check._zod.check(payload as ParsePayload<never>);\n    if (payload.issues.length > start) {\n      (payload.issues[start] as { continue?: boolean }).continue = false;\n      return true;\n    }\n  }\n  if (size > 10000) {\n    payload.issues.push({ code: \"too_big\", origin: kind as \"array\" | \"map\" | \"set\", maximum: 10000,\n      inclusive: true, input, inst, continue: false });\n    return true;\n  }\n  return !bortusBudget.admit(ctx, size);\n}\n\n"
        ],
        [
          74317,
          74317,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          75129,
          75129,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          75550,
          75550,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ]
      ],
      "f2cf342102403a2881b6c9fa8dc04a1b40bc313f4dd46260a30042d72e2a368d": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          6045,
          6111,
          "        if (bortusCollectionIssue(inst, payload, ctx)) return payload;\n"
        ],
        [
          6518,
          6518,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          7649,
          7783,
          "      if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload, ctx)) return payload;\n"
        ],
        [
          44688,
          44769,
          "function bortusCollectionIssue(inst: $ZodType, payload: ParsePayload, ctx: ParseContextInternal): boolean {\n  bortusBudget.prepareV4(payload, ctx);\n  if (bortusBudget.exhausted(ctx)) return true;\n"
        ],
        [
          45998,
          46014,
          "  return !bortusBudget.admit(ctx, size);\n"
        ],
        [
          76176,
          76176,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          76988,
          76988,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          77409,
          77409,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/schemas.js",
    "sha256": "5e1ab4e28c1503a305b311de1200100b4d0d7be6c7a96395689d0c669d560c13",
    "variants": {
      "d466582c022b08a3f9eb1a65d5970d8ca25064d73a5a838d76414ae36440a76b": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          1073,
          1118,
          "            inst._zod.run = (def.type === \"array\" || def.type === \"map\" || def.type === \"set\") ? ((payload, ctx) => {\n              if (bortusCollectionIssue(inst, payload, ctx)) return payload;\n              return inst._zod.parse(payload, ctx);\n            }) : inst._zod.parse;\n"
        ],
        [
          1320,
          1320,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          2854,
          2854,
          "            if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload, ctx)) return payload;\n"
        ],
        [
          21288,
          21288,
          "// BORTUS: cap collection work before traversal; only leading size checks may reject early.\n// A preceding refinement/overwrite remains a barrier. The default cap is always enforced.\nfunction bortusCollectionIssue(inst, payload, ctx) {\n  bortusBudget.prepareV4(payload, ctx);\n  if (bortusBudget.exhausted(ctx)) return true;\n  const input = payload.value;\n  const kind = inst._zod.def.type;\n  const size = kind === \"array\" ? (Array.isArray(input) ? input.length : -1)\n    : kind === \"map\" ? (input instanceof Map ? input.size : -1)\n    : kind === \"set\" ? (input instanceof Set ? input.size : -1) : -1;\n  if (size < 0) return false;\n  for (const check of inst._zod.def.checks ?? []) {\n    const def = check._zod.def;\n    if (![\"min_length\", \"max_length\", \"length_equals\", \"min_size\", \"max_size\", \"size_equals\"].includes(def.check)) break;\n    const maximum = def.maximum ?? def.length ?? def.size;\n    if (typeof maximum !== \"number\" || size <= maximum || Number.isNaN(maximum)) continue;\n    if (def.when && !def.when(payload)) continue;\n    const start = payload.issues.length;\n    check._zod.check(payload);\n    if (payload.issues.length > start) {\n      (payload.issues[start]).continue = false;\n      return true;\n    }\n  }\n  if (size > 10000) {\n    payload.issues.push({ code: \"too_big\", origin: kind, maximum: 10000,\n      inclusive: true, input, inst, continue: false });\n    return true;\n  }\n  return !bortusBudget.admit(ctx, size);\n}\n\n"
        ],
        [
          40944,
          40944,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          41931,
          41931,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          42486,
          42486,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ]
      ],
      "f6b44933bdd0c6e0687e5a4157ebb304cdbcdd2ec8bea1c09529641c766ef28c": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          1191,
          1263,
          "              if (bortusCollectionIssue(inst, payload, ctx)) return payload;\n"
        ],
        [
          1551,
          1551,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          3085,
          3225,
          "            if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload, ctx)) return payload;\n"
        ],
        [
          21842,
          21890,
          "function bortusCollectionIssue(inst, payload, ctx) {\n  bortusBudget.prepareV4(payload, ctx);\n  if (bortusBudget.exhausted(ctx)) return true;\n"
        ],
        [
          22965,
          22981,
          "  return !bortusBudget.admit(ctx, size);\n"
        ],
        [
          42640,
          42640,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          43627,
          43627,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          44182,
          44182,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/schemas.cjs",
    "sha256": "d63c0b03f5a6840a8d86d56d7f0ee893c98d3dc74f9c66859ceaf5bfdd7a480f",
    "variants": {
      "f5d17a7db487c943c9d07cc624010ebb6d93683eabd14339846f4912cc88b51f": [
        [
          14,
          14,
          "const bortusBudget = require(\"../../bortus-budget.cjs\");\n"
        ],
        [
          3827,
          3872,
          "            inst._zod.run = (def.type === \"array\" || def.type === \"map\" || def.type === \"set\") ? ((payload, ctx) => {\n              if (bortusCollectionIssue(inst, payload, ctx)) return payload;\n              return inst._zod.parse(payload, ctx);\n            }) : inst._zod.parse;\n"
        ],
        [
          4074,
          4074,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          5608,
          5608,
          "            if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload, ctx)) return payload;\n"
        ],
        [
          23737,
          23737,
          "// BORTUS: cap collection work before traversal; only leading size checks may reject early.\n// A preceding refinement/overwrite remains a barrier. The default cap is always enforced.\nfunction bortusCollectionIssue(inst, payload, ctx) {\n  bortusBudget.prepareV4(payload, ctx);\n  if (bortusBudget.exhausted(ctx)) return true;\n  const input = payload.value;\n  const kind = inst._zod.def.type;\n  const size = kind === \"array\" ? (Array.isArray(input) ? input.length : -1)\n    : kind === \"map\" ? (input instanceof Map ? input.size : -1)\n    : kind === \"set\" ? (input instanceof Set ? input.size : -1) : -1;\n  if (size < 0) return false;\n  for (const check of inst._zod.def.checks ?? []) {\n    const def = check._zod.def;\n    if (![\"min_length\", \"max_length\", \"length_equals\", \"min_size\", \"max_size\", \"size_equals\"].includes(def.check)) break;\n    const maximum = def.maximum ?? def.length ?? def.size;\n    if (typeof maximum !== \"number\" || size <= maximum || Number.isNaN(maximum)) continue;\n    if (def.when && !def.when(payload)) continue;\n    const start = payload.issues.length;\n    check._zod.check(payload);\n    if (payload.issues.length > start) {\n      (payload.issues[start]).continue = false;\n      return true;\n    }\n  }\n  if (size > 10000) {\n    payload.issues.push({ code: \"too_big\", origin: kind, maximum: 10000,\n      inclusive: true, input, inst, continue: false });\n    return true;\n  }\n  return !bortusBudget.admit(ctx, size);\n}\n\n"
        ],
        [
          43347,
          43347,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          44334,
          44334,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          44889,
          44889,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ]
      ],
      "fa143dce9bd9415fbfc54b44be93fd1953d52988cfb6ab46958eb1e27459ba1e": [
        [
          14,
          14,
          "const bortusBudget = require(\"../../bortus-budget.cjs\");\n"
        ],
        [
          3945,
          4017,
          "              if (bortusCollectionIssue(inst, payload, ctx)) return payload;\n"
        ],
        [
          4305,
          4305,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          5839,
          5979,
          "            if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload, ctx)) return payload;\n"
        ],
        [
          24291,
          24339,
          "function bortusCollectionIssue(inst, payload, ctx) {\n  bortusBudget.prepareV4(payload, ctx);\n  if (bortusBudget.exhausted(ctx)) return true;\n"
        ],
        [
          25414,
          25430,
          "  return !bortusBudget.admit(ctx, size);\n"
        ],
        [
          45043,
          45043,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          46030,
          46030,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          46585,
          46585,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "src/v4/core/parse.ts",
    "sha256": "a6587c859133e8ce02c90f97118f32631d277f3b4a10a3b90df3942f74d9fdb8",
    "variants": {
      "18824a99ce3c0be1a16faa8a63e297dfae4fa12152e1d317fc88d6f8c26e8905": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          602,
          773,
          "  const ctx: schemas.ParseContextInternal = bortusBudget.scope(_ctx, false);\n  let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          849,
          849,
          "  result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          1535,
          1642,
          "  const ctx: schemas.ParseContextInternal = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          1758,
          1758,
          "  result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          2392,
          2551,
          "  const ctx: schemas.ParseContextInternal = bortusBudget.scope(_ctx, false);\n  let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          2627,
          2627,
          "\n  result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          3271,
          3378,
          "  const ctx: schemas.ParseContextInternal = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          3494,
          3494,
          "\n  result = bortusBudget.finishV4(result, ctx);\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/parse.js",
    "sha256": "bca00d234b240717aa2cf6eb0ba5e3ea90568235074da029382190cf8ead001c",
    "variants": {
      "6ca78dcc2917d2634d0087372891bbeb8446ca1bdd208cfd52edfd43d40ac171": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          177,
          322,
          "    const ctx = bortusBudget.scope(_ctx, false);\n    let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          406,
          406,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          804,
          883,
          "    const ctx = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          1011,
          1011,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          1402,
          1535,
          "    const ctx = bortusBudget.scope(_ctx, false);\n    let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          1619,
          1619,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          2025,
          2104,
          "    const ctx = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          2232,
          2232,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/parse.cjs",
    "sha256": "6f93b3f1c34d62ec7f29e005992fe9fbb95a50817eef38659261cab56ddbf994",
    "variants": {
      "d1f050385216780e09cad2708bb35d06c5a7508f6313ece7b55c99a537e7676d": [
        [
          14,
          14,
          "const bortusBudget = require(\"../../bortus-budget.cjs\");\n"
        ],
        [
          1495,
          1640,
          "    const ctx = bortusBudget.scope(_ctx, false);\n    let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          1724,
          1724,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          2133,
          2212,
          "    const ctx = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          2340,
          2340,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          2752,
          2885,
          "    const ctx = bortusBudget.scope(_ctx, false);\n    let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          2969,
          2969,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          3394,
          3473,
          "    const ctx = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          3601,
          3601,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ]
      ]
    },
    "create": null
  }
];
try {
  if (JSON.parse(readFileSync(path.join(directory, "package.json"), "utf8")).version !== "3.25.76")
    throw new Error("Unsupported Zod version");
  const verified = files.map(file => {
    const target = path.join(directory, file.path);
    if (!existsSync(target)) {
      if (file.create === null) throw new Error("Missing Zod source");
      if (hash(file.create) !== file.sha256) throw new Error("Unexpected helper source");
      return { target, source: file.create };
    }
    const bytes = readFileSync(target), digest = hash(bytes);
    if (digest === file.sha256) return { target };
    const changes = file.variants[digest];
    if (!changes) throw new Error("Unexpected Zod source");
    const chunks = []; let position = 0;
    for (const [start, end, replacement] of changes) {
      if (start < position || end < start || end > bytes.length) throw new Error("Unexpected patch range");
      chunks.push(bytes.subarray(position, start), Buffer.from(replacement)); position = end;
    }
    chunks.push(bytes.subarray(position));
    const source = Buffer.concat(chunks);
    if (hash(source) !== file.sha256) throw new Error("Unexpected patched Zod source");
    return { target, source };
  });
  for (const item of verified) if (item.source !== undefined) writeFileSync(item.target, item.source);
  console.log("Verified Zod 3.25.76 maintained admission and shared parse budget in source, CJS and ESM");
} catch {
  console.error("Zod collection backport verification failed; installation/build stopped");
  process.exitCode = 1;
}
