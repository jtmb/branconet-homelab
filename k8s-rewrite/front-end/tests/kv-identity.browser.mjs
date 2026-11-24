import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { once } from 'node:events';
import { mkdtemp, readFile } from 'node:fs/promises';
import { writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const require = createRequire(import.meta.url), { chromium } = require(process.argv[2]);
const report = '../../docs/implementation-evidence/kv-identity-browser.json';
const evidence = { startedAt: new Date().toISOString(), scope: 'Actual production /secrets/kv; disposable SQLite and CA-verified synthetic native API only', checks: [], failures: [], terminal: false };
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
async function until(check, message, timeout = 25000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { if (await check()) return; await pause(100); }
  throw Error(message);
}
function mark(name, metadata = {}) {
  evidence.checks.push({ name, ...metadata });
  writeFileSync(report.replace('.json', '-progress.json'), JSON.stringify({ ...evidence, checkpointAt: new Date().toISOString() }, null, 2) + '\n');
  console.log('BROWSER_CHECK ' + name);
}
const fixture = spawn(process.execPath, ['node_modules/tsx/dist/cli.mjs', 'tests/kv-administration-ui-fixture.ts', '--integrated'], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
evidence.ownedProcesses = { fixturePid: fixture.pid };
let state, browser, chrome, page, destroyPayload;
const ready = new Promise((resolve, reject) => {
  let output = ''; const timer = setTimeout(() => reject(Error('Fixture startup timed out')), 45000);
  fixture.once('exit', () => { clearTimeout(timer); reject(Error('Fixture exited before readiness')); });
  fixture.stdout.on('data', chunk => { output = (output + chunk).slice(-65536); const match = output.match(/ADMIN_UI_FIXTURE_READY (\{[^\n]+\})/); if (match) { clearTimeout(timer); resolve(JSON.parse(match[1])); } });
  fixture.stderr.on('data', () => {});
});
const api = async path => {
  const response = await fetch(new URL(path, state.browserUrl), { signal: AbortSignal.timeout(20000) });
  assert.equal(response.status, 200); return response.json();
};
const control = async action => {
  const response = await fetch(new URL('/__fixture/control', state.browserUrl), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }), signal: AbortSignal.timeout(20000) });
  assert.equal(response.status, 204);
};
const section = () => page.getByRole('region', { name: 'BORTUS KV engine administration' });
const history = () => section().getByRole('group', { name: 'History administration' });
const box = name => history().getByRole('heading', { name, exact: true }).locator('..');
async function openHistory() {
  if (!(await section().count())) await page.getByRole('button', { name: 'Administration and audit', exact: true }).click();
  await section().getByRole('button', { name: 'History & recovery', exact: true }).click();
  await history().waitFor();
  await until(async () => await box('Permanently destroy committed versions').getByRole('checkbox').count() > 0, 'History identities unavailable');
}
async function selectHistory(version) {
  const target = box('Permanently destroy committed versions');
  await target.getByRole('checkbox', { name: new RegExp('^Version ' + version + ' ·') }).check();
  await target.getByLabel('Exact confirmation', { exact: true }).fill(await target.locator('code').innerText());
  return target;
}
try {
  state = await ready;
  const profile = await mkdtemp(join(tmpdir(), 'bortus-kv-identity-chrome-'));
  chrome = spawn(process.argv[3], ['--remote-debugging-port=0', '--user-data-dir=' + profile, '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-backgrounding-occluded-windows', '--disable-features=CalculateNativeWinOcclusion', 'about:blank'], { windowsHide: true, stdio: 'ignore' });
  evidence.ownedProcesses.chromePid = chrome.pid;
  let port;
  await until(async () => { try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; return !!port; } catch { return false; } }, 'Owned Chrome startup failed', 15000);
  browser = await chromium.connectOverCDP('http://127.0.0.1:' + port, { noDefaults: true });
  const context = browser.contexts()[0]; page = context.pages()[0];
  page.on('request', request => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/kv/paths/' + state.pathId + '/destroy') destroyPayload = request.postDataJSON();
  });
  await page.addInitScript(() => { window.__identityVisibility = []; document.addEventListener('visibilitychange', () => window.__identityVisibility.push(document.visibilityState)); });
  await page.goto(state.browserUrl); await page.bringToFront();
  await page.getByRole('button', { name: 'Open KV path apps/service/credentials', exact: true }).click();
  await openHistory();
  const route = '/api/kv/paths/' + state.pathId;
  const native = await api(route + '/status'), versions = await api(route + '/versions');
  assert.equal(versions.uid, native.uid); assert.equal(versions.head, native.head);
  const selected = versions.items.find(item => item.version === 2);
  assert(selected && selected.name && selected.uid);
  assert((await section().innerText()).includes('canonical UID ' + native.uid));
  assert((await box('Permanently destroy committed versions').innerText()).includes(selected.name));
  assert((await box('Permanently destroy committed versions').innerText()).includes('UID ' + selected.uid));
  const bounds = [];
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 900 });
    const measured = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
    evidence.sidebarAtResize = await page.locator('aside').evaluate(element => ({ width: element.getBoundingClientRect().width, transitionProperty: getComputedStyle(element).transitionProperty, transitionDuration: getComputedStyle(element).transitionDuration }));
    evidence.layoutBounds = [...bounds, measured];
    if (measured.scroll > measured.width) evidence.layoutOverflow = await page.evaluate(() => [...document.querySelectorAll('main *')].map(element => ({ tag: element.tagName.toLowerCase(), classes: element.className, width: element.getBoundingClientRect().width, right: element.getBoundingClientRect().right, minWidth: getComputedStyle(element).minWidth, overflowWrap: getComputedStyle(element).overflowWrap })).filter(item => item.right > document.documentElement.clientWidth).slice(0, 24));
    assert(measured.scroll <= measured.width, 'UID metadata exceeds document width'); bounds.push(measured);
  }
  mark('Canonical and committed-history identities display exactly and fit320/390/768', { bounds, versions: versions.items.length });
  const beforeHidden = await api('/__fixture/status');
  await selectHistory(2);
  const session = await context.newCDPSession(page), { windowId } = await session.send('Browser.getWindowForTarget');
  await session.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'minimized' } });
  await until(async () => await page.evaluate(() => document.visibilityState) === 'hidden', 'Real hidden visibility unavailable', 5000);
  await until(async () => await section().count() === 0, 'Hidden page retained administration capture');
  await session.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'normal' } }); await page.bringToFront();
  await until(async () => await page.evaluate(() => document.visibilityState) === 'visible', 'Visibility restoration unavailable');
  await openHistory();
  assert.equal(await box('Permanently destroy committed versions').getByRole('checkbox').evaluateAll(items => items.filter(item => item.checked).length), 0);
  assert.equal(await box('Permanently destroy committed versions').getByLabel('Exact confirmation').inputValue(), '');
  assert.equal((await api('/__fixture/status')).nativeWrites, beforeHidden.nativeWrites);
  mark('Real hiding clears selected destructive capture without write or restoration');
  await selectHistory(2); const beforeWithdrawal = await api('/__fixture/status');
  await control('withdraw-admin');
  await until(async () => await section().getByRole('button', { name: 'History & recovery', exact: true }).count() === 0, 'Fresh administrator withdrawal retained management');
  assert.equal(await page.getByRole('button', { name: 'Destroy selected versions once', exact: true }).count(), 0);
  assert.equal((await api('/__fixture/status')).nativeWrites, beforeWithdrawal.nativeWrites);
  await control('restore-admin');
  await until(async () => await section().getByRole('button', { name: 'History & recovery', exact: true }).count() === 1, 'Administrator did not refresh');
  await openHistory();
  assert.equal(await box('Permanently destroy committed versions').getByLabel('Exact confirmation').inputValue(), '');
  mark('Fresh administrator withdrawal discards destructive intent and requires new capture without write');
  const target = await selectHistory(2);
  await target.getByRole('button', { name: 'Destroy selected versions once', exact: true }).click();
  await until(async () => (await api(route + '/versions')).items.every(item => item.version !== 2), 'Selected reference was not detached');
  assert.equal(destroyPayload.sourceUid, native.uid);
  assert.deepEqual(destroyPayload.histories, [{ version: 2, name: selected.name, uid: selected.uid }]);
  assert.deepEqual(destroyPayload.versions, [2]);
  assert.equal(destroyPayload.pathRevision, (await api(route)).revision);
  const after = await api(route + '/status'); assert.equal(after.uid, native.uid); assert.equal(after.head, 3);
  assert((await history().innerText()).includes('deleted'));
  mark('Single explicit destroy sends displayed UID tuple and removes only selected history, preserving canonical identity/head');
  await section().getByRole('button', { name: 'Capture fresh path metadata', exact: true }).click();
  await history().waitFor();
  const orphan = box('Aged orphan history cleanup');
  await orphan.getByRole('button', { name: 'Preview aged orphan GC', exact: true }).click();
  await until(async () => await orphan.getByRole('checkbox').count() > 0, 'Aged synthetic orphan preview unavailable');
  assert((await orphan.innerText()).includes('24'));
  await orphan.getByRole('checkbox').first().check();
  await orphan.getByLabel('Exact confirmation').fill(await orphan.locator('code').last().innerText());
  await orphan.getByRole('button', { name: 'Delete exactly selected orphan histories', exact: true }).click();
  await until(async () => (await history().innerText()).includes('deleted'), 'Explicit GC result unavailable');
  assert.equal((await api(route + '/status')).uid, native.uid);
  mark('Explicit aged-orphan preview and UID/RV-selected GC preserves canonical object');
  await section().getByRole('button', { name: 'Capture fresh path metadata', exact: true }).click();
  await history().waitFor();
  const retention = box('Committed-version retention'), beforeRetention = await api('/__fixture/status');
  await retention.getByLabel('Retention limit', { exact: true }).fill('3');
  await retention.getByLabel('Exact confirmation').fill(await retention.locator('code').innerText());
  await retention.getByRole('button', { name: 'Commit retention revision', exact: true }).click();
  await until(async () => (await api(route)).retention === 3, 'Captured retention revision was not committed');
  assert.equal((await api('/__fixture/status')).nativeWrites, beforeRetention.nativeWrites);
  mark('Explicit retention revision commits metadata only without immediate history deletion');
  await section().getByRole('button', { name: 'Capture fresh path metadata', exact: true }).click();
  await history().waitFor();
  const recovery = box('Inspect ambiguous operation / recovery'), beforeRecovery = await api('/__fixture/status');
  await recovery.getByLabel('Exact operation UUID').fill(state.ambiguousOperationId);
  await recovery.getByLabel('Exact confirmation').fill('inspect operation ' + state.ambiguousOperationId);
  await recovery.getByRole('button', { name: 'Inspect operation metadata', exact: true }).click();
  await until(async () => await recovery.locator('dd').filter({ hasText: 'ambiguous' }).count() > 0, 'Missing-proof operation did not remain ambiguous');
  assert.equal((await api('/__fixture/status')).nativeWrites, beforeRecovery.nativeWrites);
  mark('Absent native recovery proof remains ambiguous without regenerated value or mutation');
  await page.setViewportSize({ width: 390, height: 900 });
  assert.equal(await page.locator('textarea').count(), 0, 'Metadata screenshot contains private value or token editor');
  await page.screenshot({ path: '../../docs/implementation-evidence/kv-identity-browser-mobile.png' });
  if (process.argv[4]) {
    const hash = createHash('sha256').update(await readFile(process.argv[4])).digest('hex');
    assert.equal(hash, '20c09fe157a8a34a30e241aaa1fcdade657734f08ab379ecfbeb7d45cc46e878');
    await page.addScriptTag({ path: process.argv[4] });
    evidence.accessibilityScan = await page.evaluate(async () => {
      const result = await window.axe.run(document.querySelector('#kv-administration-panel'));
      const safe = item => ({ id: item.id, impact: item.impact, help: item.help, helpUrl: item.helpUrl, targets: item.nodes.map(node => node.target) });
      return { version: result.testEngine.version, violations: result.violations.map(safe), incomplete: result.incomplete.map(safe), passes: result.passes.map(item => item.id) };
    });
    evidence.scanner = { name: 'axe-core', version: '4.14.0', sha256: hash, scope: 'Metadata-only History/recovery administration panel390CSSpixels; no raw node HTML/private attributes persisted' };
  }
  await session.detach();
} catch (error) {
  evidence.failures.push(error instanceof Error ? error.message.split('\n')[0] : 'Actual browser qualification failed'); process.exitCode = 1;
} finally {
  if (browser) { try { const shutdown = await browser.newBrowserCDPSession(); await shutdown.send('Browser.close'); } catch { /* A successful close can disconnect first. */ } await browser.close().catch(() => {}); }
  if (chrome?.exitCode === null && chrome.signalCode === null) await Promise.race([once(chrome, 'exit'), pause(15000)]);
  if (fixture.exitCode === null && fixture.signalCode === null) { fixture.stdin.write('stop\n'); await Promise.race([once(fixture, 'exit'), pause(30000)]); }
  evidence.cleanup = { chromeExitCode: chrome?.exitCode, chromeSignal: chrome?.signalCode, fixtureExitCode: fixture.exitCode, fixtureSignal: fixture.signalCode };
  if (chrome?.exitCode === null || fixture.exitCode === null && fixture.signalCode === null) { evidence.failures.push('Owned process failed normal cleanup'); process.exitCode = 1; }
  evidence.completedAt = new Date().toISOString(); evidence.terminal = true;
  writeFileSync(report, JSON.stringify(evidence, null, 2) + '\n');
  console.log(JSON.stringify({ checks: evidence.checks.length, failures: evidence.failures, cleanup: evidence.cleanup }));
}
