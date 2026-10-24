import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, symlinkSync, rmSync, lstatSync, realpathSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// This runner changes disposable copies only. The original unit/integration suite is separate.
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(readFileSync(new URL("./regression-sensitivity.json", import.meta.url), "utf8"));
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const started = Date.now(), deadline = started + 240_000, reserveMs = 20_000;
const outputLimit = 1024 * 1024;
assert.equal(manifest.schema, 1);
assert.deepEqual(manifest.cases.map(value => value.id), ["A04-name-admission", "A05-failed-stdout", "A06-outage-empty", "deployment-action-coercion", "private-kv-cache-admission"]);
assert.equal(manifest.files.length, 14);
const originals = new Map();
for (const row of manifest.files) {
  assert.ok(/^(?:src\/lib\/[a-z-]+\.ts|tests\/[a-z-]+\.test\.ts|package\.json|tsconfig\.json)$/.test(row.path) ||
    row.path === "src/app/api/cluster/deployments/[namespace]/[name]/action/route.ts");
  assert.ok(!originals.has(row.path));
  const path = join(root, row.path);
  assert.ok(lstatSync(path).isFile() && !lstatSync(path).isSymbolicLink());
  const bytes = readFileSync(path);
  assert.equal(sha(bytes), row.sha256, `Input changed: ${row.path}`);
  originals.set(row.path, bytes);
}
const loader = import.meta.resolve("tsx");
assert.ok(realpathSync(join(root, "node_modules")) !== root);
const work = mkdtempSync(join(tmpdir(), "bortus-regression-sensitivity-"));
const records = [], restorationFailures = [];
let primary;
function checkOriginals() {
  for (const [path, bytes] of originals) assert.ok(readFileSync(join(root, path)).equals(bytes), `Original changed: ${path}`);
}
function run(caseRow, copy, phase) {
  const timeout = Math.min(30_000, deadline - Date.now() - reserveMs);
  assert.ok(timeout > 0, "Sensitivity deadline exhausted");
  const pattern = `^${caseRow.testName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`;
  const env = { ...process.env, NODE_OPTIONS: "", NO_COLOR: "1" };
  delete env.FORCE_COLOR;
  // These filtered mock-only tests stay in this child OS process; normal 342+8 flags are unchanged.
  const child = spawnSync(process.execPath, ["--import", loader, "--test", "--experimental-test-isolation=none", "--test-reporter=tap", `--test-name-pattern=${pattern}`, caseRow.testFile], {
    cwd: copy, env,
    timeout, killSignal: "SIGKILL", maxBuffer: outputLimit, encoding: "utf8", windowsHide: true,
  });
  const out = child.stdout || "", err = child.stderr || "";
  const prefix = `${caseRow.id}-${phase}`;
  writeFileSync(join(work, `${prefix}.tap`), out, { flag: "wx", mode: 0o600 });
  writeFileSync(join(work, `${prefix}.stderr`), err, { flag: "wx", mode: 0o600 });
  const record = { id: caseRow.id, phase, actualExit: child.status, signal: child.signal, spawnErrorCode: child.error?.code || null,
    stdoutSHA256: sha(out), stderrSHA256: sha(err), stdoutBytes: Buffer.byteLength(out), stderrBytes: Buffer.byteLength(err) };
  records.push(record);
  writeFileSync(join(work, `${prefix}.json`), JSON.stringify(record, null, 2) + "\n", { flag: "wx", mode: 0o600 });
  // Only unchanged synthetic unit tests run; preserve their complete bounded TAP in hosted logs.
  process.stdout.write(`\n# ${prefix}\n${out}`);
  if (err) process.stderr.write(err);
  assert.ok(!child.error && child.signal === null, "Child timeout/spawn/output failure");
  assert.equal(err, "", "Unexpected test stderr");
  assert.ok(Buffer.byteLength(out) <= outputLimit && Buffer.byteLength(err) <= outputLimit);
  const failures = [...out.matchAll(/^not ok \d+ - (.+)$/gm)].map(match => match[1]);
  const successes = [...out.matchAll(/^ok \d+ - (.+)$/gm)].map(match => match[1]);
  assert.match(out, /^# cancelled 0$/m);
  if (phase === "pristine") {
    assert.equal(child.status, 0);
    assert.deepEqual(failures, []);
    assert.ok(successes.includes(caseRow.testName));
    assert.match(out, /^# pass 1$/m);
    assert.match(out, /^# fail 0$/m);
  } else {
    assert.equal(child.status, 1);
    assert.deepEqual(failures, [caseRow.testName]);
    assert.match(out, /^# pass 0$/m);
    assert.match(out, /^# fail 1$/m);
    assert.match(out, /failureType: 'testCodeFailure'/);
    assert.match(out, /code: 'ERR_ASSERTION'/);
    assert.match(out, /name: 'AssertionError'/);
    assert.ok(out.includes(`operator: '${caseRow.operator}'`));
    assert.match(out, new RegExp(`${caseRow.testFile.split("/").at(-1).replaceAll(".", "\\.")}:${caseRow.assertionLine}:\\d+`));
    assert.ok(out.includes(caseRow.witness), "Wrong assertion witness");
  }
}
try {
  for (const caseRow of manifest.cases) {
    assert.ok(originals.has(caseRow.source) && originals.has(caseRow.testFile));
    const copy = join(work, caseRow.id);
    mkdirSync(copy, { mode: 0o700 });
    for (const [path, bytes] of originals) {
      mkdirSync(dirname(join(copy, path)), { recursive: true, mode: 0o700 });
      writeFileSync(join(copy, path), bytes, { flag: "wx", mode: 0o600 });
    }
    symlinkSync(join(root, "node_modules"), join(copy, "node_modules"), "dir");
    const sourcePath = join(copy, caseRow.source), before = originals.get(caseRow.source);
    try {
      run(caseRow, copy, "pristine");
      const text = before.toString("utf8");
      assert.equal(text.split(caseRow.before).length - 1, 1, "Replacement is not unique");
      const mutant = Buffer.from(text.replace(caseRow.before, caseRow.after));
      assert.equal(sha(mutant), caseRow.mutantSHA256);
      writeFileSync(sourcePath, mutant);
      run(caseRow, copy, "mutant");
    } finally {
      // Attempt every restoration/check, even if another restoration or assertion fails.
      try { writeFileSync(sourcePath, before); } catch { restorationFailures.push(`${caseRow.id}:restore`); }
      for (const [path, bytes] of originals) {
        try { assert.ok(readFileSync(join(copy, path)).equals(bytes)); } catch { restorationFailures.push(`${caseRow.id}:${path}`); }
      }
      try { checkOriginals(); } catch { restorationFailures.push(`${caseRow.id}:originals`); }
    }
    assert.deepEqual(restorationFailures, []);
  }
} catch (error) { primary = error; }
finally {
  try { checkOriginals(); } catch { restorationFailures.push("final-originals"); }
  // Remove only the three owned copies; retained TAP/status records remain in this owned temp directory.
  for (const caseRow of manifest.cases) {
    try { rmSync(join(work, caseRow.id), { recursive: true, force: true }); } catch { restorationFailures.push(`${caseRow.id}:cleanup`); }
  }
  const result = { schema: 1, completed: !primary && restorationFailures.length === 0 && records.length === 10,
    cases: manifest.cases.map(value => value.id), records, restorationFailures, elapsedMs: Date.now() - started,
    originalSelectedInputsUnchanged: !restorationFailures.some(value => value.endsWith("originals")),
    originalUnitAndIntegrationExecution: "separate unchanged workflow steps", wholeA19Accepted: false };
  writeFileSync(join(work, "result.json"), JSON.stringify(result, null, 2) + "\n", { flag: "wx", mode: 0o600 });
  process.stdout.write(JSON.stringify(result) + "\n");
}
if (primary) throw primary;
assert.deepEqual(restorationFailures, []);
assert.equal(records.length, 10);
