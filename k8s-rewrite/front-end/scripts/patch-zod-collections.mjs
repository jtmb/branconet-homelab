import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import path from "node:path";

// Real Zod 4.6.7 registry package, with a fail-closed bounded-parser maintenance patch.
// Application schemas explicitly use the supported v3 export. The root is upstream v4.
// 1000 issue appends, 100000 schema entries/slots, 128 synchronous frames, default10000 collections.
// Source/CJS/ESM share per-parse state. Context-free schema compiler paths use bounded runtime.
// Truthful version/exports/declarations; no suppression or metadata-only closure.
const directory = process.argv[2] ?? path.resolve("node_modules/zod");
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const files = [
  {
    "path": "bortus-budget.cjs",
    "sha256": "18e084f1d48dc41e28f1c95ec6498f434b74ed40b2dccba416a1a570ccf74257",
    "variants": {},
    "create": "\"use strict\";\nObject.defineProperty(exports, \"__esModule\", { value: true });\nexports.seed = seed;\nexports.inherit = inherit;\nexports.scope = scope;\nexports.exhausted = exhausted;\nexports.issue = issue;\nexports.allowIssue = allowIssue;\nexports.admit = admit;\nexports.prepareV4 = prepareV4;\nexports.finishV4 = finishV4;\nexports.wrapV4 = wrapV4;\nexports.wrapV3 = wrapV3;\n// BORTUS maintained default limits. Internal state belongs to one parse, never a schema or caller context.\nconst key = Symbol.for(\"bortus.zod32576.parse-budget.v1\");\nconst carry = Symbol.for(\"bortus.zod32576.inherit-budget.v1\");\nconst MAX_ISSUES = 1000, MAX_RUNS = 100000, MAX_SLOTS = 100000, MAX_DEPTH = 128;\nfunction fresh() { return { issues: 0, runs: 0, slots: 0, depth: 0, reason: \"\", arrays: new WeakSet(), payloads: new WeakSet() }; }\nfunction state(ctx) { return ctx[key] ??= fresh(); }\nfunction seed(params) { return { [key]: params?.[carry] ?? fresh() }; }\nfunction inherit(ctx) { return { [carry]: state(ctx) }; }\nfunction scope(ctx, async) { return { ...ctx, async, ...seed(ctx) }; }\nfunction exhausted(ctx) { return !!ctx && !!state(ctx).reason; }\nfunction issue(path = []) {\n    return { code: \"custom\", message: \"BORTUS validation budget exceeded\", path, fatal: true, continue: false };\n}\nfunction consume(b, field, amount, maximum) {\n    if (b.reason)\n        return false;\n    if (amount > maximum - b[field]) {\n        b.reason = field;\n        return false;\n    }\n    b[field] += amount;\n    return true;\n}\nfunction allowIssue(ctx) {\n    const b = state(ctx);\n    if (!b.reason && b.issues >= MAX_ISSUES)\n        b.reason = \"issues\";\n    return !b.reason;\n}\nfunction admit(ctx, size) { return consume(state(ctx), \"slots\", size, MAX_SLOTS); }\nfunction array(ctx, values) {\n    const b = state(ctx);\n    if (b.arrays.has(values))\n        return values;\n    b.arrays.add(values);\n    if (!consume(b, \"issues\", values.length, MAX_ISSUES))\n        values = [];\n    Object.defineProperty(values, \"push\", { configurable: true, writable: true, value(...items) {\n            if (!consume(b, \"issues\", items.length, MAX_ISSUES))\n                return this.length;\n            return Array.prototype.push.apply(this, items);\n        } });\n    return values;\n}\nfunction prepareV4(value, ctx) {\n    const b = state(ctx);\n    if (b.payloads.has(value))\n        return;\n    b.payloads.add(value);\n    let issues = array(ctx, value.issues);\n    Object.defineProperty(value, \"issues\", { configurable: true, enumerable: true,\n        get() { return issues; }, set(next) { issues = array(ctx, next); } });\n}\nfunction enter(ctx) {\n    const b = state(ctx);\n    if (!consume(b, \"runs\", 1, MAX_RUNS))\n        return false;\n    if (b.depth >= MAX_DEPTH) {\n        b.reason = \"depth\";\n        return false;\n    }\n    b.depth++;\n    return true;\n}\nfunction finishV4(value, ctx) {\n    return (exhausted(ctx) ? { value: value.value, issues: [issue()] } : value);\n}\nfunction wrapV4(parse, kind) {\n    return function (value, ctx) {\n        prepareV4(value, ctx);\n        if (kind === \"tuple\" && Array.isArray(value.value) && !admit(ctx, value.value.length))\n            return finishV4(value, ctx);\n        if (!enter(ctx))\n            return finishV4(value, ctx);\n        let result;\n        try {\n            result = parse.call(this, value, ctx);\n        }\n        finally {\n            state(ctx).depth--;\n        }\n        return result instanceof Promise ? result.then(r => finishV4(r, ctx)) : finishV4(result, ctx);\n    };\n}\nfunction finishV3(result, ctx, path) {\n    if (!exhausted(ctx))\n        return result;\n    Array.prototype.splice.call(ctx.issues, 0, ctx.issues.length, issue(path));\n    return { status: \"aborted\" };\n}\nfunction wrapV3(parse) {\n    return function (input) {\n        const ctx = input.parent.common;\n        ctx.issues = array(ctx, ctx.issues);\n        if (this._def.typeName === \"ZodTuple\" && Array.isArray(input.data) && !admit(ctx, input.data.length))\n            return finishV3(null, ctx, input.path);\n        if (!enter(ctx))\n            return finishV3(null, ctx, input.path);\n        let result;\n        try {\n            result = parse.call(this, input);\n        }\n        finally {\n            state(ctx).depth--;\n        }\n        return result instanceof Promise ? result.then(r => finishV3(r, ctx, input.path)) : finishV3(result, ctx, input.path);\n    };\n}\n"
  },
  {
    "path": "bortus-budget.js",
    "sha256": "400c65329ff2cd5ff8ef9cf761d08e10daa3d9251c9db0fee3205dd87f7ed60b",
    "variants": {},
    "create": "// BORTUS maintained default limits. Internal state belongs to one parse, never a schema or caller context.\nconst key = Symbol.for(\"bortus.zod32576.parse-budget.v1\");\nconst carry = Symbol.for(\"bortus.zod32576.inherit-budget.v1\");\nconst MAX_ISSUES = 1000, MAX_RUNS = 100000, MAX_SLOTS = 100000, MAX_DEPTH = 128;\nfunction fresh() { return { issues: 0, runs: 0, slots: 0, depth: 0, reason: \"\", arrays: new WeakSet(), payloads: new WeakSet() }; }\nfunction state(ctx) { return ctx[key] ??= fresh(); }\nexport function seed(params) { return { [key]: params?.[carry] ?? fresh() }; }\nexport function inherit(ctx) { return { [carry]: state(ctx) }; }\nexport function scope(ctx, async) { return { ...ctx, async, ...seed(ctx) }; }\nexport function exhausted(ctx) { return !!ctx && !!state(ctx).reason; }\nexport function issue(path = []) {\n    return { code: \"custom\", message: \"BORTUS validation budget exceeded\", path, fatal: true, continue: false };\n}\nfunction consume(b, field, amount, maximum) {\n    if (b.reason)\n        return false;\n    if (amount > maximum - b[field]) {\n        b.reason = field;\n        return false;\n    }\n    b[field] += amount;\n    return true;\n}\nexport function allowIssue(ctx) {\n    const b = state(ctx);\n    if (!b.reason && b.issues >= MAX_ISSUES)\n        b.reason = \"issues\";\n    return !b.reason;\n}\nexport function admit(ctx, size) { return consume(state(ctx), \"slots\", size, MAX_SLOTS); }\nfunction array(ctx, values) {\n    const b = state(ctx);\n    if (b.arrays.has(values))\n        return values;\n    b.arrays.add(values);\n    if (!consume(b, \"issues\", values.length, MAX_ISSUES))\n        values = [];\n    Object.defineProperty(values, \"push\", { configurable: true, writable: true, value(...items) {\n            if (!consume(b, \"issues\", items.length, MAX_ISSUES))\n                return this.length;\n            return Array.prototype.push.apply(this, items);\n        } });\n    return values;\n}\nexport function prepareV4(value, ctx) {\n    const b = state(ctx);\n    if (b.payloads.has(value))\n        return;\n    b.payloads.add(value);\n    let issues = array(ctx, value.issues);\n    Object.defineProperty(value, \"issues\", { configurable: true, enumerable: true,\n        get() { return issues; }, set(next) { issues = array(ctx, next); } });\n}\nfunction enter(ctx) {\n    const b = state(ctx);\n    if (!consume(b, \"runs\", 1, MAX_RUNS))\n        return false;\n    if (b.depth >= MAX_DEPTH) {\n        b.reason = \"depth\";\n        return false;\n    }\n    b.depth++;\n    return true;\n}\nexport function finishV4(value, ctx) {\n    return (exhausted(ctx) ? { value: value.value, issues: [issue()] } : value);\n}\nexport function wrapV4(parse, kind) {\n    return function (value, ctx) {\n        prepareV4(value, ctx);\n        if (kind === \"tuple\" && Array.isArray(value.value) && !admit(ctx, value.value.length))\n            return finishV4(value, ctx);\n        if (!enter(ctx))\n            return finishV4(value, ctx);\n        let result;\n        try {\n            result = parse.call(this, value, ctx);\n        }\n        finally {\n            state(ctx).depth--;\n        }\n        return result instanceof Promise ? result.then(r => finishV4(r, ctx)) : finishV4(result, ctx);\n    };\n}\nfunction finishV3(result, ctx, path) {\n    if (!exhausted(ctx))\n        return result;\n    Array.prototype.splice.call(ctx.issues, 0, ctx.issues.length, issue(path));\n    return { status: \"aborted\" };\n}\nexport function wrapV3(parse) {\n    return function (input) {\n        const ctx = input.parent.common;\n        ctx.issues = array(ctx, ctx.issues);\n        if (this._def.typeName === \"ZodTuple\" && Array.isArray(input.data) && !admit(ctx, input.data.length))\n            return finishV3(null, ctx, input.path);\n        if (!enter(ctx))\n            return finishV3(null, ctx, input.path);\n        let result;\n        try {\n            result = parse.call(this, input);\n        }\n        finally {\n            state(ctx).depth--;\n        }\n        return result instanceof Promise ? result.then(r => finishV3(r, ctx, input.path)) : finishV3(result, ctx, input.path);\n    };\n}\n"
  },
  {
    "path": "src/bortus-budget.ts",
    "sha256": "dd819453413b495da99b90a0f978d9ba6ac9381938a779b3e10a8ab643f7619c",
    "variants": {},
    "create": "// BORTUS maintained default limits. Internal state belongs to one parse, never a schema or caller context.\nconst key = Symbol.for(\"bortus.zod32576.parse-budget.v1\");\nconst carry = Symbol.for(\"bortus.zod32576.inherit-budget.v1\");\nconst MAX_ISSUES = 1000, MAX_RUNS = 100000, MAX_SLOTS = 100000, MAX_DEPTH = 128;\ninterface Budget {\n  issues: number; runs: number; slots: number; depth: number; reason: string;\n  arrays: WeakSet<object>; payloads: WeakSet<object>;\n}\nfunction fresh(): Budget { return { issues: 0, runs: 0, slots: 0, depth: 0, reason: \"\", arrays: new WeakSet(), payloads: new WeakSet() }; }\nfunction state(ctx: any): Budget { return ctx[key] ??= fresh(); }\nexport function seed(params: any): any { return { [key]: params?.[carry] ?? fresh() }; }\nexport function inherit(ctx: any): any { return { [carry]: state(ctx) }; }\nexport function scope(ctx: any, async: boolean): any { return { ...ctx, async, ...seed(ctx) }; }\nexport function exhausted(ctx: any): boolean { return !!ctx && !!state(ctx).reason; }\nexport function issue(path: (string | number)[] = []): any {\n  return { code: \"custom\", message: \"BORTUS validation budget exceeded\", path, fatal: true, continue: false };\n}\nfunction consume(b: Budget, field: \"issues\" | \"runs\" | \"slots\", amount: number, maximum: number): boolean {\n  if (b.reason) return false;\n  if (amount > maximum - b[field]) { b.reason = field; return false; }\n  b[field] += amount; return true;\n}\nexport function allowIssue(ctx: any): boolean {\n  const b = state(ctx);\n  if (!b.reason && b.issues >= MAX_ISSUES) b.reason = \"issues\";\n  return !b.reason;\n}\nexport function admit(ctx: any, size: number): boolean { return consume(state(ctx), \"slots\", size, MAX_SLOTS); }\nfunction array(ctx: any, values: any[]): any[] {\n  const b = state(ctx);\n  if (b.arrays.has(values)) return values;\n  b.arrays.add(values);\n  if (!consume(b, \"issues\", values.length, MAX_ISSUES)) values = [];\n  Object.defineProperty(values, \"push\", { configurable: true, writable: true, value(...items: any[]) {\n    if (!consume(b, \"issues\", items.length, MAX_ISSUES)) return this.length;\n    return Array.prototype.push.apply(this, items);\n  } });\n  return values;\n}\nexport function prepareV4(value: any, ctx: any): void {\n  const b = state(ctx);\n  if (b.payloads.has(value)) return;\n  b.payloads.add(value);\n  let issues = array(ctx, value.issues);\n  Object.defineProperty(value, \"issues\", { configurable: true, enumerable: true,\n    get() { return issues; }, set(next) { issues = array(ctx, next); } });\n}\nfunction enter(ctx: any): boolean {\n  const b = state(ctx);\n  if (!consume(b, \"runs\", 1, MAX_RUNS)) return false;\n  if (b.depth >= MAX_DEPTH) { b.reason = \"depth\"; return false; }\n  b.depth++; return true;\n}\nexport function finishV4<T extends { value: any; issues: any[] }>(value: T, ctx: any): T {\n  return (exhausted(ctx) ? { value: value.value, issues: [issue()] } : value) as T;\n}\nexport function wrapV4(parse: any, kind: string): any {\n  return function (this: any, value: any, ctx: any) {\n    prepareV4(value, ctx);\n    if (kind === \"tuple\" && Array.isArray(value.value) && !admit(ctx, value.value.length)) return finishV4(value, ctx);\n    if (!enter(ctx)) return finishV4(value, ctx);\n    let result;\n    try { result = parse.call(this, value, ctx); } finally { state(ctx).depth--; }\n    return result instanceof Promise ? result.then(r => finishV4(r, ctx)) : finishV4(result, ctx);\n  };\n}\nfunction finishV3(result: any, ctx: any, path: (string | number)[]): any {\n  if (!exhausted(ctx)) return result;\n  Array.prototype.splice.call(ctx.issues, 0, ctx.issues.length, issue(path));\n  return { status: \"aborted\" };\n}\nexport function wrapV3(parse: any): any {\n  return function (this: any, input: any) {\n    const ctx = input.parent.common;\n    ctx.issues = array(ctx, ctx.issues);\n    if (this._def.typeName === \"ZodTuple\" && Array.isArray(input.data) && !admit(ctx, input.data.length)) return finishV3(null, ctx, input.path);\n    if (!enter(ctx)) return finishV3(null, ctx, input.path);\n    let result;\n    try { result = parse.call(this, input); } finally { state(ctx).depth--; }\n    return result instanceof Promise ? result.then(r => finishV3(r, ctx, input.path)) : finishV3(result, ctx, input.path);\n  };\n}"
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
    "path": "src/v3/types.ts",
    "sha256": "305c5a1e930395d8c1a4e75859fa5b717c65503a73e15d4c76a797974f20271b",
    "variants": {
      "73b9529564a34fc028a5a62c17e09148747b737039b78b124e84254cb886411a": [
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
          73489,
          73489,
          "        if (tooBig) return INVALID;\n"
        ],
        [
          74221,
          74245,
          "        return INVALID;\n"
        ],
        [
          74260,
          74288,
          "    // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n    if (ctx.data.length > 10000) {\n      addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"array\", inclusive: true, exact: false });\n      return INVALID;\n    }\n    if (!bortusBudget.admit(ctx.common, ctx.data.length)) return INVALID;\n        if (ctx.common.async) {\n"
        ],
        [
          94195,
          94286,
          "      const unionErrors = results.map((result) => new ZodError(result.ctx.common.issues.slice()));\n"
        ],
        [
          95858,
          95930,
          "      const unionErrors = issues.map((issues) => new ZodError(issues.slice()));\n"
        ],
        [
          111639,
          111639,
          "        if (bortusBudget.exhausted(ctx.common)) break;\n"
        ],
        [
          114052,
          114091,
          "    // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n    if (ctx.data.size > 10000) {\n      addIssueToContext(ctx, { code: ZodIssueCode.custom, message: \"Map exceeds the BORTUS 10000-entry validation limit\", fatal: true });\n      return INVALID;\n    }\n    if (!bortusBudget.admit(ctx.common, ctx.data.size)) return INVALID;\n        const keyType = this._def.keyType;\n"
        ],
        [
          117694,
          117718,
          "        return INVALID;\n"
        ],
        [
          117733,
          117776,
          "    // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n    if (ctx.data.size > 10000) {\n      addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"set\", inclusive: true, exact: false });\n      return INVALID;\n    }\n    if (!bortusBudget.admit(ctx.common, ctx.data.size)) return INVALID;\n        const valueType = this._def.valueType;\n"
        ],
        [
          134567,
          134622,
          "    const validated = promisified.then((data: any) => {\n"
        ],
        [
          134748,
          134748,
          "          ...bortusBudget.inherit(ctx.common),\n"
        ],
        [
          134760,
          134776,
          "      });\n    // Observe rejection even if an exhausted enclosing parse discards this deferred value.\n    validated.catch(() => {});\n    return OK(validated);\n"
        ],
        [
          138224,
          138224,
          "        if (bortusBudget.exhausted(ctx.common)) return ctx.common.async ? Promise.resolve(acc) : acc;\n"
        ],
        [
          146574,
          146637,
          "                    return new ZodError(newCtx.common.issues.slice());\n"
        ],
        [
          146935,
          146996,
          "                  return new ZodError(newCtx.common.issues.slice());\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "src/v4/core/compile.ts",
    "sha256": "1c85de2276885cecc65cb4ddb06ff6780626394bf94c5b08aa9f8fba74ec3fdb",
    "variants": {
      "6c2a8810813117e864a95dd1e8512af7ce53e6b4b02d1f0dbc1dfa78850afff0": [
        [
          5281,
          5369,
          "    // BORTUS: context-free validators cannot enforce the shared request budget.\n    delete clone._zod.bag.validator;\n"
        ],
        [
          9139,
          9227,
          "  delete clone._zod.bag.validator;\n  clone._zod.run = originalRun;\n"
        ],
        [
          9522,
          9633,
          "  // BORTUS: retain clone methods that route through the bounded runtime parser.\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "src/v4/core/core.ts",
    "sha256": "e7b78797c62a93228f911da30601dfbf57742ed1c3e3839cc38e978b5724536e",
    "variants": {
      "f3ab5ea2f1e49379b25ee99cecf6dc0a2c02aa77fce87400f010a49f2b670463": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          5174,
          5174,
          "    if (inst._zod.parse) inst._zod.parse = bortusBudget.wrapV4(inst._zod.parse, (def as any).type);\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "src/v4/core/parse.ts",
    "sha256": "402fb1576175b6b3c0f70d80f224ed2b47fb1c97443ac6d5eb9cd005446481a9",
    "variants": {
      "855bda0c95d79be1562fb1f48db4eefb7697276675b7debeb389aaba1b61e9e6": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          934,
          1097,
          "    const ctx: schemas.ParseContextInternal = bortusBudget.scope(_ctx, false);\n    let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          1179,
          1179,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          1894,
          1991,
          "    const ctx: schemas.ParseContextInternal = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          2111,
          2111,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          2781,
          2940,
          "  const ctx: schemas.ParseContextInternal = bortusBudget.scope(_ctx, false);\n  let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          3016,
          3016,
          "\n  result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          4706,
          4801,
          "  const ctx: schemas.ParseContextInternal = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          4917,
          4917,
          "\n  result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          6131,
          6479,
          "  // BORTUS: validators without a context cannot enforce the shared parse budget.\n"
        ],
        [
          6679,
          6820,
          "  const ctx: schemas.ParseContextInternal = { ...bortusBudget.scope(_ctx, false), abortEarly: true };\n"
        ],
        [
          7292,
          7355,
          "  return bortusBudget.finishV4(result as schemas.ParsePayload, ctx).issues.length === 0;\n"
        ],
        [
          7747,
          7886,
          "  const ctx: schemas.ParseContextInternal = { ...bortusBudget.scope(_ctx, true), abortEarly: true };\n"
        ],
        [
          8011,
          8074,
          "  return bortusBudget.finishV4(result as schemas.ParsePayload, ctx).issues.length === 0;\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "src/v4/core/schemas.ts",
    "sha256": "21ebe9c34b2059286b5b82f467214d977470167b6aa7c028476304f90b2e5b70",
    "variants": {
      "9a495df5c8e614f1435f8f79618e768e9f3e5a2bc76d784b2c060f51c8e0312e": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          7923,
          7964,
          "        inst._zod.run = (def.type === \"array\" || def.type === \"map\" || def.type === \"set\") ? ((payload, ctx) => {\n          if (bortusCollectionIssue(inst, payload, ctx)) return payload;\n          return inst._zod.parse(payload, ctx);\n        }) : inst._zod.parse;\n"
        ],
        [
          8360,
          8360,
          "          if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          10925,
          10925,
          "        if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload, ctx)) return payload;\n"
        ],
        [
          58969,
          58969,
          "// BORTUS: cap collection work before traversal; only leading size checks may reject early.\n// A preceding refinement/overwrite remains a barrier. The default cap is always enforced.\nfunction bortusCollectionIssue(inst: $ZodType, payload: ParsePayload, ctx: ParseContextInternal): boolean {\n  bortusBudget.prepareV4(payload, ctx);\n  if (bortusBudget.exhausted(ctx)) return true;\n  const input = payload.value;\n  const kind = inst._zod.def.type;\n  const size = kind === \"array\" ? (Array.isArray(input) ? input.length : -1)\n    : kind === \"map\" ? (input instanceof Map ? input.size : -1)\n    : kind === \"set\" ? (input instanceof Set ? input.size : -1) : -1;\n  if (size < 0) return false;\n  for (const check of inst._zod.def.checks ?? []) {\n    const def = check._zod.def as checks.$ZodCheckDef & { maximum?: number; length?: number; size?: number };\n    if (![\"min_length\", \"max_length\", \"length_equals\", \"min_size\", \"max_size\", \"size_equals\"].includes(def.check)) break;\n    const maximum = def.maximum ?? def.length ?? def.size;\n    if (typeof maximum !== \"number\" || size <= maximum || Number.isNaN(maximum)) continue;\n    if (def.when && !def.when(payload)) continue;\n    const start = payload.issues.length;\n    check._zod.check(payload as ParsePayload<never>);\n    if (payload.issues.length > start) {\n      (payload.issues[start] as { continue?: boolean }).continue = false;\n      return true;\n    }\n  }\n  if (size > 10000) {\n    payload.issues.push({ code: \"too_big\", origin: kind as \"array\" | \"map\" | \"set\", maximum: 10000,\n      inclusive: true, input, inst, continue: false });\n    return true;\n  }\n  return !bortusBudget.admit(ctx, size);\n}\n\n"
        ],
        [
          109012,
          109012,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          110721,
          110721,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ],
        [
          111929,
          111929,
          "        if (bortusBudget.exhausted(ctx)) break;\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v3/helpers/parseUtil.cjs",
    "sha256": "80bd131b65cb71ef8ac02c9f20af0505cfb425f79d5b4a12a7758f3df5cf40bf",
    "variants": {
      "53dfcdf771a06985cc4186aa3dd51552d13be3e90c59aa38414b93875f908e26": [
        [
          14,
          153,
          ""
        ],
        [
          455,
          564,
          "const bortusBudget = require(\"../../bortus-budget.js\");\nconst errors_js_1 = require(\"../errors.js\");\nconst en_js_1 = require(\"../locales/en.js\");\n"
        ],
        [
          1401,
          1401,
          "    if (!bortusBudget.allowIssue(ctx.common))\n        return;\n"
        ],
        [
          2004,
          2060,
          "    value = \"valid\";\n"
        ],
        [
          4272,
          4900,
          ""
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v3/helpers/parseUtil.js",
    "sha256": "b51bb4ff77d1de9af639911b2e18219bbad2e4e125dc4a6b1d3f8148c9ed5305",
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
          "    if (!bortusBudget.allowIssue(ctx.common))\n        return;\n"
        ],
        [
          1497,
          1553,
          "    value = \"valid\";\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v3/types.cjs",
    "sha256": "e31218e01ffb82a4440cce63c881ad398713df78a2e88d5e7d0067cc08981473",
    "variants": {
      "7a2f06d88e280bdd198c60e0d292ed7f1e3993e877be4415de07e6abc7746dd1": [
        [
          1765,
          2026,
          "const bortusBudget = require(\"../bortus-budget.js\");\nconst ZodError_js_1 = require(\"./ZodError.js\");\nconst errors_js_1 = require(\"./errors.js\");\nconst errorUtil_js_1 = require(\"./helpers/errorUtil.js\");\nconst parseUtil_js_1 = require(\"./helpers/parseUtil.js\");\nconst util_js_1 = require(\"./helpers/util.js\");\n"
        ],
        [
          2053,
          2053,
          "    parent;\n    data;\n    _path;\n    _key;\n    _cachedPath = [];\n"
        ],
        [
          2097,
          2128,
          ""
        ],
        [
          3002,
          3079,
          "                const error = new ZodError_js_1.ZodError(ctx.common.issues.slice());\n"
        ],
        [
          4173,
          4173,
          "    _type;\n    _output;\n    _input;\n    _def;\n"
        ],
        [
          4241,
          4241,
          "    \"~standard\";\n"
        ],
        [
          5669,
          5669,
          "                ...bortusBudget.seed(params),\n"
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
          "                ...bortusBudget.seed(params),\n"
        ],
        [
          8338,
          8338,
          "    /** Alias of safeParseAsync */\n    spa = this.safeParseAsync;\n"
        ],
        [
          10210,
          10289,
          ""
        ],
        [
          10314,
          10314,
          "        this._parse = bortusBudget.wrapV3(this._parse);\n"
        ],
        [
          44682,
          44682,
          "    static create = (params) => {\n        return new ZodString({\n            checks: [],\n            typeName: ZodFirstPartyTypeKind.ZodString,\n            coerce: params?.coerce ?? false,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          44715,
          44938,
          ""
        ],
        [
          45565,
          45715,
          ""
        ],
        [
          49416,
          49416,
          "    static create = (params) => {\n        return new ZodNumber({\n            checks: [],\n            typeName: ZodFirstPartyTypeKind.ZodNumber,\n            coerce: params?.coerce || false,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          49542,
          49542,
          "    min = this.gte;\n"
        ],
        [
          49794,
          49794,
          "    max = this.lte;\n"
        ],
        [
          51692,
          51692,
          "    step = this.multipleOf;\n"
        ],
        [
          53609,
          53832,
          ""
        ],
        [
          53866,
          53979,
          ""
        ],
        [
          56809,
          56809,
          "    static create = (params) => {\n        return new ZodBigInt({\n            checks: [],\n            typeName: ZodFirstPartyTypeKind.ZodBigInt,\n            coerce: params?.coerce ?? false,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          56935,
          56935,
          "    min = this.gte;\n"
        ],
        [
          57187,
          57187,
          "    max = this.lte;\n"
        ],
        [
          59514,
          59737,
          ""
        ],
        [
          60391,
          60391,
          "    static create = (params) => {\n        return new ZodBoolean({\n            typeName: ZodFirstPartyTypeKind.ZodBoolean,\n            coerce: params?.coerce || false,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          60426,
          60632,
          ""
        ],
        [
          64199,
          64199,
          "    static create = (params) => {\n        return new ZodDate({\n            checks: [],\n            coerce: params?.coerce || false,\n            typeName: ZodFirstPartyTypeKind.ZodDate,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          64228,
          64445,
          ""
        ],
        [
          65008,
          65008,
          "    static create = (params) => {\n        return new ZodSymbol({\n            typeName: ZodFirstPartyTypeKind.ZodSymbol,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          65041,
          65203,
          ""
        ],
        [
          65775,
          65775,
          "    params;\n    static create = (params) => {\n        return new ZodUndefined({\n            typeName: ZodFirstPartyTypeKind.ZodUndefined,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          65814,
          65985,
          ""
        ],
        [
          66542,
          66542,
          "    static create = (params) => {\n        return new ZodNull({\n            typeName: ZodFirstPartyTypeKind.ZodNull,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          66571,
          66727,
          ""
        ],
        [
          66758,
          66958,
          "    // to prevent instances of other classes from extending ZodAny. this causes issues with catchall in ZodObject.\n    _any = true;\n"
        ],
        [
          67035,
          67035,
          "    static create = (params) => {\n        return new ZodAny({\n            typeName: ZodFirstPartyTypeKind.ZodAny,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          67062,
          67215,
          ""
        ],
        [
          67250,
          67355,
          "    // required\n    _unknown = true;\n"
        ],
        [
          67432,
          67432,
          "    static create = (params) => {\n        return new ZodUnknown({\n            typeName: ZodFirstPartyTypeKind.ZodUnknown,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          67467,
          67632,
          ""
        ],
        [
          67994,
          67994,
          "    static create = (params) => {\n        return new ZodNever({\n            typeName: ZodFirstPartyTypeKind.ZodNever,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          68025,
          68184,
          ""
        ],
        [
          68746,
          68746,
          "    static create = (params) => {\n        return new ZodVoid({\n            typeName: ZodFirstPartyTypeKind.ZodVoid,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          68775,
          68931,
          ""
        ],
        [
          70150,
          70150,
          "                if (tooBig)\n                    return parseUtil_js_1.INVALID;\n"
        ],
        [
          71156,
          71188,
          "                return parseUtil_js_1.INVALID;\n"
        ],
        [
          71212,
          71212,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.length > 10000) {\n            (0, parseUtil_js_1.addIssueToContext)(ctx, { code: ZodError_js_1.ZodIssueCode.too_big, maximum: 10000, type: \"array\", inclusive: true, exact: false });\n            return parseUtil_js_1.INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.length))\n            return parseUtil_js_1.INVALID;\n"
        ],
        [
          72495,
          72495,
          "    static create = (schema, params) => {\n        return new ZodArray({\n            type: schema,\n            minLength: null,\n            maxLength: null,\n            exactLength: null,\n            typeName: ZodFirstPartyTypeKind.ZodArray,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          72526,
          72792,
          ""
        ],
        [
          73802,
          75362,
          "    _cached = null;\n"
        ],
        [
          80342,
          80342,
          "    /**\n     * @deprecated In most cases, this is no longer needed - unknown properties are now silently stripped.\n     * If you want to pass through unknown properties, use `.passthrough()` instead.\n     */\n    nonstrict = this.passthrough;\n"
        ],
        [
          81080,
          81080,
          "    // extend<\n    //   Augmentation extends ZodRawShape,\n    //   NewOutput extends util.flatten<{\n    //     [k in keyof Augmentation | keyof Output]: k extends keyof Augmentation\n    //       ? Augmentation[k][\"_output\"]\n    //       : k extends keyof Output\n    //       ? Output[k]\n    //       : never;\n    //   }>,\n    //   NewInput extends util.flatten<{\n    //     [k in keyof Augmentation | keyof Input]: k extends keyof Augmentation\n    //       ? Augmentation[k][\"_input\"]\n    //       : k extends keyof Input\n    //       ? Input[k]\n    //       : never;\n    //   }>\n    // >(\n    //   augmentation: Augmentation\n    // ): ZodObject<\n    //   extendShape<T, Augmentation>,\n    //   UnknownKeys,\n    //   Catchall,\n    //   NewOutput,\n    //   NewInput\n    // > {\n    //   return new ZodObject({\n    //     ...this._def,\n    //     shape: () => ({\n    //       ...this._def.shape(),\n    //       ...augmentation,\n    //     }),\n    //   }) as any;\n    // }\n    /**\n     * @deprecated Use `.extend` instead\n     *  */\n    augment = this.extend;\n"
        ],
        [
          85782,
          85782,
          "    static create = (shape, params) => {\n        return new ZodObject({\n            shape: () => shape,\n            unknownKeys: \"strip\",\n            catchall: ZodNever.create(),\n            typeName: ZodFirstPartyTypeKind.ZodObject,\n            ...processCreateParams(params),\n        });\n    };\n    static strictCreate = (shape, params) => {\n        return new ZodObject({\n            shape: () => shape,\n            unknownKeys: \"strict\",\n            catchall: ZodNever.create(),\n            typeName: ZodFirstPartyTypeKind.ZodObject,\n            ...processCreateParams(params),\n        });\n    };\n    static lazycreate = (shape, params) => {\n        return new ZodObject({\n            shape,\n            unknownKeys: \"strip\",\n            catchall: ZodNever.create(),\n            typeName: ZodFirstPartyTypeKind.ZodObject,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          85815,
          86605,
          ""
        ],
        [
          87366,
          87477,
          "            const unionErrors = results.map((result) => new ZodError_js_1.ZodError(result.ctx.common.issues.slice()));\n"
        ],
        [
          89437,
          89529,
          "            const unionErrors = issues.map((issues) => new ZodError_js_1.ZodError(issues.slice()));\n"
        ],
        [
          89814,
          89814,
          "    static create = (types, params) => {\n        return new ZodUnion({\n            options: types,\n            typeName: ZodFirstPartyTypeKind.ZodUnion,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          89845,
          90035,
          ""
        ],
        [
          98355,
          98355,
          "    static create = (left, right, params) => {\n        return new ZodIntersection({\n            left: left,\n            right: right,\n            typeName: ZodFirstPartyTypeKind.ZodIntersection,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          98400,
          98635,
          ""
        ],
        [
          100776,
          100776,
          "    static create = (schemas, params) => {\n        if (!Array.isArray(schemas)) {\n            throw new Error(\"You must pass an array of schemas to z.tuple([ ... ])\");\n        }\n        return new ZodTuple({\n            items: schemas,\n            typeName: ZodFirstPartyTypeKind.ZodTuple,\n            rest: null,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          100807,
          101142,
          ""
        ],
        [
          101897,
          101897,
          "            if (bortusBudget.exhausted(ctx.common))\n                break;\n"
        ],
        [
          103631,
          103631,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            (0, parseUtil_js_1.addIssueToContext)(ctx, { code: ZodError_js_1.ZodIssueCode.custom, message: \"Map exceeds the BORTUS 10000-entry validation limit\", fatal: true });\n            return parseUtil_js_1.INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.size))\n            return parseUtil_js_1.INVALID;\n"
        ],
        [
          105383,
          105383,
          "    static create = (keyType, valueType, params) => {\n        return new ZodMap({\n            valueType,\n            keyType,\n            typeName: ZodFirstPartyTypeKind.ZodMap,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          105410,
          105619,
          ""
        ],
        [
          107040,
          107072,
          "                return parseUtil_js_1.INVALID;\n"
        ],
        [
          107096,
          107096,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            (0, parseUtil_js_1.addIssueToContext)(ctx, { code: ZodError_js_1.ZodIssueCode.too_big, maximum: 10000, type: \"set\", inclusive: true, exact: false });\n            return parseUtil_js_1.INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.size))\n            return parseUtil_js_1.INVALID;\n"
        ],
        [
          108466,
          108466,
          "    static create = (valueType, params) => {\n        return new ZodSet({\n            valueType,\n            minSize: null,\n            maxSize: null,\n            typeName: ZodFirstPartyTypeKind.ZodSet,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          108493,
          108722,
          ""
        ],
        [
          108758,
          108853,
          ""
        ],
        [
          113016,
          113016,
          "    validate = this.implement;\n"
        ],
        [
          113687,
          113687,
          "    static create = (getter, params) => {\n        return new ZodLazy({\n            getter: getter,\n            typeName: ZodFirstPartyTypeKind.ZodLazy,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          113716,
          113904,
          ""
        ],
        [
          114446,
          114446,
          "    static create = (value, params) => {\n        return new ZodLiteral({\n            value: value,\n            typeName: ZodFirstPartyTypeKind.ZodLiteral,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          114481,
          114675,
          ""
        ],
        [
          114888,
          114888,
          "    _cache;\n"
        ],
        [
          116850,
          116850,
          "    static create = createZodEnum;\n"
        ],
        [
          116879,
          116911,
          ""
        ],
        [
          116949,
          116949,
          "    _cache;\n"
        ],
        [
          118241,
          118241,
          "    static create = (values, params) => {\n        return new ZodNativeEnum({\n            values: values,\n            typeName: ZodFirstPartyTypeKind.ZodNativeEnum,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          118282,
          118488,
          ""
        ],
        [
          119157,
          119224,
          "        const validated = promisified.then((data) => {\n"
        ],
        [
          119366,
          119366,
          "                ...bortusBudget.inherit(ctx.common),\n"
        ],
        [
          119382,
          119395,
          "        });\n        // Observe rejection even if an exhausted enclosing parse discards this deferred value.\n        validated.catch(() => { });\n        return (0, parseUtil_js_1.OK)(validated);\n"
        ],
        [
          119401,
          119401,
          "    static create = (schema, params) => {\n        return new ZodPromise({\n            type: schema,\n            typeName: ZodFirstPartyTypeKind.ZodPromise,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          119436,
          119631,
          ""
        ],
        [
          122242,
          122242,
          "                if (bortusBudget.exhausted(ctx.common))\n                    return ctx.common.async ? Promise.resolve(acc) : acc;\n"
        ],
        [
          125085,
          125085,
          "    static create = (schema, effect, params) => {\n        return new ZodEffects({\n            schema,\n            typeName: ZodFirstPartyTypeKind.ZodEffects,\n            effect,\n            ...processCreateParams(params),\n        });\n    };\n    static createWithPreprocess = (preprocess, schema, params) => {\n        return new ZodEffects({\n            schema,\n            effect: { type: \"preprocess\", transform: preprocess },\n            typeName: ZodFirstPartyTypeKind.ZodEffects,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          125157,
          125648,
          ""
        ],
        [
          125994,
          125994,
          "    static create = (type, params) => {\n        return new ZodOptional({\n            innerType: type,\n            typeName: ZodFirstPartyTypeKind.ZodOptional,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          126031,
          126230,
          ""
        ],
        [
          126566,
          126566,
          "    static create = (type, params) => {\n        return new ZodNullable({\n            innerType: type,\n            typeName: ZodFirstPartyTypeKind.ZodNullable,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          126603,
          126802,
          ""
        ],
        [
          127263,
          127263,
          "    static create = (type, params) => {\n        return new ZodDefault({\n            innerType: type,\n            typeName: ZodFirstPartyTypeKind.ZodDefault,\n            defaultValue: typeof params.default === \"function\" ? params.default : () => params.default,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          127298,
          127594,
          ""
        ],
        [
          128459,
          128548,
          "                                return new ZodError_js_1.ZodError(newCtx.common.issues.slice());\n"
        ],
        [
          128936,
          129021,
          "                            return new ZodError_js_1.ZodError(newCtx.common.issues.slice());\n"
        ],
        [
          129209,
          129209,
          "    static create = (type, params) => {\n        return new ZodCatch({\n            innerType: type,\n            typeName: ZodFirstPartyTypeKind.ZodCatch,\n            catchValue: typeof params.catch === \"function\" ? params.catch : () => params.catch,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          129240,
          129522,
          ""
        ],
        [
          130080,
          130080,
          "    static create = (params) => {\n        return new ZodNaN({\n            typeName: ZodFirstPartyTypeKind.ZodNaN,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          130107,
          130260,
          ""
        ],
        [
          132975,
          132975,
          "    static create = (type, params) => {\n        return new ZodReadonly({\n            innerType: type,\n            typeName: ZodFirstPartyTypeKind.ZodReadonly,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          133069,
          133268,
          ""
        ],
        [
          140296,
          140924,
          ""
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v3/types.js",
    "sha256": "1aac9f9841a44db40a75171dcc51937726c8946746773868d6ab76a9eaf1a189",
    "variants": {
      "d7214e1dacf9e6e70c9ca80247717b4be13b240510428fef132b7da3260d1a32": [
        [
          0,
          0,
          "import * as bortusBudget from \"../bortus-budget.js\";\n"
        ],
        [
          411,
          411,
          "    parent;\n    data;\n    _path;\n    _key;\n    _cachedPath = [];\n"
        ],
        [
          455,
          486,
          ""
        ],
        [
          1340,
          1403,
          "                const error = new ZodError(ctx.common.issues.slice());\n"
        ],
        [
          2504,
          2504,
          "    _type;\n    _output;\n    _input;\n    _def;\n"
        ],
        [
          2572,
          2572,
          "    \"~standard\";\n"
        ],
        [
          3920,
          3920,
          "                ...bortusBudget.seed(params),\n"
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
          "                ...bortusBudget.seed(params),\n"
        ],
        [
          6484,
          6484,
          "    /** Alias of safeParseAsync */\n    spa = this.safeParseAsync;\n"
        ],
        [
          8342,
          8421,
          ""
        ],
        [
          8446,
          8446,
          "        this._parse = bortusBudget.wrapV3(this._parse);\n"
        ],
        [
          41413,
          41413,
          "    static create = (params) => {\n        return new ZodString({\n            checks: [],\n            typeName: ZodFirstPartyTypeKind.ZodString,\n            coerce: params?.coerce ?? false,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          41415,
          41638,
          ""
        ],
        [
          42272,
          42422,
          ""
        ],
        [
          45849,
          45849,
          "    static create = (params) => {\n        return new ZodNumber({\n            checks: [],\n            typeName: ZodFirstPartyTypeKind.ZodNumber,\n            coerce: params?.coerce || false,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          45960,
          45960,
          "    min = this.gte;\n"
        ],
        [
          46182,
          46182,
          "    max = this.lte;\n"
        ],
        [
          47960,
          47960,
          "    step = this.multipleOf;\n"
        ],
        [
          49791,
          50014,
          ""
        ],
        [
          50055,
          50168,
          ""
        ],
        [
          52802,
          52802,
          "    static create = (params) => {\n        return new ZodBigInt({\n            checks: [],\n            typeName: ZodFirstPartyTypeKind.ZodBigInt,\n            coerce: params?.coerce ?? false,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          52913,
          52913,
          "    min = this.gte;\n"
        ],
        [
          53135,
          53135,
          "    max = this.lte;\n"
        ],
        [
          55326,
          55549,
          ""
        ],
        [
          56121,
          56121,
          "    static create = (params) => {\n        return new ZodBoolean({\n            typeName: ZodFirstPartyTypeKind.ZodBoolean,\n            coerce: params?.coerce || false,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          56123,
          56329,
          ""
        ],
        [
          59662,
          59662,
          "    static create = (params) => {\n        return new ZodDate({\n            checks: [],\n            coerce: params?.coerce || false,\n            typeName: ZodFirstPartyTypeKind.ZodDate,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          59664,
          59881,
          ""
        ],
        [
          60362,
          60362,
          "    static create = (params) => {\n        return new ZodSymbol({\n            typeName: ZodFirstPartyTypeKind.ZodSymbol,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          60364,
          60526,
          ""
        ],
        [
          61016,
          61016,
          "    params;\n    static create = (params) => {\n        return new ZodUndefined({\n            typeName: ZodFirstPartyTypeKind.ZodUndefined,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          61018,
          61189,
          ""
        ],
        [
          61664,
          61664,
          "    static create = (params) => {\n        return new ZodNull({\n            typeName: ZodFirstPartyTypeKind.ZodNull,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          61666,
          61822,
          ""
        ],
        [
          61860,
          62060,
          "    // to prevent instances of other classes from extending ZodAny. this causes issues with catchall in ZodObject.\n    _any = true;\n"
        ],
        [
          62117,
          62117,
          "    static create = (params) => {\n        return new ZodAny({\n            typeName: ZodFirstPartyTypeKind.ZodAny,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          62119,
          62272,
          ""
        ],
        [
          62314,
          62419,
          "    // required\n    _unknown = true;\n"
        ],
        [
          62476,
          62476,
          "    static create = (params) => {\n        return new ZodUnknown({\n            typeName: ZodFirstPartyTypeKind.ZodUnknown,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          62478,
          62643,
          ""
        ],
        [
          62953,
          62953,
          "    static create = (params) => {\n        return new ZodNever({\n            typeName: ZodFirstPartyTypeKind.ZodNever,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          62955,
          63114,
          ""
        ],
        [
          63594,
          63594,
          "    static create = (params) => {\n        return new ZodVoid({\n            typeName: ZodFirstPartyTypeKind.ZodVoid,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          63596,
          63752,
          ""
        ],
        [
          64861,
          64861,
          "                if (tooBig)\n                    return INVALID;\n"
        ],
        [
          65799,
          65831,
          "                return INVALID;\n"
        ],
        [
          65855,
          65855,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.length > 10000) {\n            addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"array\", inclusive: true, exact: false });\n            return INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.length))\n            return INVALID;\n"
        ],
        [
          67063,
          67063,
          "    static create = (schema, params) => {\n        return new ZodArray({\n            type: schema,\n            minLength: null,\n            maxLength: null,\n            exactLength: null,\n            typeName: ZodFirstPartyTypeKind.ZodArray,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          67065,
          67331,
          ""
        ],
        [
          68348,
          69908,
          "    _cached = null;\n"
        ],
        [
          74715,
          74715,
          "    /**\n     * @deprecated In most cases, this is no longer needed - unknown properties are now silently stripped.\n     * If you want to pass through unknown properties, use `.passthrough()` instead.\n     */\n    nonstrict = this.passthrough;\n"
        ],
        [
          75453,
          75453,
          "    // extend<\n    //   Augmentation extends ZodRawShape,\n    //   NewOutput extends util.flatten<{\n    //     [k in keyof Augmentation | keyof Output]: k extends keyof Augmentation\n    //       ? Augmentation[k][\"_output\"]\n    //       : k extends keyof Output\n    //       ? Output[k]\n    //       : never;\n    //   }>,\n    //   NewInput extends util.flatten<{\n    //     [k in keyof Augmentation | keyof Input]: k extends keyof Augmentation\n    //       ? Augmentation[k][\"_input\"]\n    //       : k extends keyof Input\n    //       ? Input[k]\n    //       : never;\n    //   }>\n    // >(\n    //   augmentation: Augmentation\n    // ): ZodObject<\n    //   extendShape<T, Augmentation>,\n    //   UnknownKeys,\n    //   Catchall,\n    //   NewOutput,\n    //   NewInput\n    // > {\n    //   return new ZodObject({\n    //     ...this._def,\n    //     shape: () => ({\n    //       ...this._def.shape(),\n    //       ...augmentation,\n    //     }),\n    //   }) as any;\n    // }\n    /**\n     * @deprecated Use `.extend` instead\n     *  */\n    augment = this.extend;\n"
        ],
        [
          80105,
          80105,
          "    static create = (shape, params) => {\n        return new ZodObject({\n            shape: () => shape,\n            unknownKeys: \"strip\",\n            catchall: ZodNever.create(),\n            typeName: ZodFirstPartyTypeKind.ZodObject,\n            ...processCreateParams(params),\n        });\n    };\n    static strictCreate = (shape, params) => {\n        return new ZodObject({\n            shape: () => shape,\n            unknownKeys: \"strict\",\n            catchall: ZodNever.create(),\n            typeName: ZodFirstPartyTypeKind.ZodObject,\n            ...processCreateParams(params),\n        });\n    };\n    static lazycreate = (shape, params) => {\n        return new ZodObject({\n            shape,\n            unknownKeys: \"strip\",\n            catchall: ZodNever.create(),\n            typeName: ZodFirstPartyTypeKind.ZodObject,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          80107,
          80897,
          ""
        ],
        [
          81665,
          81762,
          "            const unionErrors = results.map((result) => new ZodError(result.ctx.common.issues.slice()));\n"
        ],
        [
          83673,
          83751,
          "            const unionErrors = issues.map((issues) => new ZodError(issues.slice()));\n"
        ],
        [
          83987,
          83987,
          "    static create = (types, params) => {\n        return new ZodUnion({\n            options: types,\n            typeName: ZodFirstPartyTypeKind.ZodUnion,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          83989,
          84179,
          ""
        ],
        [
          92076,
          92076,
          "    static create = (left, right, params) => {\n        return new ZodIntersection({\n            left: left,\n            right: right,\n            typeName: ZodFirstPartyTypeKind.ZodIntersection,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          92078,
          92313,
          ""
        ],
        [
          94279,
          94279,
          "    static create = (schemas, params) => {\n        if (!Array.isArray(schemas)) {\n            throw new Error(\"You must pass an array of schemas to z.tuple([ ... ])\");\n        }\n        return new ZodTuple({\n            items: schemas,\n            typeName: ZodFirstPartyTypeKind.ZodTuple,\n            rest: null,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          94281,
          94616,
          ""
        ],
        [
          95309,
          95309,
          "            if (bortusBudget.exhausted(ctx.common))\n                break;\n"
        ],
        [
          96920,
          96920,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            addIssueToContext(ctx, { code: ZodIssueCode.custom, message: \"Map exceeds the BORTUS 10000-entry validation limit\", fatal: true });\n            return INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.size))\n            return INVALID;\n"
        ],
        [
          98642,
          98642,
          "    static create = (keyType, valueType, params) => {\n        return new ZodMap({\n            valueType,\n            keyType,\n            typeName: ZodFirstPartyTypeKind.ZodMap,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          98644,
          98853,
          ""
        ],
        [
          100144,
          100176,
          "                return INVALID;\n"
        ],
        [
          100200,
          100200,
          "        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"set\", inclusive: true, exact: false });\n            return INVALID;\n        }\n        if (!bortusBudget.admit(ctx.common, ctx.data.size))\n            return INVALID;\n"
        ],
        [
          101525,
          101525,
          "    static create = (valueType, params) => {\n        return new ZodSet({\n            valueType,\n            minSize: null,\n            maxSize: null,\n            typeName: ZodFirstPartyTypeKind.ZodSet,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          101527,
          101756,
          ""
        ],
        [
          101799,
          101894,
          ""
        ],
        [
          105780,
          105780,
          "    validate = this.implement;\n"
        ],
        [
          106423,
          106423,
          "    static create = (getter, params) => {\n        return new ZodLazy({\n            getter: getter,\n            typeName: ZodFirstPartyTypeKind.ZodLazy,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          106425,
          106613,
          ""
        ],
        [
          107113,
          107113,
          "    static create = (value, params) => {\n        return new ZodLiteral({\n            value: value,\n            typeName: ZodFirstPartyTypeKind.ZodLiteral,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          107115,
          107309,
          ""
        ],
        [
          107529,
          107529,
          "    _cache;\n"
        ],
        [
          109363,
          109363,
          "    static create = createZodEnum;\n"
        ],
        [
          109365,
          109397,
          ""
        ],
        [
          109442,
          109442,
          "    _cache;\n"
        ],
        [
          110546,
          110546,
          "    static create = (values, params) => {\n        return new ZodNativeEnum({\n            values: values,\n            typeName: ZodFirstPartyTypeKind.ZodNativeEnum,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          110548,
          110754,
          ""
        ],
        [
          111351,
          111398,
          "        const validated = promisified.then((data) => {\n"
        ],
        [
          111540,
          111540,
          "                ...bortusBudget.inherit(ctx.common),\n"
        ],
        [
          111556,
          111569,
          "        });\n        // Observe rejection even if an exhausted enclosing parse discards this deferred value.\n        validated.catch(() => { });\n        return OK(validated);\n"
        ],
        [
          111575,
          111575,
          "    static create = (schema, params) => {\n        return new ZodPromise({\n            type: schema,\n            typeName: ZodFirstPartyTypeKind.ZodPromise,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          111577,
          111772,
          ""
        ],
        [
          114230,
          114230,
          "                if (bortusBudget.exhausted(ctx.common))\n                    return ctx.common.async ? Promise.resolve(acc) : acc;\n"
        ],
        [
          116963,
          116963,
          "    static create = (schema, effect, params) => {\n        return new ZodEffects({\n            schema,\n            typeName: ZodFirstPartyTypeKind.ZodEffects,\n            effect,\n            ...processCreateParams(params),\n        });\n    };\n    static createWithPreprocess = (preprocess, schema, params) => {\n        return new ZodEffects({\n            schema,\n            effect: { type: \"preprocess\", transform: preprocess },\n            typeName: ZodFirstPartyTypeKind.ZodEffects,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          116965,
          117456,
          ""
        ],
        [
          117820,
          117820,
          "    static create = (type, params) => {\n        return new ZodOptional({\n            innerType: type,\n            typeName: ZodFirstPartyTypeKind.ZodOptional,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          117822,
          118021,
          ""
        ],
        [
          118334,
          118334,
          "    static create = (type, params) => {\n        return new ZodNullable({\n            innerType: type,\n            typeName: ZodFirstPartyTypeKind.ZodNullable,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          118336,
          118535,
          ""
        ],
        [
          118993,
          118993,
          "    static create = (type, params) => {\n        return new ZodDefault({\n            innerType: type,\n            typeName: ZodFirstPartyTypeKind.ZodDefault,\n            defaultValue: typeof params.default === \"function\" ? params.default : () => params.default,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          118995,
          119291,
          ""
        ],
        [
          120143,
          120218,
          "                                return new ZodError(newCtx.common.issues.slice());\n"
        ],
        [
          120606,
          120677,
          "                            return new ZodError(newCtx.common.issues.slice());\n"
        ],
        [
          120865,
          120865,
          "    static create = (type, params) => {\n        return new ZodCatch({\n            innerType: type,\n            typeName: ZodFirstPartyTypeKind.ZodCatch,\n            catchValue: typeof params.catch === \"function\" ? params.catch : () => params.catch,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          120867,
          121149,
          ""
        ],
        [
          121645,
          121645,
          "    static create = (params) => {\n        return new ZodNaN({\n            typeName: ZodFirstPartyTypeKind.ZodNaN,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          121647,
          121800,
          ""
        ],
        [
          124383,
          124383,
          "    static create = (type, params) => {\n        return new ZodReadonly({\n            innerType: type,\n            typeName: ZodFirstPartyTypeKind.ZodReadonly,\n            ...processCreateParams(params),\n        });\n    };\n"
        ],
        [
          124442,
          124641,
          ""
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/compile.cjs",
    "sha256": "37030c33fc6c0a02a3e3badf233b62544c606a815b8054373cb9589cccaf4a8f",
    "variants": {
      "53920c324ac3709a099d2b608398699a6160211738c9ced6473065d9509b7b61": [
        [
          14,
          1041,
          ""
        ],
        [
          1289,
          1571,
          "const core_js_1 = require(\"./core.js\");\nconst doc_js_1 = require(\"./doc.js\");\nconst memoizer_js_1 = require(\"./memoizer.js\");\nconst regexes = require(\"./regexes.js\");\nconst schemas_js_1 = require(\"./schemas.js\");\nconst util = require(\"./util.js\");\n"
        ],
        [
          2641,
          2641,
          "    /** Whether a container may absorb this refusal by running the child through the runtime (see `compileChild`). False when running only that node on the runtime is not equivalent to running the whole parse there \u2014 a runtime island gets no parse context, so a node that *consumes* issues rather than propagating them would finalize them against the wrong error map and still succeed. */\n    islandable;\n"
        ],
        [
          4234,
          4303,
          "        // BORTUS: context-free validators cannot enforce the shared request budget.\n        delete clone._zod.bag.validator;\n"
        ],
        [
          7881,
          7950,
          "    delete clone._zod.bag.validator;\n    clone._zod.run = originalRun;\n"
        ],
        [
          8246,
          8337,
          "    // BORTUS: retain clone methods that route through the bounded runtime parser.\n"
        ],
        [
          93552,
          94180,
          ""
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/compile.js",
    "sha256": "5ca8a79f5d0f36dbbfbc78d7ac5785d7a8d146c123ee56d6c7795c75592ccd3c",
    "variants": {
      "53fcf24821f50ecf42492ab7101abe8a50ead8286a53567d71648fe5ca346b99": [
        [
          1464,
          1464,
          "    /** Whether a container may absorb this refusal by running the child through the runtime (see `compileChild`). False when running only that node on the runtime is not equivalent to running the whole parse there \u2014 a runtime island gets no parse context, so a node that *consumes* issues rather than propagating them would finalize them against the wrong error map and still succeed. */\n    islandable;\n"
        ],
        [
          2999,
          3068,
          "        // BORTUS: context-free validators cannot enforce the shared request budget.\n        delete clone._zod.bag.validator;\n"
        ],
        [
          6607,
          6676,
          "    delete clone._zod.bag.validator;\n    clone._zod.run = originalRun;\n"
        ],
        [
          6972,
          7063,
          "    // BORTUS: retain clone methods that route through the bounded runtime parser.\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/core.cjs",
    "sha256": "6c262d58838d117fcdc4cd0c006cde6c168ad8821aa9605e2507903e41e94440",
    "variants": {
      "0aec383c3aa438289a963c30bcccde1277e7f9657fef9215f74330d2794f0dea": [
        [
          14,
          22,
          ""
        ],
        [
          262,
          303,
          "const bortusBudget = require(\"../../bortus-budget.js\");\nconst util_js_1 = require(\"./util.js\");\n"
        ],
        [
          4956,
          4956,
          "        if (inst._zod.parse)\n            inst._zod.parse = bortusBudget.wrapV4(inst._zod.parse, def.type);\n"
        ],
        [
          6631,
          6701,
          "globalThis.__zod_globalConfig ??= {};\n"
        ],
        [
          6894,
          7522,
          ""
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/core.js",
    "sha256": "b724937efb2e4067fad9149965a65a50669b15f4ae2c651ba9b6ec746d99ed39",
    "variants": {
      "c7ce485c97263e42568d16b11bb4a90133221c7e807498a9273d70f41ba16ef6": [
        [
          0,
          8,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          4759,
          4759,
          "        if (inst._zod.parse)\n            inst._zod.parse = bortusBudget.wrapV4(inst._zod.parse, def.type);\n"
        ],
        [
          6383,
          6453,
          "globalThis.__zod_globalConfig ??= {};\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/parse.cjs",
    "sha256": "e2cd027e1da3de80571210f613e77dc02b1278cdac3d4e148166cd522c5028a5",
    "variants": {
      "e19bfe843aed1844680a014f9a185d17374fe87bcd1676a2d62ed11177c1caa8": [
        [
          14,
          1041,
          ""
        ],
        [
          1675,
          1829,
          "const bortusBudget = require(\"../../bortus-budget.js\");\nconst core = require(\"./core.js\");\nconst errors = require(\"./errors.js\");\nconst util = require(\"./util.js\");\n"
        ],
        [
          2117,
          2258,
          "        const ctx = bortusBudget.scope(_ctx, false);\n        let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          2354,
          2354,
          "        result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          2832,
          2903,
          "        const ctx = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          3043,
          3043,
          "        result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          3507,
          3640,
          "    const ctx = bortusBudget.scope(_ctx, false);\n    let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          3724,
          3724,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          5126,
          5193,
          "    const ctx = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          5321,
          5321,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          6075,
          6448,
          "    // BORTUS: validators without a context cannot enforce the shared parse budget.\n"
        ],
        [
          6551,
          6672,
          "    const ctx = { ...bortusBudget.scope(_ctx, false), abortEarly: true };\n"
        ],
        [
          7127,
          7166,
          "    return bortusBudget.finishV4(result, ctx).issues.length === 0;\n"
        ],
        [
          7372,
          7491,
          "    const ctx = { ...bortusBudget.scope(_ctx, true), abortEarly: true };\n"
        ],
        [
          7619,
          7658,
          "    return bortusBudget.finishV4(result, ctx).issues.length === 0;\n"
        ],
        [
          10374,
          11002,
          ""
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/parse.js",
    "sha256": "04340cdceeb538cce42a68cfba21b3c3053a6ace5ab5ba15b88cfc34d36bd3b6",
    "variants": {
      "fb05b91ec260f3f484f7c00a177b6126ceb8fd1b09dc90b1200afdffd4d98efd": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          404,
          545,
          "        const ctx = bortusBudget.scope(_ctx, false);\n        let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          641,
          641,
          "        result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          1108,
          1179,
          "        const ctx = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          1319,
          1319,
          "        result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          1762,
          1895,
          "    const ctx = bortusBudget.scope(_ctx, false);\n    let result = schema._zod.run({ value, issues: [] }, ctx);\n"
        ],
        [
          1979,
          1979,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          3362,
          3429,
          "    const ctx = bortusBudget.scope(_ctx, true);\n"
        ],
        [
          3557,
          3557,
          "    result = bortusBudget.finishV4(result, ctx);\n"
        ],
        [
          4280,
          4653,
          "    // BORTUS: validators without a context cannot enforce the shared parse budget.\n"
        ],
        [
          4756,
          4877,
          "    const ctx = { ...bortusBudget.scope(_ctx, false), abortEarly: true };\n"
        ],
        [
          5332,
          5371,
          "    return bortusBudget.finishV4(result, ctx).issues.length === 0;\n"
        ],
        [
          5584,
          5703,
          "    const ctx = { ...bortusBudget.scope(_ctx, true), abortEarly: true };\n"
        ],
        [
          5831,
          5870,
          "    return bortusBudget.finishV4(result, ctx).issues.length === 0;\n"
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/schemas.cjs",
    "sha256": "6b0e733b21ead8e35157525d5a78c1c2f489db340c287441bdfdff14a7715bf4",
    "variants": {
      "7e35563b275bcc457a6d8ae0f5e1354b3c499ddd38401439f16bed1b8f357e41": [
        [
          14,
          1041,
          ""
        ],
        [
          3524,
          3865,
          "const bortusBudget = require(\"../../bortus-budget.js\");\nconst checks = require(\"./checks.js\");\nconst core = require(\"./core.js\");\nconst doc_js_1 = require(\"./doc.js\");\nconst parse_js_1 = require(\"./parse.js\");\nconst regexes = require(\"./regexes.js\");\nconst util = require(\"./util.js\");\nconst versions_js_1 = require(\"./versions.js\");\n"
        ],
        [
          3931,
          3968,
          "    inst ??= {};\n"
        ],
        [
          4614,
          4671,
          "        inst._zod.deferred ??= [];\n"
        ],
        [
          4712,
          4757,
          "            inst._zod.run = (def.type === \"array\" || def.type === \"map\" || def.type === \"set\") ? ((payload, ctx) => {\n                if (bortusCollectionIssue(inst, payload, ctx))\n                    return payload;\n                return inst._zod.parse(payload, ctx);\n            }) : inst._zod.parse;\n"
        ],
        [
          5021,
          5021,
          "                if (bortusBudget.exhausted(ctx))\n                    break;\n"
        ],
        [
          8082,
          8082,
          "            if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload, ctx))\n                return payload;\n"
        ],
        [
          9869,
          9908,
          "var util_js_1 = require(\"./util.js\");\n"
        ],
        [
          11018,
          11067,
          "    def.pattern ??= regexes.guid;\n"
        ],
        [
          11541,
          11597,
          "        def.pattern ??= regexes.uuid(v);\n"
        ],
        [
          11612,
          11667,
          "        def.pattern ??= regexes.uuid();\n"
        ],
        [
          11785,
          11835,
          "    def.pattern ??= regexes.email;\n"
        ],
        [
          16564,
          16616,
          "    def.pattern ??= regexes.emoji();\n"
        ],
        [
          16888,
          17003,
          "    def.pattern ??= def.length === undefined ? regexes.nanoid : regexes.nanoidOfLength(def.length);\n"
        ],
        [
          17319,
          17368,
          "    def.pattern ??= regexes.cuid;\n"
        ],
        [
          17486,
          17536,
          "    def.pattern ??= regexes.cuid2;\n"
        ],
        [
          17652,
          17701,
          "    def.pattern ??= regexes.ulid;\n"
        ],
        [
          17815,
          17863,
          "    def.pattern ??= regexes.xid;\n"
        ],
        [
          17981,
          18031,
          "    def.pattern ??= regexes.ksuid;\n"
        ],
        [
          18161,
          18219,
          "    def.pattern ??= regexes.datetime(def);\n"
        ],
        [
          18341,
          18390,
          "    def.pattern ??= regexes.date;\n"
        ],
        [
          18512,
          18566,
          "    def.pattern ??= regexes.time(def);\n"
        ],
        [
          18696,
          18749,
          "    def.pattern ??= regexes.duration;\n"
        ],
        [
          18865,
          18914,
          "    def.pattern ??= regexes.ipv4;\n"
        ],
        [
          19604,
          19653,
          "    def.pattern ??= regexes.ipv6;\n"
        ],
        [
          20084,
          20147,
          "    def.pattern ??= regexes.mac(def.delimiter);\n"
        ],
        [
          20267,
          20318,
          "    def.pattern ??= regexes.cidrv4;\n"
        ],
        [
          20826,
          20904,
          "    def.pattern ??= regexes.cidrv6; // not used for validation\n"
        ],
        [
          22031,
          22089,
          "    def.pattern ??= exports.base64Charset;\n"
        ],
        [
          23074,
          23135,
          "    def.pattern ??= exports.base64urlCharset;\n"
        ],
        [
          23557,
          23606,
          "    def.pattern ??= regexes.e164;\n"
        ],
        [
          24543,
          24598,
          "    def.pattern ??= regexes.creditCard;\n"
        ],
        [
          25811,
          25860,
          "    def.pattern ??= regexes.iban;\n"
        ],
        [
          34900,
          34900,
          "// BORTUS: cap collection work before traversal; only leading size checks may reject early.\n// A preceding refinement/overwrite remains a barrier. The default cap is always enforced.\nfunction bortusCollectionIssue(inst, payload, ctx) {\n    bortusBudget.prepareV4(payload, ctx);\n    if (bortusBudget.exhausted(ctx))\n        return true;\n    const input = payload.value;\n    const kind = inst._zod.def.type;\n    const size = kind === \"array\" ? (Array.isArray(input) ? input.length : -1)\n        : kind === \"map\" ? (input instanceof Map ? input.size : -1)\n            : kind === \"set\" ? (input instanceof Set ? input.size : -1) : -1;\n    if (size < 0)\n        return false;\n    for (const check of inst._zod.def.checks ?? []) {\n        const def = check._zod.def;\n        if (![\"min_length\", \"max_length\", \"length_equals\", \"min_size\", \"max_size\", \"size_equals\"].includes(def.check))\n            break;\n        const maximum = def.maximum ?? def.length ?? def.size;\n        if (typeof maximum !== \"number\" || size <= maximum || Number.isNaN(maximum))\n            continue;\n        if (def.when && !def.when(payload))\n            continue;\n        const start = payload.issues.length;\n        check._zod.check(payload);\n        if (payload.issues.length > start) {\n            payload.issues[start].continue = false;\n            return true;\n        }\n    }\n    if (size > 10000) {\n        payload.issues.push({ code: \"too_big\", origin: kind, maximum: 10000,\n            inclusive: true, input, inst, continue: false });\n        return true;\n    }\n    return !bortusBudget.admit(ctx, size);\n}\n"
        ],
        [
          43210,
          43256,
          "        value ??= _normalized.value;\n"
        ],
        [
          49616,
          49662,
          "        value ??= _normalized.value;\n"
        ],
        [
          62581,
          62627,
          "            unrecIssue ??= iss;\n"
        ],
        [
          71141,
          71141,
          "                if (bortusBudget.exhausted(ctx))\n                    break;\n"
        ],
        [
          73290,
          73290,
          "                if (bortusBudget.exhausted(ctx))\n                    break;\n"
        ],
        [
          74766,
          74766,
          "                if (bortusBudget.exhausted(ctx))\n                    break;\n"
        ],
        [
          101235,
          101291,
          "        isInt ||= !!d.format?.includes(\"int\");\n"
        ],
        [
          110203,
          110831,
          ""
        ]
      ]
    },
    "create": null
  },
  {
    "path": "v4/core/schemas.js",
    "sha256": "1585fbe564311d16f33aa51dd5eb0dfcc599bff738f6a51db5d19c91a89fef95",
    "variants": {
      "0ee56e8afbae28eeb1060a162ad7e56f0675ee6fb83f0ae56bea2e088f6cdbc0": [
        [
          0,
          0,
          "import * as bortusBudget from \"../../bortus-budget.js\";\n"
        ],
        [
          356,
          393,
          "    inst ??= {};\n"
        ],
        [
          1025,
          1082,
          "        inst._zod.deferred ??= [];\n"
        ],
        [
          1123,
          1168,
          "            inst._zod.run = (def.type === \"array\" || def.type === \"map\" || def.type === \"set\") ? ((payload, ctx) => {\n                if (bortusCollectionIssue(inst, payload, ctx))\n                    return payload;\n                return inst._zod.parse(payload, ctx);\n            }) : inst._zod.parse;\n"
        ],
        [
          1432,
          1432,
          "                if (bortusBudget.exhausted(ctx))\n                    break;\n"
        ],
        [
          4493,
          4493,
          "            if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload, ctx))\n                return payload;\n"
        ],
        [
          7364,
          7413,
          "    def.pattern ??= regexes.guid;\n"
        ],
        [
          7898,
          7954,
          "        def.pattern ??= regexes.uuid(v);\n"
        ],
        [
          7969,
          8024,
          "        def.pattern ??= regexes.uuid();\n"
        ],
        [
          8153,
          8203,
          "    def.pattern ??= regexes.email;\n"
        ],
        [
          12958,
          13010,
          "    def.pattern ??= regexes.emoji();\n"
        ],
        [
          13293,
          13408,
          "    def.pattern ??= def.length === undefined ? regexes.nanoid : regexes.nanoidOfLength(def.length);\n"
        ],
        [
          13735,
          13784,
          "    def.pattern ??= regexes.cuid;\n"
        ],
        [
          13913,
          13963,
          "    def.pattern ??= regexes.cuid2;\n"
        ],
        [
          14090,
          14139,
          "    def.pattern ??= regexes.ulid;\n"
        ],
        [
          14264,
          14312,
          "    def.pattern ??= regexes.xid;\n"
        ],
        [
          14441,
          14491,
          "    def.pattern ??= regexes.ksuid;\n"
        ],
        [
          14632,
          14690,
          "    def.pattern ??= regexes.datetime(def);\n"
        ],
        [
          14823,
          14872,
          "    def.pattern ??= regexes.date;\n"
        ],
        [
          15005,
          15059,
          "    def.pattern ??= regexes.time(def);\n"
        ],
        [
          15200,
          15253,
          "    def.pattern ??= regexes.duration;\n"
        ],
        [
          15380,
          15429,
          "    def.pattern ??= regexes.ipv4;\n"
        ],
        [
          16137,
          16186,
          "    def.pattern ??= regexes.ipv6;\n"
        ],
        [
          16628,
          16691,
          "    def.pattern ??= regexes.mac(def.delimiter);\n"
        ],
        [
          16822,
          16873,
          "    def.pattern ??= regexes.cidrv4;\n"
        ],
        [
          17399,
          17477,
          "    def.pattern ??= regexes.cidrv6; // not used for validation\n"
        ],
        [
          18627,
          18677,
          "    def.pattern ??= base64Charset;\n"
        ],
        [
          19677,
          19730,
          "    def.pattern ??= base64urlCharset;\n"
        ],
        [
          20163,
          20212,
          "    def.pattern ??= regexes.e164;\n"
        ],
        [
          21167,
          21222,
          "    def.pattern ??= regexes.creditCard;\n"
        ],
        [
          22453,
          22502,
          "    def.pattern ??= regexes.iban;\n"
        ],
        [
          31706,
          31706,
          "// BORTUS: cap collection work before traversal; only leading size checks may reject early.\n// A preceding refinement/overwrite remains a barrier. The default cap is always enforced.\nfunction bortusCollectionIssue(inst, payload, ctx) {\n    bortusBudget.prepareV4(payload, ctx);\n    if (bortusBudget.exhausted(ctx))\n        return true;\n    const input = payload.value;\n    const kind = inst._zod.def.type;\n    const size = kind === \"array\" ? (Array.isArray(input) ? input.length : -1)\n        : kind === \"map\" ? (input instanceof Map ? input.size : -1)\n            : kind === \"set\" ? (input instanceof Set ? input.size : -1) : -1;\n    if (size < 0)\n        return false;\n    for (const check of inst._zod.def.checks ?? []) {\n        const def = check._zod.def;\n        if (![\"min_length\", \"max_length\", \"length_equals\", \"min_size\", \"max_size\", \"size_equals\"].includes(def.check))\n            break;\n        const maximum = def.maximum ?? def.length ?? def.size;\n        if (typeof maximum !== \"number\" || size <= maximum || Number.isNaN(maximum))\n            continue;\n        if (def.when && !def.when(payload))\n            continue;\n        const start = payload.issues.length;\n        check._zod.check(payload);\n        if (payload.issues.length > start) {\n            payload.issues[start].continue = false;\n            return true;\n        }\n    }\n    if (size > 10000) {\n        payload.issues.push({ code: \"too_big\", origin: kind, maximum: 10000,\n            inclusive: true, input, inst, continue: false });\n        return true;\n    }\n    return !bortusBudget.admit(ctx, size);\n}\n"
        ],
        [
          40038,
          40084,
          "        value ??= _normalized.value;\n"
        ],
        [
          46446,
          46492,
          "        value ??= _normalized.value;\n"
        ],
        [
          59455,
          59501,
          "            unrecIssue ??= iss;\n"
        ],
        [
          68037,
          68037,
          "                if (bortusBudget.exhausted(ctx))\n                    break;\n"
        ],
        [
          70186,
          70186,
          "                if (bortusBudget.exhausted(ctx))\n                    break;\n"
        ],
        [
          71662,
          71662,
          "                if (bortusBudget.exhausted(ctx))\n                    break;\n"
        ],
        [
          98340,
          98396,
          "        isInt ||= !!d.format?.includes(\"int\");\n"
        ]
      ]
    },
    "create": null
  }
];
try {
  if (JSON.parse(readFileSync(path.join(directory, "package.json"), "utf8")).version !== "4.6.7")
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
  console.log("Verified Zod 4.6.7 maintained admission and shared parse budget in v3/v4 source, CJS and ESM");
} catch {
  console.error("Zod collection backport verification failed; installation/build stopped");
  process.exitCode = 1;
}
