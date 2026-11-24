import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
if (process.platform === "linux" && process.arch === "x64") {
  const source = path.join(process.cwd(), "native", "secret-flat-selector.node");
  const folder = path.join(process.cwd(), ".next", "standalone", "native");
  fs.mkdirSync(folder, { recursive: true });
  const target = path.join(folder, "secret-flat-selector.node");
  fs.copyFileSync(source, target);
  const hash = file => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
  if (hash(source) !== hash(target)) throw Error("Standalone native selector binding failed");
  console.log(JSON.stringify({ standaloneNativeSelector: "bound", elfSha256: hash(target) }));
}
