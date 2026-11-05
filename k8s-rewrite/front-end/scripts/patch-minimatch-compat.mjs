import { createHash } from "node:crypto";
import { existsSync, lstatSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

// Upgrade the actual matching engine, retaining the legacy import shape only.
// Never restore makeRe: the sole legacy rule uses the fixed matcher directly.
const patches = [
  {
    "path": "minimatch/dist/commonjs/index.js",
    "before": "d89e8ca7dda77bd9dc9efed6920b0ed09deb2f478ada54110980daa3080d3f9b",
    "after": "9dd68ac255a24ea7055314faf273b923ec8a91d577ca5f885ebabece134b6962",
    "edits": [
      [
        "append",
        "\n// BORTUS: preserve legacy callable CommonJS imports using the fixed upstream matcher.\nmodule.exports = Object.assign(exports.minimatch, exports);\n"
      ]
    ]
  },
  {
    "path": "minimatch/dist/esm/index.js",
    "before": "c2ac65e82b196476009b53e1939811c788cb001d910304c6108a1f665fac3c3d",
    "after": "8497568cdc4a694b393ccd710645356cd25e95c3720d7ecbc4589cfcf5866dca",
    "edits": [
      [
        "append",
        "\n// BORTUS: preserve legacy default imports using the fixed upstream matcher.\nexport default minimatch;\n"
      ]
    ]
  },
  {
    "path": "eslint-plugin-import/lib/rules/no-internal-modules.js",
    "before": "f36ab9b9b97cc2d8a49f8fe474c4200875db4fa357c5061fe71538b01db696a4",
    "after": "e77e421c0bba00394cd1c94d57e649722e5c8ca27cd6f302f9f9661ffb9a45f1",
    "edits": [
      [
        "replace",
        "_minimatch2['default'].makeRe(p)",
        "new _minimatch2['default'].Minimatch(p)",
        2
      ],
      [
        "replace",
        "re.test(importPath)",
        "re.match(importPath)",
        2
      ]
    ]
  }
];
const hash = bytes => createHash("sha256").update(bytes).digest("hex");

export function patchMinimatch(directory = path.resolve("node_modules")) {
  const root = realpathSync(directory);
  const omitted = (process.env.npm_config_omit ?? "").split(/\s+/).includes("dev");
  if (omitted && ["minimatch", "eslint-plugin-import"].every(name => !existsSync(path.join(root, name)))) {
    return { files: 0, changed: 0, developmentDependenciesOmitted: true };
  }
  for (const [name, version] of [["minimatch", "11.0.1"], ["eslint-plugin-import", "2.32.0"]]) {
    const manifest = path.join(root, name, "package.json");
    if (!realpathSync(manifest).startsWith(root + path.sep) || JSON.parse(readFileSync(manifest)).version !== version) {
      throw new Error("Unexpected maintained lint dependency identity");
    }
  }
  // Authenticate every target before writing any file. Unknown bytes fail closed.
  const changes = patches.map(spec => {
    const file = path.join(root, spec.path);
    if (!lstatSync(file).isFile() || realpathSync(file) !== file) throw new Error("Unsafe lint patch target");
    const bytes = readFileSync(file), digest = hash(bytes);
    if (digest === spec.after) return { file, bytes, changed: false };
    if (digest !== spec.before) throw new Error(`Unknown lint dependency bytes: ${spec.path}`);
    let text = bytes.toString("utf8");
    for (const edit of spec.edits) {
      if (edit[0] === "append") text += edit[1];
      else {
        if (text.split(edit[1]).length - 1 !== edit[3]) throw new Error("Lint patch occurrence mismatch");
        text = text.split(edit[1]).join(edit[2]);
      }
    }
    const updated = Buffer.from(text);
    if (hash(updated) !== spec.after) throw new Error("Lint patch output mismatch");
    return { file, bytes: updated, changed: true };
  });
  for (const change of changes) if (change.changed) writeFileSync(change.file, change.bytes);
  return { files: changes.length, changed: changes.filter(change => change.changed).length };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  console.log(JSON.stringify(patchMinimatch(process.argv[2])));
}
