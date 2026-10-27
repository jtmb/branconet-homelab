import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

// Zod 3.25.76 compatible backport of early array/set rejection (upstream #6653).
// BORTUS additionally caps each array/set/map at 10000 entries before traversal.
// All application arrays already have bounds <=10000; keep boundedArray guards.
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
  console.log("Verified Zod 3.25.76 maintained collection admission in source, CJS and ESM");
} catch {
  console.error("Zod collection backport verification failed; installation/build stopped");
  process.exitCode = 1;
}
