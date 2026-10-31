// Source preparation only. Derived from the retained provisioning-output focused runner.
const fs = require('node:fs'), path = require('node:path'), cp = require('node:child_process'), crypto = require('node:crypto'), assert = require('node:assert/strict');
process.umask(0o077);
const mode = process.argv[2], manifest = JSON.parse(fs.readFileSync('/producer/manifest.json', 'utf8'));
const mutations = JSON.parse(fs.readFileSync('/producer/mutations.json', 'utf8'));
const expected = JSON.parse(fs.readFileSync('/producer/expectations.json', 'utf8'))[mode];
assert(expected, 'Unknown focused mode');
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const dir = fs.mkdtempSync('/tmp/configuration-json-'), originals = new Map(), failures = [];
let record, primary = null;
const write = (suffix, value) => fs.writeFileSync('/output/' + mode + suffix, value, { flag: 'wx', mode: 0o600 });
try {
  for (const row of manifest) {
    assert(!path.isAbsolute(row.path) && !row.path.split('/').includes('..'));
    const bytes = fs.readFileSync('/source/' + row.path); assert.equal(sha(bytes), row.sha256);
    const target = path.join(dir, row.path); fs.mkdirSync(path.dirname(target), { recursive: true, mode: 0o700 });
    fs.writeFileSync(target, bytes, { flag: 'wx', mode: 0o600 }); originals.set(row.path, bytes);
  }
  fs.symlinkSync('/deps/node_modules', path.join(dir, 'node_modules'), 'dir');
  const mutation = mutations[mode];
  if (mutation) {
    const target = path.join(dir, mutation.path), before = fs.readFileSync(target, 'utf8');
    assert.equal(sha(before), mutation.originalSHA256); assert.equal(before.split(mutation.before).length - 1, 1);
    const after = before.replace(mutation.before, mutation.after); assert.equal(sha(after), mutation.mutantSHA256);
    fs.writeFileSync(target, after);
  }
  const args = ['--import', 'tsx', '--test', '--experimental-test-isolation=none', '--test-reporter=tap', 'tests/request-json-response.test.ts'];
  const child = cp.spawnSync(process.execPath, args, { cwd: dir, env: process.env, encoding: 'utf8', timeout: 30000, maxBuffer: 1048576, killSignal: 'SIGKILL' });
  const out = child.stdout || '', err = child.stderr || '';
  record = { mode, status: child.status, signal: child.signal, errorCode: child.error?.code || null,
    stdoutBytes: Buffer.byteLength(out), stderrBytes: Buffer.byteLength(err), stdoutSHA256: sha(out), stderrSHA256: sha(err),
    testSHA256: sha(fs.readFileSync(path.join(dir, 'tests/request-json-response.test.ts'))),
    sourceMutation: mutation ? { path: mutation.path, mutantSHA256: mutation.mutantSHA256 } : null };
  write('.stdout', out); write('.stderr', err); write('-status.json', JSON.stringify(record, null, 2) + '\n');
  assert(!child.error && child.signal === null, 'Child timeout/spawn/output failure'); assert.equal(err, '', 'Unexpected test stderr');
  const failed = [...out.matchAll(/^not ok \d+ - (.+)$/gm)].map(match => match[1]);
  const passed = [...out.matchAll(/^ok \d+ - (.+)$/gm)].map(match => match[1]);
  assert.equal(child.status, expected.exit); assert.deepEqual(failed, expected.failures.map(row => row.name));
  assert.equal(passed.length, 5 - expected.failures.length);
  for (const [label, count] of [['tests', 5], ['pass', passed.length], ['fail', failed.length], ['cancelled', 0], ['skipped', 0], ['todo', 0]])
    assert.match(out, new RegExp('^# ' + label + ' ' + count + '$', 'm'));
  for (const witness of expected.failures) {
    const start = out.indexOf(' - ' + witness.name + '\n'); assert(start >= 0);
    const rest = out.slice(start), boundary = rest.slice(1).search(/\n(?:ok|not ok) \d+ - /);
    const block = boundary < 0 ? rest : rest.slice(0, boundary + 1);
    assert(block.includes("failureType: 'testCodeFailure'")); assert(block.includes("code: 'ERR_ASSERTION'"));
    assert(block.includes("name: 'AssertionError'")); assert(block.includes("operator: '" + witness.operator + "'"));
    assert.match(block, new RegExp('request-json-response\\.test\\.ts:' + witness.line + ':\\d+'));
  }
} catch (error) { primary = { name: error.name, code: error.code || null }; }
finally {
  for (const [relative, bytes] of originals) {
    try { fs.writeFileSync(path.join(dir, relative), bytes); assert(fs.readFileSync(path.join(dir, relative)).equals(bytes)); }
    catch { failures.push('restore:' + relative); }
    try { assert(fs.readFileSync('/source/' + relative).equals(bytes)); } catch { failures.push('source:' + relative); }
  }
  try { assert(path.dirname(dir) === '/tmp' && path.basename(dir).startsWith('configuration-json-')); fs.rmSync(dir, { recursive: true }); }
  catch { failures.push('cleanup'); }
  write('-complete.json', JSON.stringify({ mode, record, runnerError: primary, restorationFailures: failures,
    sourceUnchanged: failures.length === 0, noOldCorpus: true, browserEvidence: false }, null, 2) + '\n');
}
console.log(JSON.stringify({ mode, record, runnerError: primary, restorationFailures: failures }));
if (primary || failures.length) process.exitCode = 1;
