// Actual production route plus disposable SQLite/verified native TLS fixture.
// Run after build: node tests/shared-freshness.browser.mjs <absolute playwright package> <Chrome executable>
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { writeFile, mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
const require = createRequire(import.meta.url);
const { chromium } = require(process.argv[2]);
const id = '20000000-0000-4000-8000-000000000000';
const capabilityKey = `GET /api/kv/paths/${id}/capabilities`;
const evidence = { fixture: 'Actual built /secrets/kv route; disposable SQLite and CA-verified native TLS API', node: process.version, checks: [], failures: [], source: 'da84f0f archive plus exact recovered six handoff source files; no application behavior changes', limitations: ['Local synthetic browser evidence; no live API/RBAC/admission/image acceptance', 'Not a controlled latency or CPU benchmark'], cleanup: {} };
const fixture = spawn(process.execPath, ['node_modules/tsx/dist/cli.mjs', 'tests/ui-fixture.ts'], { env: { ...process.env, BORTUS_UI_NATIVE_FIXTURE: 'true', BORTUS_UI_KV_FIXTURE: 'true', BORTUS_UI_KV_GUARDED_FIXTURE: 'true' }, stdio: ['pipe', 'pipe', 'pipe'] });
let browser, fixtureState, chrome;
const mark = (name, metadata = {}) => { evidence.checks.push({ name, ...metadata }); console.log('BROWSER_CHECK ' + name); };
const ready = new Promise((resolve, reject) => {
  let output = ''; const timeout = setTimeout(() => reject(Error('Fixture startup timed out')), 45000);
  fixture.once('exit', () => { clearTimeout(timeout); reject(Error('Fixture exited before startup')); });
  fixture.stdout.on('data', chunk => {
    output = (output + chunk).slice(-65536); const match = output.match(/UI_FIXTURE_READY (\{[^\n]+\})/);
    if (match) { clearTimeout(timeout); resolve(JSON.parse(match[1])); }
  });
  fixture.stderr.on('data', () => {}); // Never copy arbitrary server output into browser evidence.
});
async function until(check, message, timeout = 22000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) { if (await check()) return; await new Promise(resolve => setTimeout(resolve, 100)); }
  throw Error(message);
}
async function status(base) { return (await fetch(base + '/__fixture/status')).json(); }
async function control(base, action) { const result = await fetch(base + '/__fixture/native-control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) }); assert.ok(result.status === 204, 'Fixture control failed'); }
async function open(page, base) {
  await page.goto(base + '/secrets/kv');
  await page.getByRole('button', { name: 'Open KV path services/api', exact: true }).click();
  await page.getByRole('button', { name: 'Values and versions', exact: true }).waitFor({ state: 'visible' });
  await until(async () => !await page.getByRole('button', { name: 'Values and versions', exact: true }).isDisabled(), 'Capabilities not ready');
}
const dialog = page => page.getByRole('dialog');
async function editor(page) {
  await dialog(page).getByRole('button', { name: 'Edit grouped fields', exact: true }).click();
  await page.getByLabel('Value for __proto__', { exact: true }).waitFor();
  await page.getByLabel('Value for __proto__', { exact: true }).fill('synthetic unsaved browser draft');
}
try {
  fixtureState = await ready;
  // Default Playwright focus emulation forces visible even when minimized.
  // Use its supported CDP noDefaults option on a fresh, disposable profile.
  const profile = await mkdtemp(join(tmpdir(), 'bortus-freshness-chrome-'));
  chrome = spawn(process.argv[3], ['--remote-debugging-port=0', '--user-data-dir=' + profile, '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-backgrounding-occluded-windows', '--disable-features=CalculateNativeWinOcclusion', 'about:blank'], { windowsHide: true, stdio: 'ignore' });
  let port;
  await until(async () => { try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; return !!port; } catch { return false; } }, 'Owned Chrome CDP startup timed out', 15000);
  browser = await chromium.connectOverCDP('http://127.0.0.1:' + port, { noDefaults: true });
  const context = browser.contexts()[0];
  const page = context.pages()[0];
  await page.setViewportSize({ width: 390, height: 900 });
  await page.bringToFront();
  await page.addInitScript(() => { window.__bortusVisibility = []; document.addEventListener('visibilitychange', () => window.__bortusVisibility.push({ state: document.visibilityState, at: Date.now() })); });
  let lastCapabilitiesCompleted = 0;
  page.on('response', response => {
    if (new URL(response.url()).pathname === `/api/kv/paths/${id}/capabilities`) void response.finished().then(error => { if (!error && response.ok()) lastCapabilitiesCompleted = Date.now(); });
  });
  await open(page, fixtureState.writerUrl);
  const beforeOpen = await status(fixtureState.writerUrl);
  await page.getByRole('button', { name: 'Values and versions', exact: true }).click();
  await dialog(page).getByRole('button', { name: 'Preview explicit adoption', exact: true }).waitFor();
  const afterOpen = await status(fixtureState.writerUrl);
  assert.ok(afterOpen.requests[capabilityKey] === beforeOpen.requests[capabilityKey], 'Workbench started duplicate capability request');
  assert.ok(afterOpen.valueRequests === 0, 'Metadata browsing requested values');
  mark('Parent and workbench share capability GET; opening fetches no values', { capabilityReadsBefore: beforeOpen.requests[capabilityKey], capabilityReadsAfter: afterOpen.requests[capabilityKey] });
  await dialog(page).getByRole('button', { name: 'Preview explicit adoption', exact: true }).click();
  await page.getByLabel('Type exact logical path: services/api').fill('services/api');
  await page.getByLabel('I reviewed the mapped fields and all affected aliases; preserve the originals and create immutable version 1.').check();
  await dialog(page).getByRole('button', { name: 'Confirm adoption', exact: true }).click();
  await page.getByText('Operation committed. Refresh metadata to inspect the new head.').waitFor();
  await dialog(page).getByRole('button', { name: 'Refresh metadata', exact: true }).click();
  await dialog(page).getByRole('button', { name: 'Edit grouped fields', exact: true }).waitFor();
  await editor(page);
  const captureBefore = await dialog(page).getByText(/^Captured head /).textContent();
  const pollingStart = await status(fixtureState.writerUrl);
  const completionBeforePoll = lastCapabilitiesCompleted;
  await until(async () => (await status(fixtureState.writerUrl)).requests[capabilityKey] > pollingStart.requests[capabilityKey], 'Capability poll missing');
  await until(async () => lastCapabilitiesCompleted > completionBeforePoll, 'Capability poll response did not complete');
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await until(async () => !await dialog(page).getByText('Checking fresh permissions. Value controls are paused.').count(), 'Equivalent refresh stayed stale');
  evidence.visibilityBeforeDraftCheck = await page.evaluate(() => ({ state: document.visibilityState, events: window.__bortusVisibility }));
  assert.ok(evidence.visibilityBeforeDraftCheck.state === 'visible', 'Desktop hid test page before equivalent refresh assertion');
  assert.ok(await page.getByLabel('Value for __proto__', { exact: true }).inputValue() === 'synthetic unsaved browser draft', 'Equivalent refresh erased unsaved draft');
  assert.ok(await dialog(page).getByText(/^Captured head /).textContent() === captureBefore, 'Equivalent refresh changed frozen action capture');
  const pollingEnd = await status(fixtureState.writerUrl);
  assert.ok(pollingEnd.requests[capabilityKey] === pollingStart.requests[capabilityKey] + 1, 'One polling cycle made duplicate capability requests');
  mark('Equivalent refresh preserves unsaved draft and frozen capture; one shared poll', { capabilityPolls: 1 });
  await control(fixtureState.writerUrl, 'delay-kv-capabilities');
  const originalSuccess = lastCapabilitiesCompleted;
  await until(async () => (await status(fixtureState.writerUrl)).pendingKvCapabilities, 'Held capability response not reached');
  await until(async () => await page.getByLabel('Value for __proto__', { exact: true }).count() === 0, 'Original capability deadline did not erase private draft');
  const elapsed = Date.now() - originalSuccess;
  assert.ok(elapsed >= 14500 && elapsed <= 18500, 'Expiry did not follow original successful capability timestamp');
  assert.ok(await dialog(page).getByText('Checking fresh permissions. Value controls are paused.').count() === 1, 'Expired capabilities did not pause private controls');
  mark('Held capability refresh expires at original fifteen-second deadline and clears draft', { elapsedFromCompletedResponseMs: elapsed, pendingAtExpiry: (await status(fixtureState.writerUrl)).pendingKvCapabilities });
  await control(fixtureState.writerUrl, 'release-kv-capabilities');
  await dialog(page).getByRole('button', { name: 'Edit grouped fields', exact: true }).waitFor();
  assert.ok(await page.getByLabel('Value for __proto__', { exact: true }).count() === 0, 'Fresh capability reply resurrected cleared draft');
  await editor(page);
  const hiddenCountsBefore = await status(fixtureState.writerUrl);
  await control(fixtureState.writerUrl, 'delay-kv-capabilities');
  await until(async () => (await status(fixtureState.writerUrl)).pendingKvCapabilities, 'Hidden-page held response not reached');
  const windowControl = await context.newCDPSession(page);
  const { windowId } = await windowControl.send('Browser.getWindowForTarget');
  await windowControl.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'minimized' } });
  await until(async () => await page.evaluate(() => document.visibilityState) === 'hidden', 'Browser did not generate real hidden visibility', 5000);
  await until(async () => await page.getByLabel('Value for __proto__', { exact: true }).count() === 0, 'Hidden page retained private editor');
  await control(fixtureState.writerUrl, 'release-kv-capabilities');
  const hiddenCounts = await status(fixtureState.writerUrl);
  await new Promise(resolve => setTimeout(resolve, 11000));
  const hiddenLater = await status(fixtureState.writerUrl);
  assert.ok(hiddenLater.requests[capabilityKey] === hiddenCounts.requests[capabilityKey], 'Hidden page continued capability polling');
  await windowControl.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'normal' } });
  await page.bringToFront();
  await until(async () => await page.evaluate(() => document.visibilityState) === 'visible', 'Page did not return visible');
  await dialog(page).getByRole('button', { name: 'Edit grouped fields', exact: true }).waitFor();
  assert.ok(await page.getByLabel('Value for __proto__', { exact: true }).count() === 0, 'Late held response resurrected hidden private state');
  mark('Real hidden visibility clears private state, stops shared polling and fences held reply', { pollsWhileHidden: 0, heldReadAdded: hiddenCounts.requests[capabilityKey] - hiddenCountsBefore.requests[capabilityKey] });
  await windowControl.detach();
  await dialog(page).getByRole('button', { name: 'Close dialog', exact: true }).click();
  const scoped = await context.newPage(); await scoped.setViewportSize({ width: 390, height: 900 }); await scoped.bringToFront(); await open(scoped, fixtureState.scopedUrl);
  await scoped.getByRole('button', { name: 'Values and versions', exact: true }).click(); await editor(scoped);
  const beforeWithdrawal = await status(fixtureState.scopedUrl);
  await control(fixtureState.scopedUrl, 'deny-kv-update');
  await until(async () => await scoped.getByLabel('Value for __proto__', { exact: true }).count() === 0, 'Fresh policy withdrawal retained private draft');
  assert.ok(await dialog(scoped).getByRole('button', { name: 'Edit grouped fields', exact: true }).count() === 0, 'Denied update control remained available');
  assert.ok((await status(fixtureState.scopedUrl)).requests['PUT /api/kv/paths/' + id + '/data'] === beforeWithdrawal.requests['PUT /api/kv/paths/' + id + '/data'], 'Policy withdrawal test sent a mutation');
  mark('Fresh scoped update withdrawal discards draft and removes mutation control without write');
  const bounds = await scoped.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth, privateEditors: document.querySelectorAll('textarea').length }));
  assert.ok(bounds.privateEditors === 0, 'Metadata screenshot would retain private editor');
  assert.ok(bounds.scroll <= bounds.client, 'Actual route exceeds mobile document bounds');
  await scoped.screenshot({ path: '../../docs/implementation-evidence/shared-freshness-browser-mobile.png' });
  evidence.metadataScreenshot = 'shared-freshness-browser-mobile.png'; evidence.mobileBounds = bounds;
  evidence.counts = await status(fixtureState.scopedUrl);
  mark('Metadata-only final screenshot fits390pixels and has no private textarea');
} catch (error) {
  evidence.failures.push(error instanceof Error ? error.message.split('\n')[0] : 'Browser qualification failed');
  process.exitCode = 1; console.log('BROWSER_QUALIFICATION_FAILED');
} finally {
  if (browser?.isConnected()) { const shutdown = await browser.newBrowserCDPSession(); await shutdown.send('Browser.close'); await browser.close(); }
  if (chrome?.exitCode === null) await Promise.race([once(chrome, 'exit'), new Promise((_, reject) => setTimeout(() => reject(Error('Owned Chrome normal shutdown timed out')), 10000))]);
  evidence.cleanup.browserClosed = true; evidence.cleanup.chromeExitCode = chrome?.exitCode;
  if (fixture.exitCode === null) { fixture.stdin.write('stop\n'); await Promise.race([once(fixture, 'exit'), new Promise((_, reject) => setTimeout(() => reject(Error('Fixture normal shutdown timed out')), 15000))]); }
  evidence.cleanup.fixtureExitCode = fixture.exitCode;
  await writeFile('../../docs/implementation-evidence/shared-freshness-browser.json', JSON.stringify(evidence, null, 2) + '\n');
}
