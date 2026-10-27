import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

// Zod 3.25.76 compatible backport of early array/set rejection (upstream #6653).
// BORTUS additionally caps each array/set/map at 10000 entries before traversal.
// All application arrays already have bounds <=10000; keep boundedArray guards.
// v4 classic/mini/core share a compatible leading-bound/default10000 run gate.
// No total nested issue budget or package HIGH closure is claimed.
// This is maintained code, not an upstream version upgrade or scanner waiver.
const directory = process.argv[2] ?? path.resolve("node_modules/zod");
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const files = [
  [
    "v3/types.cjs",
    "06487cc05ed45c5dd29789bf0aa75734d1ce06592a7f2665ba4ca90a68e8a3e1",
    "5b3f72231f98fc63d8ff6cc661893fc4aa05736bb574b8d1718db2456a3fc1d5",
    [
      [
        "                    exact: true,\n                    message: def.exactLength.message,\n                });\n                status.dirty();\n            }\n        }\n",
        "                    exact: true,\n                    message: def.exactLength.message,\n                });\n                if (tooBig) return parseUtil_js_1.INVALID;\n                status.dirty();\n            }\n        }\n"
      ],
      [
        "                    exact: false,\n                    message: def.maxLength.message,\n                });\n                status.dirty();\n            }\n        }\n        if (ctx.common.async) {\n            return Promise.all([...ctx.data].map((item, i) => {\n",
        "                    exact: false,\n                    message: def.maxLength.message,\n                });\n                return parseUtil_js_1.INVALID;\n            }\n        }\n        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.length > 10000) {\n            (0, parseUtil_js_1.addIssueToContext)(ctx, { code: ZodError_js_1.ZodIssueCode.too_big, maximum: 10000, type: \"array\", inclusive: true, exact: false });\n            return parseUtil_js_1.INVALID;\n        }\n        if (ctx.common.async) {\n            return Promise.all([...ctx.data].map((item, i) => {\n"
      ],
      [
        "                expected: util_js_1.ZodParsedType.map,\n                received: ctx.parsedType,\n            });\n            return parseUtil_js_1.INVALID;\n        }\n        const keyType = this._def.keyType;\n",
        "                expected: util_js_1.ZodParsedType.map,\n                received: ctx.parsedType,\n            });\n            return parseUtil_js_1.INVALID;\n        }\n        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            (0, parseUtil_js_1.addIssueToContext)(ctx, { code: ZodError_js_1.ZodIssueCode.custom, message: \"Map exceeds the BORTUS 10000-entry validation limit\", fatal: true });\n            return parseUtil_js_1.INVALID;\n        }\n        const keyType = this._def.keyType;\n"
      ],
      [
        "                    exact: false,\n                    message: def.maxSize.message,\n                });\n                status.dirty();\n            }\n        }\n        const valueType = this._def.valueType;\n        function finalizeSet(elements) {\n",
        "                    exact: false,\n                    message: def.maxSize.message,\n                });\n                return parseUtil_js_1.INVALID;\n            }\n        }\n        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            (0, parseUtil_js_1.addIssueToContext)(ctx, { code: ZodError_js_1.ZodIssueCode.too_big, maximum: 10000, type: \"set\", inclusive: true, exact: false });\n            return parseUtil_js_1.INVALID;\n        }\n        const valueType = this._def.valueType;\n        function finalizeSet(elements) {\n"
      ]
    ]
  ],
  [
    "v3/types.js",
    "9763a2938f0e7f983363ef4bf6530e7583e3f2d54f8a4a6684efad58febc6e8e",
    "100470f7b530b15c8aec05fc6c17a1810286654ff83f877d1e638b08d382a07b",
    [
      [
        "                    exact: true,\n                    message: def.exactLength.message,\n                });\n                status.dirty();\n            }\n        }\n",
        "                    exact: true,\n                    message: def.exactLength.message,\n                });\n                if (tooBig) return INVALID;\n                status.dirty();\n            }\n        }\n"
      ],
      [
        "                    exact: false,\n                    message: def.maxLength.message,\n                });\n                status.dirty();\n            }\n        }\n        if (ctx.common.async) {\n            return Promise.all([...ctx.data].map((item, i) => {\n",
        "                    exact: false,\n                    message: def.maxLength.message,\n                });\n                return INVALID;\n            }\n        }\n        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.length > 10000) {\n            addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"array\", inclusive: true, exact: false });\n            return INVALID;\n        }\n        if (ctx.common.async) {\n            return Promise.all([...ctx.data].map((item, i) => {\n"
      ],
      [
        "                expected: ZodParsedType.map,\n                received: ctx.parsedType,\n            });\n            return INVALID;\n        }\n        const keyType = this._def.keyType;\n",
        "                expected: ZodParsedType.map,\n                received: ctx.parsedType,\n            });\n            return INVALID;\n        }\n        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            addIssueToContext(ctx, { code: ZodIssueCode.custom, message: \"Map exceeds the BORTUS 10000-entry validation limit\", fatal: true });\n            return INVALID;\n        }\n        const keyType = this._def.keyType;\n"
      ],
      [
        "                    exact: false,\n                    message: def.maxSize.message,\n                });\n                status.dirty();\n            }\n        }\n        const valueType = this._def.valueType;\n        function finalizeSet(elements) {\n",
        "                    exact: false,\n                    message: def.maxSize.message,\n                });\n                return INVALID;\n            }\n        }\n        // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n        if (ctx.data.size > 10000) {\n            addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"set\", inclusive: true, exact: false });\n            return INVALID;\n        }\n        const valueType = this._def.valueType;\n        function finalizeSet(elements) {\n"
      ]
    ]
  ],
  [
    "src/v3/types.ts",
    "70309a0877c35d036842e291fe7c8a4439d5db49411d233f8a22bf8a59c41419",
    "311ca5077ac866abbaa9fee38c98fb931c3e74b347f3d5dd219d16309790be20",
    [
      [
        "          exact: true,\n          message: def.exactLength.message,\n        });\n        status.dirty();\n      }\n    }\n",
        "          exact: true,\n          message: def.exactLength.message,\n        });\n        if (tooBig) return INVALID;\n        status.dirty();\n      }\n    }\n"
      ],
      [
        "          exact: false,\n          message: def.maxLength.message,\n        });\n        status.dirty();\n      }\n    }\n\n    if (ctx.common.async) {\n      return Promise.all(\n        ([...ctx.data] as any[]).map((item, i) => {\n",
        "          exact: false,\n          message: def.maxLength.message,\n        });\n        return INVALID;\n      }\n    }\n\n    // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n    if (ctx.data.length > 10000) {\n      addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"array\", inclusive: true, exact: false });\n      return INVALID;\n    }\n    if (ctx.common.async) {\n      return Promise.all(\n        ([...ctx.data] as any[]).map((item, i) => {\n"
      ],
      [
        "      return INVALID;\n    }\n\n    const keyType = this._def.keyType;\n    const valueType = this._def.valueType;\n\n",
        "      return INVALID;\n    }\n\n    // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n    if (ctx.data.size > 10000) {\n      addIssueToContext(ctx, { code: ZodIssueCode.custom, message: \"Map exceeds the BORTUS 10000-entry validation limit\", fatal: true });\n      return INVALID;\n    }\n    const keyType = this._def.keyType;\n    const valueType = this._def.valueType;\n\n"
      ],
      [
        "          exact: false,\n          message: def.maxSize.message,\n        });\n        status.dirty();\n      }\n    }\n\n    const valueType = this._def.valueType;\n\n    function finalizeSet(elements: SyncParseReturnType<any>[]) {\n",
        "          exact: false,\n          message: def.maxSize.message,\n        });\n        return INVALID;\n      }\n    }\n\n    // BORTUS: finite default ceiling; explicit tighter bounds are checked first.\n    if (ctx.data.size > 10000) {\n      addIssueToContext(ctx, { code: ZodIssueCode.too_big, maximum: 10000, type: \"set\", inclusive: true, exact: false });\n      return INVALID;\n    }\n    const valueType = this._def.valueType;\n\n    function finalizeSet(elements: SyncParseReturnType<any>[]) {\n"
      ]
    ]
  ],
[
  "src/v4/core/schemas.ts",
  "5910d2a181b6570189730578df0ff7c90bd7b2cda6ae1064026d236a47fb687d",
  "f2cf342102403a2881b6c9fa8dc04a1b40bc313f4dd46260a30042d72e2a368d",
  [
    [
      "function handleArrayResult(",
      "// BORTUS: cap collection work before traversal; only leading size checks may reject early.\n// A preceding refinement/overwrite remains a barrier. The default cap is always enforced.\nfunction bortusCollectionIssue(inst: $ZodType, payload: ParsePayload): boolean {\n  const input = payload.value;\n  const kind = inst._zod.def.type;\n  const size = kind === \"array\" ? (Array.isArray(input) ? input.length : -1)\n    : kind === \"map\" ? (input instanceof Map ? input.size : -1)\n    : kind === \"set\" ? (input instanceof Set ? input.size : -1) : -1;\n  if (size < 0) return false;\n  for (const check of inst._zod.def.checks ?? []) {\n    const def = check._zod.def as checks.$ZodCheckDef & { maximum?: number; length?: number; size?: number };\n    if (![\"min_length\", \"max_length\", \"length_equals\", \"min_size\", \"max_size\", \"size_equals\"].includes(def.check)) break;\n    const maximum = def.maximum ?? def.length ?? def.size;\n    if (typeof maximum !== \"number\" || size <= maximum || Number.isNaN(maximum)) continue;\n    if (def.when && !def.when(payload)) continue;\n    const start = payload.issues.length;\n    check._zod.check(payload as ParsePayload<never>);\n    if (payload.issues.length > start) {\n      (payload.issues[start] as { continue?: boolean }).continue = false;\n      return true;\n    }\n  }\n  if (size > 10000) {\n    payload.issues.push({ code: \"too_big\", origin: kind as \"array\" | \"map\" | \"set\", maximum: 10000,\n      inclusive: true, input, inst, continue: false });\n    return true;\n  }\n  return false;\n}\n\nfunction handleArrayResult("
    ],
    [
      "      inst._zod.run = inst._zod.parse;",
      "      inst._zod.run = (def.type === \"array\" || def.type === \"map\" || def.type === \"set\") ? ((payload, ctx) => {\n        if (bortusCollectionIssue(inst, payload)) return payload;\n        return inst._zod.parse(payload, ctx);\n      }) : inst._zod.parse;"
    ],
    [
      "      const result = inst._zod.parse(payload, ctx);",
      "      if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload)) return payload;\n      const result = inst._zod.parse(payload, ctx);"
    ]
  ]
],
[
  "v4/core/schemas.js",
  "d466582c022b08a3f9eb1a65d5970d8ca25064d73a5a838d76414ae36440a76b",
  "f6b44933bdd0c6e0687e5a4157ebb304cdbcdd2ec8bea1c09529641c766ef28c",
  [
    [
      "function handleArrayResult(",
      "// BORTUS: cap collection work before traversal; only leading size checks may reject early.\n// A preceding refinement/overwrite remains a barrier. The default cap is always enforced.\nfunction bortusCollectionIssue(inst, payload) {\n  const input = payload.value;\n  const kind = inst._zod.def.type;\n  const size = kind === \"array\" ? (Array.isArray(input) ? input.length : -1)\n    : kind === \"map\" ? (input instanceof Map ? input.size : -1)\n    : kind === \"set\" ? (input instanceof Set ? input.size : -1) : -1;\n  if (size < 0) return false;\n  for (const check of inst._zod.def.checks ?? []) {\n    const def = check._zod.def;\n    if (![\"min_length\", \"max_length\", \"length_equals\", \"min_size\", \"max_size\", \"size_equals\"].includes(def.check)) break;\n    const maximum = def.maximum ?? def.length ?? def.size;\n    if (typeof maximum !== \"number\" || size <= maximum || Number.isNaN(maximum)) continue;\n    if (def.when && !def.when(payload)) continue;\n    const start = payload.issues.length;\n    check._zod.check(payload);\n    if (payload.issues.length > start) {\n      (payload.issues[start]).continue = false;\n      return true;\n    }\n  }\n  if (size > 10000) {\n    payload.issues.push({ code: \"too_big\", origin: kind, maximum: 10000,\n      inclusive: true, input, inst, continue: false });\n    return true;\n  }\n  return false;\n}\n\nfunction handleArrayResult("
    ],
    [
      "            inst._zod.run = inst._zod.parse;",
      "            inst._zod.run = (def.type === \"array\" || def.type === \"map\" || def.type === \"set\") ? ((payload, ctx) => {\n              if (bortusCollectionIssue(inst, payload)) return payload;\n              return inst._zod.parse(payload, ctx);\n            }) : inst._zod.parse;"
    ],
    [
      "            const result = inst._zod.parse(payload, ctx);",
      "            if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload)) return payload;\n            const result = inst._zod.parse(payload, ctx);"
    ]
  ]
],
[
  "v4/core/schemas.cjs",
  "f5d17a7db487c943c9d07cc624010ebb6d93683eabd14339846f4912cc88b51f",
  "fa143dce9bd9415fbfc54b44be93fd1953d52988cfb6ab46958eb1e27459ba1e",
  [
    [
      "function handleArrayResult(",
      "// BORTUS: cap collection work before traversal; only leading size checks may reject early.\n// A preceding refinement/overwrite remains a barrier. The default cap is always enforced.\nfunction bortusCollectionIssue(inst, payload) {\n  const input = payload.value;\n  const kind = inst._zod.def.type;\n  const size = kind === \"array\" ? (Array.isArray(input) ? input.length : -1)\n    : kind === \"map\" ? (input instanceof Map ? input.size : -1)\n    : kind === \"set\" ? (input instanceof Set ? input.size : -1) : -1;\n  if (size < 0) return false;\n  for (const check of inst._zod.def.checks ?? []) {\n    const def = check._zod.def;\n    if (![\"min_length\", \"max_length\", \"length_equals\", \"min_size\", \"max_size\", \"size_equals\"].includes(def.check)) break;\n    const maximum = def.maximum ?? def.length ?? def.size;\n    if (typeof maximum !== \"number\" || size <= maximum || Number.isNaN(maximum)) continue;\n    if (def.when && !def.when(payload)) continue;\n    const start = payload.issues.length;\n    check._zod.check(payload);\n    if (payload.issues.length > start) {\n      (payload.issues[start]).continue = false;\n      return true;\n    }\n  }\n  if (size > 10000) {\n    payload.issues.push({ code: \"too_big\", origin: kind, maximum: 10000,\n      inclusive: true, input, inst, continue: false });\n    return true;\n  }\n  return false;\n}\n\nfunction handleArrayResult("
    ],
    [
      "            inst._zod.run = inst._zod.parse;",
      "            inst._zod.run = (def.type === \"array\" || def.type === \"map\" || def.type === \"set\") ? ((payload, ctx) => {\n              if (bortusCollectionIssue(inst, payload)) return payload;\n              return inst._zod.parse(payload, ctx);\n            }) : inst._zod.parse;"
    ],
    [
      "            const result = inst._zod.parse(payload, ctx);",
      "            if ((def.type === \"array\" || def.type === \"map\" || def.type === \"set\") && bortusCollectionIssue(inst, payload)) return payload;\n            const result = inst._zod.parse(payload, ctx);"
    ]
  ]
]
];
try {
  if (JSON.parse(readFileSync(path.join(directory, "package.json"), "utf8")).version !== "3.25.76")
    throw new Error("Unsupported Zod version");
  const verified = files.map(([file, before, after, changes]) => {
    const target = path.join(directory, file), bytes = readFileSync(target), original = bytes.toString("utf8");
    if (hash(bytes) === after) return { target, changed: false };
    if (hash(bytes) !== before) throw new Error("Unexpected Zod source");
    let source = original;
    for (const [from, to] of changes) {
      if (source.split(from).length !== 2) throw new Error("Unexpected Zod patch location");
      source = source.replace(from, to);
    }
    if (hash(source) !== after) throw new Error("Unexpected patched Zod source");
    return { target, changed: true, source };
  });
  for (const item of verified) if (item.changed) writeFileSync(item.target, item.source);
  console.log("Verified Zod 3.25.76 maintained collection admission in root/v3 and v4 source, CJS and ESM");
} catch {
  console.error("Zod collection backport verification failed; installation/build stopped");
  process.exitCode = 1;
}
