const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const load = process.dlopen;
process.dlopen = function (moduleArg, file, ...args) {
  const result = load.call(this, moduleArg, file, ...args);
  if (path.basename(file) === "secret-flat-selector.node") {
    fs.writeFileSync(process.env.BORTUS_TEST_NATIVE_LOAD_RECORD, JSON.stringify({
      loaded: true,
      artifactDigest: crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex"),
    }));
  }
  return result;
};
