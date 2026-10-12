import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";

const hash = file => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const root = process.cwd(), output = path.join(root, "native", "secret-flat-selector.node");
if (process.platform !== "linux" || process.arch !== "x64") {
  console.log(JSON.stringify({ nativeFlatBuild: "portable-development-fallback", platform: process.platform, arch: process.arch }));
} else {
  const compiler = "/usr/bin/x86_64-linux-gnu-gcc-12", linker = "/usr/bin/x86_64-linux-gnu-ld.bfd";
  // No inherited compiler, include, library, preload or locale overrides.
  const compileEnv = { PATH: "/usr/bin:/bin", LANG: "C", LC_ALL: "C", TZ: "UTC", SOURCE_DATE_EPOCH: "0" };
  const selection = ["-B/usr/bin/", "-fuse-ld=bfd"];
  const toolPins = {
    cc1: { realpath: "/usr/lib/gcc/x86_64-linux-gnu/12/cc1", sha256: "18a3506428fe238a6c14c9a39251a11c7203245d632df40ddb8e9d3bf2d387d8" },
    as: { realpath: "/usr/bin/x86_64-linux-gnu-as", sha256: "41fe4f5a03389ea5cf7c92d6753fa1ecc69b45b12534fd8713c53bba0e2d7e17" },
    collect2: { realpath: "/usr/lib/gcc/x86_64-linux-gnu/12/collect2", sha256: "06c070d6b746da665041ea6f2e7d30faf9ef4e1f87cb9c932f963953e32aeec2" },
    "ld.bfd": { realpath: linker, sha256: "f6d71a1bcd45764550a42dfaa179bc43b63ee879ec6f875bfd39fca013515da7" },
  };
  // Immutable public file checksums, retained verbatim for inspection.
  const headerPins = [
    { path: "node_api.h", sha256: "2d4560831e525b47b060ec8a0864ab73993df9e20215ce9f0fe7b24cd31af32a" },
    { path: "js_native_api.h", sha256: "624b39a85f0fe332f7cc1eb537e98f0e119be8503c742265fef6bdd53893adc8" },
    { path: "js_native_api_types.h", sha256: "c63d227f42878411e2a291ce81e0adf83ce57b81c0ea806740108b979b741156" },
    { path: "node_api_types.h", sha256: "088766b3cf1f0cd9b292c361ad30f7a04e7cc6db35a20ca52c572c1adf9635e7" },
  ];
  const headers = Object.fromEntries(headerPins.map(pin => [pin.path, pin.sha256]));
  if (process.version !== "v22.23.3" || hash(process.execPath) !== "fde6a4bf8d0562f7751d1a2d6cb9b417c4cfe107bbcb0aa3e9a24e125e348f48" ||
      hash(compiler) !== "75e997ec62297a6484f491bae28ab0ccb489daba23e398fd10fe68e9e6f0def8" ||
      hash(linker) !== "f6d71a1bcd45764550a42dfaa179bc43b63ee879ec6f875bfd39fca013515da7" ||
      headerPins.some(pin => hash("/usr/local/include/node/" + pin.path) !== pin.sha256)) {
    throw Error("Pinned native selector build inputs unavailable");
  }
  const selectedTools = {};
  for (const [name, expected] of Object.entries(toolPins)) {
    const selected = execFileSync(compiler, [...selection, "-print-prog-name=" + name], { env: compileEnv, encoding: "utf8", timeout: 5000 }).trim();
    const realpath = fs.realpathSync(selected.startsWith("/") ? selected : "/usr/bin/" + selected);
    if (realpath !== expected.realpath || hash(realpath) !== expected.sha256) throw Error("Pinned compiler subtool selection failed");
    selectedTools[name] = { selected, realpath, sha256: hash(realpath) };
  }
  const source = path.join(root, "native", "secret-flat-selector.c"), temp = fs.mkdtempSync(path.join(os.tmpdir(), "bortus-native-build-"));
  try {
    const args = [...selection, "-O3", "-ffreestanding", "-fno-builtin", "-fno-stack-protector", "-fPIC", "-shared", "-DNAPI_VERSION=8", "-DNODE_GYP_MODULE_NAME=selector",
      "-Wl,--build-id=none", "-Wl,-z,noexecstack", "-I/usr/local/include/node", source];
    const first = path.join(temp, "first.node"), second = path.join(temp, "second.node");
    for (const target of [first, second]) execFileSync(compiler, [...args, "-o", target], { timeout: 30000, stdio: "pipe", env: compileEnv });
    if (hash(first) !== hash(second)) throw Error("Native selector build is not reproducible");
    fs.copyFileSync(first, output);
    fs.writeFileSync(path.join(root, "native", "secret-flat-selector-build.json"), JSON.stringify({ scope: "Generated build provenance; not performance acceptance", target: "linux-x64", napi: 8,
      sourceSha256: hash(source), elfSha256: hash(output), compilerSha256: hash(compiler), linkerSha256: hash(linker), headers, identicalCompiles: 2,
      externalRuntimeDependency: "libc memcpy; NAPI symbols resolved by Node", selectedTools, compileEnv, compilerArguments: args }, null, 2) + "\n");
    console.log(JSON.stringify({ nativeFlatBuild: "complete", target: "linux-x64", napi: 8, identicalCompiles: 2, elfSha256: hash(output) }));
  } finally {
    if (path.dirname(temp) !== os.tmpdir() || !path.basename(temp).startsWith("bortus-native-build-")) throw Error("Owned native build cleanup refused");
    fs.rmSync(temp, { recursive: true, force: true });
  }
}
