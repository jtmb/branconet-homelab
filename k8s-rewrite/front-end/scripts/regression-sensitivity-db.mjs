import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, symlinkSync, rmSync, lstatSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(readFileSync(new URL("./regression-sensitivity-db.json", import.meta.url), "utf8"));
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const started = Date.now(), deadline = started + 240_000, reserveMs = 20_000, outputLimit = 1024 * 1024;
assert.equal(manifest.schema, 1);
assert.deepEqual(manifest.cases.map(row => row.id), ["A02-deleted-account", "A03-bootstrap-writer"]);
assert.equal(manifest.files.length, 29);
const flatRunner = readFileSync(join(root, "scripts/regression-sensitivity.mjs"));
assert.equal(sha(flatRunner), manifest.flatRunnerSHA256);
const originals = new Map();
for (const row of manifest.files) {
  assert.ok(!originals.has(row.path) && !row.path.includes("\\") && !row.path.split("/").includes("..") && !row.path.startsWith("/"));
  assert.ok(row.path === "package.json" || row.path === "tsconfig.json" ||
    /^src\/lib\/[a-z-]+\.ts$/.test(row.path) || /^tests\/(accounts|account-registration)\.test\.ts$/.test(row.path) ||
    row.path === "prisma/schema.prisma" || row.path === "prisma/migrations/migration_lock.toml" ||
    /^prisma\/migrations\/\d{14}_[a-z_]+\/migration\.sql$/.test(row.path) ||
    ["runtime/direct-account-reader-worker.cjs", "runtime/direct-account-core.cjs", "runtime/direct-account-build.json"].includes(row.path));
  const path = join(root, row.path), stat = lstatSync(path);
  assert.ok(stat.isFile() && !stat.isSymbolicLink());
  const bytes = readFileSync(path); assert.equal(sha(bytes), row.sha256, `Input changed: ${row.path}`); originals.set(row.path, bytes);
}
const workerReceipt = JSON.parse(originals.get("runtime/direct-account-build.json").toString("utf8"));
assert.equal(workerReceipt.sourceSHA256, sha(originals.get("src/lib/direct-account-core.ts")));
assert.equal(workerReceipt.coreSHA256, sha(originals.get("runtime/direct-account-core.cjs")));
assert.equal(workerReceipt.workerSHA256, sha(originals.get("runtime/direct-account-reader-worker.cjs")));
assert.equal(workerReceipt.typescript, "5.9.3");
const loader = import.meta.resolve("tsx");
const work = mkdtempSync(join(tmpdir(), "bortus-db-sensitivity-"));
const records = [], restorationFailures = [];
let primary;
function checkOriginals() {
  for (const [path, bytes] of originals) assert.ok(readFileSync(join(root, path)).equals(bytes), `Original changed: ${path}`);
  assert.ok(readFileSync(join(root, "scripts/regression-sensitivity.mjs")).equals(flatRunner));
}
// Fixed two-level TAP from the unchanged test() parents and their direct t.test() children.
function checkTap(out, row, phase) {
  const matches = [...out.matchAll(/^( *)(ok|not ok) \d+ - (.+)$/gm)];
  assert.deepEqual(matches.map(m => ({ indent: m[1].length, name: m[3] })),
    [...row.children.map(name => ({ indent: 4, name })), { indent: 0, name: row.parent }]);
  const intended = phase === "pristine" ? [] : row.failures;
  assert.deepEqual(matches.filter(m => m[2] === "not ok").map(m => m[3]),
    intended.length ? [...intended.map(value => value.name), row.parent] : []);
  for (const m of matches.filter(value => value[2] === "not ok")) {
    const rest = out.slice(m.index + m[0].length + 1), indent = " ".repeat(m[1].length + 2);
    assert.ok(rest.startsWith(indent + "---\n"));
    const end = rest.indexOf("\n" + indent + "..."); assert.ok(end > 0);
    const block = rest.slice(0, end);
    if (!m[1].length) {
      assert.ok(block.includes("failureType: 'subtestsFailed'") && block.includes("code: 'ERR_TEST_FAILURE'"));
      assert.ok(!block.includes("code: 'ERR_ASSERTION'"));
    } else {
      const expected = intended.find(value => value.name === m[3]); assert.ok(expected);
      for (const literal of ["failureType: 'testCodeFailure'", "code: 'ERR_ASSERTION'", "name: 'AssertionError'", "operator: 'strictEqual'", ...expected.witnesses])
        assert.ok(block.includes(literal), `Wrong assertion metadata: ${row.id}`);
      assert.match(block, new RegExp(`${row.testFile.split("/").at(-1).replaceAll(".", "\\.")}:${expected.line}:\\d+`));
    }
  }
  const failed = intended.length ? intended.length + 1 : 0, total = row.children.length + 1;
  for (const [name, count] of [["tests", total], ["pass", total - failed], ["fail", failed], ["cancelled", 0], ["skipped", 0], ["todo", 0]])
    assert.match(out, new RegExp(`^# ${name} ${count}$`, "m"));
}
function run(row, copy, phase) {
  const timeout = Math.min(30_000, deadline - Date.now() - reserveMs); assert.ok(timeout > 0, "DB sensitivity deadline exhausted");
  const env = { ...process.env, NODE_OPTIONS: "", NO_COLOR: "1" }; delete env.FORCE_COLOR;
  const child = spawnSync(process.execPath, ["--import", loader, "--test", "--experimental-test-isolation=none", "--test-reporter=tap", row.testFile], {
    cwd: copy, env, timeout, killSignal: "SIGKILL", maxBuffer: outputLimit, encoding: "utf8", windowsHide: true,
  });
  const out = child.stdout || "", err = child.stderr || "", prefix = `${row.id}-${phase}`;
  const record = { id: row.id, phase, actualExit: child.status, signal: child.signal, spawnErrorCode: child.error?.code || null,
    stdoutSHA256: sha(out), stderrSHA256: sha(err), stdoutBytes: Buffer.byteLength(out), stderrBytes: Buffer.byteLength(err) };
  records.push(record);
  for (const [suffix, text] of [["tap", out], ["stderr", err], ["json", JSON.stringify(record, null, 2) + "\n"]])
    writeFileSync(join(work, `${prefix}.${suffix}`), text, { flag: "wx", mode: 0o600 });
  process.stdout.write(`\n# ${prefix}\n${out}`); if (err) process.stderr.write(err);
  assert.ok(!child.error && child.signal === null, "Child deadline/spawn/output failure");
  assert.ok(Buffer.byteLength(out) <= outputLimit && Buffer.byteLength(err) <= outputLimit);
  // No warning filtering: retain it verbatim. Only this literal Node22 SQLite warning may be emitted.
  const sqliteWarning = `(node:${child.pid}) ExperimentalWarning: SQLite is an experimental feature and might change at any time\n` +
    "(Use `node --trace-warnings ...` to show where the warning was created)\n";
  assert.ok(err === "" || (row.id === "A02-deleted-account" && err === sqliteWarning), "Unexpected stderr");
  assert.equal(child.status, phase === "pristine" ? 0 : 1);
  checkTap(out, row, phase);
}
try {
  for (const row of manifest.cases) {
    const copy = join(work, row.id); mkdirSync(copy, { mode: 0o700 });
    for (const [path, bytes] of originals) {
      mkdirSync(dirname(join(copy, path)), { recursive: true, mode: 0o700 });
      writeFileSync(join(copy, path), bytes, { flag: "wx", mode: 0o600 });
    }
    symlinkSync(join(root, "node_modules"), join(copy, "node_modules"), "dir");
    const sourcePath = join(copy, row.source), before = originals.get(row.source); assert.ok(before);
    try {
      run(row, copy, "pristine");
      const text = before.toString("utf8"); assert.equal(text.split(row.before).length - 1, 1);
      const mutant = Buffer.from(text.replace(row.before, row.after)); assert.equal(sha(mutant), row.mutantSHA256);
      writeFileSync(sourcePath, mutant); run(row, copy, "mutant");
    } finally {
      try { writeFileSync(sourcePath, before); } catch { restorationFailures.push(`${row.id}:restore`); }
      for (const [path, bytes] of originals) {
        try { assert.ok(readFileSync(join(copy, path)).equals(bytes)); } catch { restorationFailures.push(`${row.id}:${path}`); }
      }
      try { checkOriginals(); } catch { restorationFailures.push(`${row.id}:originals`); }
    }
    assert.deepEqual(restorationFailures, []);
  }
} catch (error) { primary = error; }
finally {
  try { checkOriginals(); } catch { restorationFailures.push("final-originals"); }
  for (const row of manifest.cases) {
    try { rmSync(join(work, row.id), { recursive: true, force: true }); } catch { restorationFailures.push(`${row.id}:cleanup`); }
  }
  const result = { schema: 1, completed: !primary && !restorationFailures.length && records.length === 4, cases: manifest.cases.map(row => row.id), records,
    restorationFailures, elapsedMs: Date.now() - started, originalSelectedInputsUnchanged: !restorationFailures.some(v => v.endsWith("originals")),
    flatFiveRunnerUnchanged: true, wholeA19Accepted: false, A01CrossProcessSensitivityQualified: false };
  writeFileSync(join(work, "result.json"), JSON.stringify(result, null, 2) + "\n", { flag: "wx", mode: 0o600 });
  process.stdout.write(JSON.stringify(result) + "\n");
}
if (primary) throw primary;
assert.deepEqual(restorationFailures, []); assert.equal(records.length, 4);
