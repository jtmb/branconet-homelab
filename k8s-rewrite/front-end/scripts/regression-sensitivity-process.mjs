import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, symlinkSync, rmSync, lstatSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), ".."), sha = bytes => createHash("sha256").update(bytes).digest("hex");
const manifest = JSON.parse(readFileSync(new URL("./regression-sensitivity-process.json", import.meta.url), "utf8"));
const started = Date.now(), deadline = started + 240000, reserveMs = 20000, outputLimit = 1048576;
assert.equal(manifest.schema, 1); assert.equal(manifest.id, "A01-SQL-writer-lock"); assert.equal(manifest.files.length, 19);
const originals = new Map(), retained = new Map();
for (const row of manifest.files) {
  assert.ok(!originals.has(row.path) && !row.path.includes("\\") && !row.path.startsWith("/") && !row.path.split("/").includes(".."));
  assert.ok(["src/lib/account-store.ts", "src/lib/account-change-queue.ts", "package.json", "tsconfig.json", "tests/fixtures/account-lock.sensitivity.ts", "tests/fixtures/account-lock-participant.cjs", "prisma/schema.prisma", "prisma/migrations/migration_lock.toml"].includes(row.path) || /^prisma\/migrations\/\d{14}_[a-z_]+\/migration\.sql$/.test(row.path));
  const metadata = lstatSync(join(root, row.path)); assert.ok(metadata.isFile() && !metadata.isSymbolicLink());
  const bytes = readFileSync(join(root, row.path)); assert.equal(sha(bytes), row.sha256); originals.set(row.path, bytes);
}
assert.deepEqual(manifest.unchanged.map(row => row.path).sort(), ["scripts/regression-sensitivity-db.json", "scripts/regression-sensitivity-db.mjs", "scripts/regression-sensitivity.json", "scripts/regression-sensitivity.mjs", "tests/account-process.test.ts", "tests/fixtures/account-process.cjs"]);
for (const row of manifest.unchanged) { const bytes = readFileSync(join(root, row.path)); assert.equal(sha(bytes), row.sha256); retained.set(row.path, bytes); }
const loader = import.meta.resolve("tsx"), work = mkdtempSync(join(tmpdir(), "bortus-process-sensitivity-"));
const copy = join(work, "A01-SQL-writer-lock"), records = [], restorationFailures = [];
let primary;
function checkOriginals() {
  for (const [path, bytes] of [...originals, ...retained]) assert.ok(readFileSync(join(root, path)).equals(bytes), `Original changed: ${path}`);
}
function proof(out, marker) {
  const rows = [...out.matchAll(new RegExp(`^(?:# )?${marker} (\\{[^\\n]+\\})$`, "gm"))]; assert.equal(rows.length, 1);
  return JSON.parse(rows[0][1]);
}
function run(phase) {
  const timeout = Math.min(30000, deadline - Date.now() - reserveMs); assert.ok(timeout > 0, "Process sensitivity deadline exhausted");
  const env = { ...process.env, NODE_OPTIONS: "", NO_COLOR: "1" }; delete env.FORCE_COLOR;
  const child = spawnSync(process.execPath, ["--import", loader, "--test", "--experimental-test-isolation=none", "--test-reporter=tap", manifest.testFile], {
    cwd: copy, env, timeout, killSignal: "SIGKILL", maxBuffer: outputLimit, encoding: "utf8", windowsHide: true,
  });
  const out = child.stdout || "", err = child.stderr || "";
  const record = { phase, actualExit: child.status, signal: child.signal, spawnErrorCode: child.error?.code || null,
    stdoutSHA256: sha(out), stderrSHA256: sha(err), stdoutBytes: Buffer.byteLength(out), stderrBytes: Buffer.byteLength(err) };
  records.push(record);
  for (const [suffix, bytes] of [["tap", out], ["stderr", err], ["json", JSON.stringify(record, null, 2) + "\n"]]) writeFileSync(join(work, `${phase}.${suffix}`), bytes, { flag: "wx", mode: 0o600 });
  process.stdout.write(`\n# A01-SQL-writer-lock-${phase}\n${out}`); if (err) process.stderr.write(err);
  assert.ok(!child.error && child.signal === null, "Child deadline/spawn/output failure");
  assert.ok(Buffer.byteLength(out) <= outputLimit && Buffer.byteLength(err) <= outputLimit);
  const warning = `(node:${child.pid}) ExperimentalWarning: SQLite is an experimental feature and might change at any time\n` + "(Use `node --trace-warnings ...` to show where the warning was created)\n";
  assert.equal(err, warning, "Unexpected stderr; exactly the retained Node22 SQLite warning is required");
  assert.equal(child.status, phase === "pristine" ? 0 : 1);
  const successes = [...out.matchAll(/^ok \d+ - (.+)$/gm)].map(row => row[1]), failures = [...out.matchAll(/^not ok \d+ - (.+)$/gm)].map(row => row[1]);
  assert.deepEqual(successes, phase === "pristine" ? [manifest.testName] : []); assert.deepEqual(failures, phase === "mutant" ? [manifest.testName] : []);
  for (const [name, value] of [["tests", 1], ["pass", phase === "pristine" ? 1 : 0], ["fail", phase === "pristine" ? 0 : 1], ["cancelled", 0], ["skipped", 0], ["todo", 0]]) assert.match(out, new RegExp(`^# ${name} ${value}$`, "m"));
  const observed = proof(out, "A01_LOCK_PROOF"), cleanup = proof(out, "A01_LOCK_CLEANUP");
  assert.deepEqual(cleanup, { failures: [], twoParticipants: true, bothReportedExit: true });
  assert.equal(observed.schema, 1); assert.equal(observed.firstCount, 2); assert.equal(observed.distinctParticipantProcesses, true); assert.deepEqual(observed.participantExits, [0, 0]);
  if (phase === "pristine") {
    assert.equal(observed.acquired, false); assert.equal(observed.busyCode, 5); assert.equal(observed.secondCount, null); assert.deepEqual(observed.countCalls, [1, 0]);
    assert.equal(observed.outcomes[0].success, true); assert.equal(observed.outcomes[1].success, false); assert.ok([401, 403].includes(observed.outcomes[1].status));
    assert.equal(observed.writers, 1); assert.equal(observed.administrators, 1);
  } else {
    assert.equal(observed.acquired, true); assert.equal(observed.busyCode, null); assert.equal(observed.secondCount, 2); assert.deepEqual(observed.countCalls, [1, 1]);
    assert.deepEqual(observed.outcomes, [{ success: true, status: null }, { success: true, status: null }]); assert.equal(observed.writers, 0); assert.equal(observed.administrators, 0);
    for (const literal of ["failureType: 'testCodeFailure'", "code: 'ERR_ASSERTION'", "name: 'AssertionError'", "operator: 'strictEqual'", "expected: 1", "actual: 2"]) assert.ok(out.includes(literal), "Wrong invariant assertion");
    assert.match(out, new RegExp(`account-lock\\.sensitivity\\.ts:${manifest.assertionLine}:\\d+`));
  }
  record.lockProof = observed; record.cleanupProof = cleanup;
}
try {
  mkdirSync(copy, { mode: 0o700 });
  for (const [path, bytes] of originals) { mkdirSync(dirname(join(copy, path)), { recursive: true, mode: 0o700 }); writeFileSync(join(copy, path), bytes, { flag: "wx", mode: 0o600 }); }
  symlinkSync(join(root, "node_modules"), join(copy, "node_modules"), "dir");
  const sourcePath = join(copy, manifest.source), before = originals.get(manifest.source); assert.ok(before);
  try {
    run("pristine");
    const text = before.toString("utf8"); assert.equal(text.split(manifest.before).length - 1, 1);
    const mutant = Buffer.from(text.replace(manifest.before, manifest.after)); assert.equal(sha(mutant), manifest.mutantSHA256);
    writeFileSync(sourcePath, mutant); run("mutant");
  } finally {
    try { writeFileSync(sourcePath, before); } catch { restorationFailures.push("restore"); }
    for (const [path, bytes] of originals) { try { assert.ok(readFileSync(join(copy, path)).equals(bytes)); } catch { restorationFailures.push(path); } }
    try { checkOriginals(); } catch { restorationFailures.push("originals"); }
  }
} catch (error) { primary = error; }
finally {
  try { checkOriginals(); } catch { restorationFailures.push("final-originals"); }
  try { rmSync(copy, { recursive: true, force: true }); } catch { restorationFailures.push("cleanup"); }
  const result = { schema: 1, completed: !primary && !restorationFailures.length && records.length === 2, id: manifest.id, records, restorationFailures,
    elapsedMs: Date.now() - started, originalSelectedInputsUnchanged: !restorationFailures.some(value => value.endsWith("originals")),
    existingSixRacesAndSevenSensitivityControlsUnchanged: true, wholeA19Accepted: false, crossProcessSensitivityScope: "One deterministic cross-demotion SQL-lock control only" };
  writeFileSync(join(work, "result.json"), JSON.stringify(result, null, 2) + "\n", { flag: "wx", mode: 0o600 }); process.stdout.write(JSON.stringify(result) + "\n");
}
if (primary) throw primary;
assert.deepEqual(restorationFailures, []); assert.equal(records.length, 2);
