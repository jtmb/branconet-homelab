import assert from 'node:assert/strict';
import { cp, mkdir, mkdtemp, readFile, realpath, lstat, rm, symlink, writeFile } from 'node:fs/promises';
import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';

// This wrapper only copies artifacts and starts the existing fixture. No app source changes.
const root = '/app', exchange = '/exchange';
const fixtureDeadline = Date.now() + 150000;
let work, fixture, closePromise;
let failure = false, orderlyStopRequested = false, outBytes = 0, errBytes = 0;
// PID1 must receive Docker stop directly so orderly fixture completion retains its literal exit.
// The external CI timeout and named-container cleanup remain the final process boundary.
const watchdog = setTimeout(() => { console.log('{"browserFixture":"deadline"}'); process.exit(1); }, 180000);
watchdog.unref();
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const sleep = (ms, unref = false) => new Promise(resolve => { const timer = setTimeout(resolve, ms); if (unref) timer.unref(); });
async function settled(ms) {
  return Promise.race([closePromise.then(() => true), sleep(ms, true).then(() => false)]);
}
async function fixtureExecutionDiagnostic(dir, deadline) {
  const result = { tmpMountRecords: 0, tmpNoexec: null, fakeFileRegular: false, fakeFileExecutable: false,
    spawnObserved: false, actualExit: null, spawnErrorClass: 0, errno: null, signalNumber: 0,
    stdoutBytes: 0, stderrBytes: 0, diagnosticFailed: false };
  try {
    const mounts = await readFile('/proc/self/mountinfo', 'utf8');
    if (Buffer.byteLength(mounts) > 1048576) throw Error('Diagnostic mount bound');
    const matches = mounts.split('\n').map(line => line.split(' ')).filter(fields => fields[4] === '/tmp');
    result.tmpMountRecords = matches.length;
    if (matches.length === 1) result.tmpNoexec = matches[0][5].split(',').includes('noexec');
    const fixtureDir = await realpath(dir);
    if (path.dirname(fixtureDir) !== await realpath(tmpdir()) || !path.basename(fixtureDir).startsWith('bortus-ui-test-')) throw Error('Diagnostic fixture scope');
    const bin = path.join(fixtureDir, 'fake-bin'), executable = path.join(bin, 'kubectl');
    const metadata = await lstat(executable);
    result.fakeFileRegular = metadata.isFile() && !metadata.isSymbolicLink();
    result.fakeFileExecutable = (metadata.mode & 0o111) !== 0;
    if (!result.fakeFileRegular) throw Error('Diagnostic executable scope');
    const remaining = Math.min(5000, deadline - Date.now());
    if (remaining <= 0) throw Error('Diagnostic original deadline');
    const child = spawnSync(executable, ['get', 'pods', '-A', '-o', 'json'], {
      env: { PATH: bin + path.delimiter + process.env.PATH, BORTUS_FAKE_KUBECTL: bin, HOME: '/tmp/bortus-ci-home', TMPDIR: '/tmp' },
      timeout: remaining, killSignal: 'SIGKILL', maxBuffer: 1048576,
    });
    result.spawnObserved = true;
    result.actualExit = Number.isInteger(child.status) && child.status >= 0 && child.status <= 255 ? child.status : null;
    // Fixed enum:0 none,1 EACCES,2 ENOENT,3 EPERM,4 ENOEXEC,5 ETIMEDOUT,6 ENOBUFS,7 other.
    const errors = { EACCES: 1, ENOENT: 2, EPERM: 3, ENOEXEC: 4, ETIMEDOUT: 5, ENOBUFS: 6 };
    result.spawnErrorClass = child.error ? (Object.hasOwn(errors, child.error.code) ? errors[child.error.code] : 7) : 0;
    result.errno = Number.isInteger(child.error?.errno) && child.error.errno >= -4096 && child.error.errno <= 0 ? child.error.errno : null;
    result.signalNumber = child.signal === null ? 0 : child.signal === 'SIGKILL' ? 9 : child.signal === 'SIGTERM' ? 15 : 1;
    result.stdoutBytes = child.stdout?.byteLength ?? 0; result.stderrBytes = child.stderr?.byteLength ?? 0;
  } catch { result.diagnosticFailed = true; }
  // Only fixed Booleans/enums/counts: never print command output, error bodies or paths.
  console.log(JSON.stringify({ fixtureExecutionDiagnostic: result }));
}
try {
  const pins = JSON.parse(await readFile(path.join(root, 'ci/browser-tools/provenance.json'), 'utf8'));
  for (const row of pins.fixtureFiles) assert.equal(sha(await readFile(path.join(root, row.path))), row.sha256);
  work = await mkdtemp(path.join(tmpdir(), 'bortus-ci-browser-'));
  await mkdir(path.join(work, '.next'));
  for (const rel of ['.next/standalone', '.next/static', 'public', 'prisma']) {
    await cp(path.join(root, rel), path.join(work, rel), { recursive: true, force: false, errorOnExist: true });
  }
  for (const rel of ['package.json', 'tsconfig.json', ...pins.fixtureFiles.map(row => row.path)]) {
    await mkdir(path.dirname(path.join(work, rel)), { recursive: true });
    await cp(path.join(root, rel), path.join(work, rel), { force: false, errorOnExist: true });
  }
  await symlink('/app/node_modules', path.join(work, 'node_modules'), 'dir');
  const env = {
    PATH: process.env.PATH, HOME: '/tmp/bortus-ci-home', TMPDIR: '/tmp', NEXT_TELEMETRY_DISABLED: '1',
    BORTUS_UI_PRODUCTION_ASSETS_FIXTURE: 'true', BORTUS_UI_NATIVE_FIXTURE: 'false',
    BORTUS_UI_KV_FIXTURE: 'false', BORTUS_UI_KV_GUARDED_FIXTURE: 'false', BORTUS_UI_FLUX_FIXTURE: 'false',
  };
  fixture = spawn(process.execPath, ['/app/node_modules/tsx/dist/cli.mjs', 'tests/ui-fixture.ts'], {
    cwd: work, env, stdio: ['pipe', 'pipe', 'pipe'],
  });
  closePromise = new Promise(resolve => fixture.once('close', (code, signal) => resolve([code, signal])));
  fixture.once('error', () => { failure = true; });
  fixture.stdin.on('error', () => { failure = true; });
  let pending = '', ready = false, closing = false;
  fixture.stdout.on('data', chunk => {
    outBytes += chunk.length;
    if (outBytes > 1048576) { failure = true; fixture.kill('SIGTERM'); return; }
    pending = (pending + chunk.toString()).slice(-65536);
  });
  fixture.stderr.on('data', chunk => {
    errBytes += chunk.length;
    if (errBytes > 1048576) { failure = true; fixture.kill('SIGTERM'); }
  });
  // No response bodies, credentials, fixture output or browser errors enter CI logs.
  const deadline = Math.min(Date.now() + 45000, fixtureDeadline);
  while (Date.now() < deadline) {
    assert.equal(fixture.exitCode, null);
    assert.equal(fixture.signalCode, null);
    assert.equal(failure, false);
    const match = /(?:^|\n)UI_FIXTURE_READY (\{[^\n]+\})/.exec(pending);
    if (match) {
      const state = JSON.parse(match[1]), url = new URL(state.writerUrl);
      assert.equal(url.protocol, 'http:'); assert.equal(url.hostname, '127.0.0.1');
      assert.equal(url.pathname, '/'); assert.equal(url.search, ''); assert.equal(url.hash, '');
      assert.equal(url.username, ''); assert.equal(url.password, ''); assert.match(url.port, /^\d+$/);
      await fixtureExecutionDiagnostic(state.dir, deadline);
      await writeFile(path.join(exchange, 'ready.json'), JSON.stringify({ schema: 1, writerUrl: url.origin }) + '\n', { flag: 'wx', mode: 0o600 });
      ready = true; break;
    }
    await sleep(100);
  }
  assert.equal(ready, true);
  const stop = () => { orderlyStopRequested = true; closing = true; };
  process.once('SIGTERM', stop); process.once('SIGINT', stop);
  const activeDeadline = Math.min(Date.now() + 105000, fixtureDeadline);
  while (!closing && Date.now() < activeDeadline) {
    assert.equal(fixture.exitCode, null); assert.equal(fixture.signalCode, null); assert.equal(failure, false);
    await sleep(100);
  }
  assert.equal(closing, true);
} catch (error) {
  failure = true;
  console.log(JSON.stringify({ browserFixture: 'refused', errorType: error?.name === 'AssertionError' ? 'AssertionError' : 'Error' }));
} finally {
  if (fixture) {
    if (fixture.exitCode === null && fixture.signalCode === null) {
      try { fixture.stdin.end('stop\n'); } catch { failure = true; }
      if (!await settled(10000)) {
        failure = true; try { fixture.kill('SIGTERM'); } catch { /* outer container cleanup remains authoritative */ }
        if (!await settled(5000)) { try { fixture.kill('SIGKILL'); } catch { /* same owned container */ } await settled(5000); }
      }
    }
    const [code, signal] = await Promise.race([closePromise, sleep(100, true).then(() => [null, 'unsettled'])]);
    if (code !== 0 || signal !== null) failure = true;
  }
  if (work) {
    try {
      assert.equal(path.dirname(await realpath(work)), await realpath(tmpdir()));
      assert.equal(path.basename(work).startsWith('bortus-ci-browser-'), true);
      await rm(work, { recursive: true, force: false });
    } catch { failure = true; }
  }
  console.log(JSON.stringify({ browserFixtureClosed: !failure, orderlyStopRequested, fixtureStdoutBytes: outBytes, fixtureStderrBytes: errBytes }));
  clearTimeout(watchdog);
  process.exitCode = failure ? 1 : 0;
}
