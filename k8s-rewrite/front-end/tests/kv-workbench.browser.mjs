// Standalone synthetic browser qualification. No production server, DB, credentials or native API.
// Run from front-end: node tests/kv-workbench.browser.mjs <absolute playwright package path> [browser executable]
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
const require = createRequire(import.meta.url);
const { chromium } = require(process.argv[2] || 'playwright');
const { build } = require('esbuild');
const temp = await mkdtemp(path.join(tmpdir(), 'bortus-workbench-browser-'));
await build({ entryPoints: ['tests/kv-workbench-browser-entry.tsx'], bundle: true, outfile: path.join(temp, 'fixture.js'), platform: 'browser', jsx: 'automatic', define: { 'process.env.NODE_ENV': '"production"' } });
execFileSync(process.execPath, ['node_modules/tailwindcss/lib/cli.js', '-i', 'src/app/globals.css', '-o', path.join(temp, 'fixture.css')], { stdio: 'pipe' });
const js = await readFile(path.join(temp, 'fixture.js')), css = await readFile(path.join(temp, 'fixture.css'));
const server = createServer((req, res) => {
  if (req.url === '/fixture.js') { res.setHeader('Content-Type', 'application/javascript'); res.end(js); }
  else if (req.url === '/fixture.css') { res.setHeader('Content-Type', 'text/css'); res.end(css); }
  else { res.setHeader('Content-Type', 'text/html'); res.end('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Synthetic BORTUS workbench fixture</title><link rel="stylesheet" href="/fixture.css"><body class="bg-zinc-950 text-zinc-100"><div id="root"></div><script src="/fixture.js"></script></body></html>'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;
const browser = await chromium.launch({ headless: true, ...(process.argv[3] ? { executablePath: process.argv[3] } : {}) });
const page = await browser.newPage({ viewport: { width: 768, height: 900 }, acceptDownloads: true });
const evidence = { fixture: 'Synthetic standalone real component with intercepted API responses; no native/backend acceptance', port, node: process.version, checks: [], viewports: [], failures: [] };
const mark = name => evidence.checks.push(name);
let role = 'write', head = 0, rv = 1, adopted = false, tombstone = false, staleNext = false, delayed = false, readGranted = true;
let valueRequests = 0, adoptionRequests = 0, mutationRequests = 0;
const originals = [{ field: 'text', encoding: 'utf8', value: 'synthetic original' }, { field: 'empty', encoding: 'utf8', value: '' }, { field: 'binary', encoding: 'base64', value: 'AP8=' }];
let fields = structuredClone(originals), versions = [];
const snapshots = new Map();
const id = '11111111-1111-1111-1111-111111111111', mountId = '22222222-2222-2222-2222-222222222222';
const mapping = [{ field: 'text', key: 'original_under_score' }, { field: 'empty', key: 'zero' }, { field: 'binary', key: 'bytes' }];
const caps = pathId => ({ pathId, revision: 7, permissions: Object.fromEntries(['list', 'read', 'create', 'update', 'delete', 'rollback', 'reconcile', 'export'].map(action => [action, action === 'list' || role === 'write' && (action !== 'read' || readGranted)])), nativeMutationEnabled: true, initializationAllowed: role === 'write' });
function commit(next = fields, deleted = false) {
  mutationRequests++; head++; rv++; fields = structuredClone(next); tombstone = deleted; adopted = true;
  snapshots.set(head, { fields: structuredClone(fields), tombstone }); versions.push({ version: head, createdAt: '2026-10-10T20:00:00Z', tombstone });
  return { operationId: '44444444-4444-4444-4444-444444444444', outcome: 'committed', head, resourceVersion: String(rv), tombstone };
}
await page.route('**/api/**', async route => {
  const req = route.request(), url = new URL(req.url()), method = req.method(); let body;
  try { body = req.postDataJSON(); } catch { body = undefined; }
  const send = (json, status = 200) => route.fulfill({ status, contentType: 'application/json', headers: { 'Cache-Control': 'private, no-store' }, body: JSON.stringify(json) }).catch(() => {});
  if (url.pathname === '/api/auth/session') return send({ authenticated: true, username: 'synthetic', role, engineAdmin: role === 'write' });
  if (url.pathname.endsWith('/capabilities')) return send(caps(url.pathname.split('/')[4]));
  if (url.pathname.endsWith('/status')) return send({ pathId: id, resourceVersion: String(rv), adopted, head, tombstone, guardedAdoption: true });
  if (url.pathname.endsWith('/adopt') && method === 'GET') {
    adoptionRequests++; return send({ pathId: id, resourceVersion: String(rv), expectedHead: 0, fields: mapping, guardedAdoption: true,
      legacyAliases: Array.from({ length: 45 }, (_, i) => ({ alias: 'exact_alias_' + i, namespace: 'apps', name: 'original', key: 'original_under_score' })) });
  }
  if (url.pathname.endsWith('/versions')) return send({ pathId: id, head, resourceVersion: String(rv), items: versions });
  if (url.pathname.endsWith('/data') && method === 'GET') {
    valueRequests++; const historical = url.pathname.match(/versions\/(\d+)\/data/), version = historical ? Number(historical[1]) : head;
    const snapshot = snapshots.get(version) ?? { fields, tombstone };
    if (delayed) { delayed = false; await new Promise(resolve => setTimeout(resolve, 500)); }
    return send({ pathId: id, resourceVersion: String(rv), head, version, ...snapshot });
  }
  if (url.pathname.startsWith('/api/kv/operations/')) return send({ id: '44444444-4444-4444-4444-444444444444', outcome: 'committed' });
  if (url.pathname === '/api/kv/export') {
    assert.equal(body.confirmCredentials, true); const selection = body.selections[0];
    const selected = snapshots.get(selection.version ?? head);
    return send({ format: 'bortus-kv', version: 1, documents: [{ mountId, path: 'apps/api', namespace: 'apps', name: 'original', mappings: mapping, fields: selected.fields, sourceVersion: selection.version ?? head }] });
  }
  if (url.pathname === '/api/kv/import/preview') return send({ format: 'bortus-kv-import-preview', version: 1, guardedAdoption: true, containsCredentialValues: false, atomic: false,
    plans: body.bundle.documents.map((doc, documentIndex) => ({ documentIndex, outcome: 'ready', status: 200, pathId: id, revision: 7, resourceVersion: String(rv), expectedHead: head, requiresOverwrite: true, path: doc.path, namespace: doc.namespace, name: doc.name })) });
  if (url.pathname === '/api/kv/import') {
    assert.equal(body.confirmCredentials, true); assert.equal(body.plans.every(plan => plan.overwrite && plan.revision === 7), true);
    const result = commit(body.bundle.documents[0].fields);
    return send({ atomic: false, success: false, outcomes: [{ documentIndex: 0, pathId: id, status: 200, ...result }, { documentIndex: 1, pathId: null, status: 409, outcome: 'refused' }] });
  }
  if (method !== 'GET') {
    assert.equal(body.pathRevision, 7); // The app owner's human-schema fix is a separate native API gate.
    if (staleNext || body.resourceVersion !== String(rv) || body.expectedHead !== head) { staleNext = false; return send({ error: 'synthetic secret error must be suppressed', outcome: 'conflict', operationId: '44444444-4444-4444-4444-444444444444' }, 409); }
    assert.equal(body.resourceVersion, String(rv)); assert.equal(body.expectedHead, head);
    if (url.pathname.endsWith('/adopt')) { assert.equal(body.legacyAliases.length, 45); const result = commit(); assert.deepEqual(fields, originals); return send(result); }
    if (method === 'DELETE') { assert.equal(body.confirmPath, 'apps/api'); return send(commit([], true)); }
    if (url.pathname.endsWith('/rollback')) { const saved = snapshots.get(body.version); return send(commit(saved.fields, saved.tombstone)); }
    return send(commit(body.fields ?? fields));
  }
  return send({ error: 'Synthetic unknown route' }, 404);
});
const click = text => page.getByRole('button', { name: text, exact: true }).click();
const fillExact = async () => { await page.getByLabel('Type exact logical path: apps/api').fill('apps/api'); };
const wait = () => page.waitForTimeout(100);
const fillReplacement = async () => {
  await page.getByLabel('Value for text', { exact: true }).fill('synthetic operator replacement');
  await page.getByLabel('Intentionally store empty bytes for empty', { exact: true }).check();
  await page.getByLabel('Encoding for binary', { exact: true }).selectOption('base64');
  await page.getByLabel('Value for binary', { exact: true }).fill('AQI=');
  await fillExact();
  await page.getByLabel('Replace the entire mapped document with only these entered fields. Unchecked mapped fields are removed; current values have not been read.').check();
};
try {
  await page.goto('http://127.0.0.1:' + port); await click('Open synthetic workbench');
  await page.getByRole('button', { name: 'Preview explicit adoption', exact: true }).waitFor(); await wait();
  assert.equal(valueRequests, 0); assert.equal(adoptionRequests, 0); mark('Browse triggers only status/capabilities, no value or adoption access');
  await click('Preview explicit adoption'); await page.getByRole('heading', { name: 'Preserve originals and adopt as version 1' }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Confirm adoption', exact: true }).isDisabled(), true);
  assert.equal(await page.locator('[aria-label="Adoption preview"] li').count(), 23); // 3 mappings + 20 aliases
  await page.locator('[aria-label="Adoption preview"]').getByRole('button', { name: 'Next', exact: true }).click();
  await fillExact(); await page.getByLabel('I reviewed the mapped fields and all affected aliases; preserve the originals and create immutable version 1.').check();
  await click('Confirm adoption'); await page.getByText('Operation committed. Refresh metadata to inspect the new head.').waitFor();
  assert.deepEqual(fields, originals); mark('Explicit adoption preserves original binary/empty/text bytes and exact aliases');
  await click('Refresh metadata'); await click('Edit grouped fields'); await page.getByRole('heading', { name: 'Edit grouped fields', exact: true }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Save as new version', exact: true }).isDisabled(), true);
  await page.getByLabel('Value for text', { exact: true }).fill('');
  assert.equal(await page.getByRole('button', { name: 'Save as new version', exact: true }).isDisabled(), true);
  await page.getByLabel('Intentionally store empty bytes for text', { exact: true }).check();
  assert.equal(await page.getByRole('button', { name: 'Save as new version', exact: true }).isDisabled(), false);
  await page.getByLabel('Value for text', { exact: true }).fill('synthetic replacement');
  await click('Save as new version'); await page.getByText('Operation committed. Refresh metadata to inspect the new head.').waitFor();
  assert.equal(fields.find(field => field.field === 'binary').value, 'AP8='); assert.equal(fields.find(field => field.field === 'empty').value, '');
  mark('Untouched save disabled; explicit empty intent; grouped update preserves binary/empty siblings');
  await click('Refresh metadata'); await click('Edit grouped fields'); await page.getByLabel('Value for text', { exact: true }).fill('synthetic stale draft');
  staleNext = true; const beforeConflict = mutationRequests;
  await click('Save as new version'); await page.getByText('Conflict or external drift. Clear drafts, refresh metadata, and inspect before opening a new action.').waitFor();
  assert.equal(mutationRequests, beforeConflict); assert.equal(await page.getByLabel('Value for text', { exact: true }).count(), 0); assert.equal((await page.locator('body').innerText()).includes('synthetic secret error'), false);
  mark('409 clears failed edit, preserves current data and suppresses arbitrary API error text without retry');
  await click('Refresh metadata'); await click('Browse immutable history metadata');
  await page.getByRole('button', { name: 'Reveal version 1', exact: true }).waitFor();
  assert.equal(valueRequests, 2); // only two explicit edit opens
  await click('Rollback version 1'); await fillExact(); await page.getByLabel('I understand and explicitly authorize this action for the exact path and selected version.').check();
  await click('Confirm rollback'); await page.getByText('Operation committed. Refresh metadata to inspect the new head.').waitFor();
  assert.equal(head, 3); assert.deepEqual(snapshots.get(1).fields, originals); assert.deepEqual(fields, originals); mark('History is metadata-only; rollback creates a new immutable head');
  await click('Refresh metadata'); await click('Soft-delete document'); await fillExact(); await page.getByLabel('I understand and explicitly authorize this action for the exact path and selected version.').check();
  await click('Confirm delete'); await page.getByText('Operation committed. Refresh metadata to inspect the new head.').waitFor();
  assert.equal(tombstone, true); assert.equal(fields.length, 0);
  await click('Refresh metadata'); await click('Browse immutable history metadata'); await click('Restore version 1'); await fillExact();
  await page.getByLabel('I understand and explicitly authorize this action for the exact path and selected version.').check(); await click('Confirm rollback');
  await page.getByText('Operation committed. Refresh metadata to inspect the new head.').waitFor(); assert.equal(head, 5); assert.equal(tombstone, false); mark('Soft-delete retains history; explicit restore creates a new value version');
  await click('Refresh metadata'); delayed = true; const beforeLate = valueRequests; await click('Reveal current fields');
  await page.waitForFunction(() => document.body.innerText.includes('Request in progress'));
  await click('Clear display and draft'); await page.waitForTimeout(700);
  assert.equal(valueRequests, beforeLate + 1); assert.equal(await page.locator('[aria-label^="Revealed version"]').count(), 0); mark('Clear cancels/fences delayed reveal');
  await click('Reveal current fields'); await page.locator('[aria-label^="Revealed version"]').waitFor();
  assert.equal(await page.getByLabel('binary · base64').inputValue(), 'AP8=');
  await page.evaluate(() => { for (const storage of [localStorage, sessionStorage]) for (let i = 0; i < storage.length; i++) { if (storage.getItem(storage.key(i)).includes('synthetic original')) throw Error('Value entered browser persistence'); } });
  await click('Clear display and draft');
  await click('Export current document'); assert.equal(await page.getByRole('button', { name: 'Confirm export', exact: true }).isDisabled(), true);
  await fillExact(); await page.getByLabel('I understand and explicitly authorize this action for the exact path and selected version.').check();
  const download = page.waitForEvent('download'); await click('Confirm export'); const artifact = await download;
  assert.equal(artifact.suggestedFilename(), 'bortus-kv-export.json'); await artifact.delete(); mark('Native export requires exact path/credential acknowledgement; ephemeral download removed after fixture check');
  await click('Import bundle');
  const bundle = { format: 'bortus-kv', version: 1, documents: [{ mountId, path: 'apps/api', namespace: 'apps', name: 'original', mappings: mapping, fields: originals }, { mountId, path: 'apps/other', namespace: 'apps', name: 'other', mappings: mapping, fields: originals }] };
  await page.getByLabel('BORTUS v1 JSON bundle').fill(JSON.stringify(bundle)); await click('Preview target metadata');
  await page.getByText('2 documents · independent commits · partial success possible. Source versions are informational; each commit creates a new version.').waitFor();
  assert.equal((await page.locator('[aria-label="Protected import"]').innerText()).includes('synthetic original'), false); assert.equal(await page.getByLabel('BORTUS v1 JSON bundle').count(), 0);
  await page.getByLabel('I reviewed every explicit target/mapping and authorize credential transfer with independent commits and new version creation.').check();
  assert.equal(await page.getByRole('button', { name: 'Commit reviewed import', exact: true }).isDisabled(), true);
  for (const checkbox of await page.getByLabel('Overwrite this existing document at the captured head/revision by creating a new version.').all()) await checkbox.check();
  await click('Commit reviewed import'); await page.getByRole('heading', { name: 'Per-document outcomes' }).waitFor();
  assert.equal(await page.getByText('Document 2: refused · HTTP 409').count(), 1); mark('Metadata-only import preview, per-document overwrite/new-version acknowledgement and partial outcomes');
  await click('Refresh metadata'); await click('Edit grouped fields'); await click('Cancel edit'); await wait();
  assert.equal(await page.getByRole('button', { name: 'Refresh metadata', exact: true }).evaluate(el => el === document.activeElement), true); mark('Inline cancellation returns keyboard focus to stable metadata control');
  versions.push(...Array.from({ length: 45 }, (_, i) => ({ version: 100 + i, createdAt: '2026-10-10T20:00:00Z', tombstone: false })));
  await click('Browse immutable history metadata'); await wait();
  assert.equal(await page.locator('[aria-label="Immutable version history"] tbody tr').count(), 20);
  await page.locator('[aria-label="Immutable version history"]').getByRole('button', { name: 'Next', exact: true }).click();
  assert.equal(await page.locator('[aria-label="Immutable version history"] tbody tr').count(), 20);
  await page.locator('[aria-label="Immutable version history"]').getByRole('button', { name: 'Previous', exact: true }).click(); mark('History metadata renders at most 20 versions per page and supports forward/back navigation');
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 900 }); await click('Browse immutable history metadata'); await wait();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    assert.equal(overflow, false); evidence.viewports.push({ width, documentOverflow: overflow });
    await mkdir('../../docs/implementation-evidence', { recursive: true });
    await page.screenshot({ path: `../../docs/implementation-evidence/kv-workbench-${width}.png`, fullPage: true });
  }
  mark('320/390/768 layouts retain overflow within table container');
  await click('Reveal current fields'); await page.locator('[aria-label^="Revealed version"]').waitFor(); role = 'readonly';
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await page.getByText('Metadata only. Fresh write access and path policy are required for values.').waitFor();
  assert.equal(await page.locator('textarea').count(), 0); assert.equal(await page.getByRole('button', { name: 'Edit grouped fields', exact: true }).count(), 0); mark('Fresh role withdrawal clears values/drafts and hides writer actions');
  await page.keyboard.press('Escape'); await wait(); assert.equal(await page.getByRole('button', { name: 'Open synthetic workbench', exact: true }).evaluate(el => el === document.activeElement), true); mark('Escape closes dialog and restores selection trigger focus');
  await click('Open synthetic workbench'); await wait(); assert.equal(await page.locator('textarea').count(), 0); mark('Close/reopen does not restore prior sensitive state');
  await page.keyboard.press('Escape'); role = 'write'; await click('Open synthetic workbench');
  await page.evaluate(() => window.dispatchEvent(new Event('focus'))); await page.getByRole('button', { name: 'Reveal current fields', exact: true }).waitFor();
  await click('Reveal current fields'); await page.locator('[aria-label^="Revealed version"]').waitFor(); readGranted = false;
  await page.waitForFunction(() => document.querySelectorAll('textarea').length === 0, { timeout: 15000 });
  assert.equal(await page.getByRole('button', { name: 'Reveal current fields', exact: true }).count(), 0); mark('Fresh capability denial clears revealed values even while human role remains write');
  const readsBeforeReplacement = valueRequests, headBeforeReplacement = head;
  await click('Replace complete document without reveal');
  assert.equal(await page.getByRole('button', { name: 'Save as new version', exact: true }).isDisabled(), true);
  await fillReplacement(); await click('Save as new version'); await page.getByText('Operation committed. Refresh metadata to inspect the new head.').waitFor();
  assert.equal(valueRequests, readsBeforeReplacement); assert.equal(head, headBeforeReplacement + 1);
  assert.equal(fields.find(field => field.field === 'binary').value, 'AQI=');
  assert.equal(fields.find(field => field.field === 'empty').value, '');
  await click('Refresh metadata'); await click('Browse immutable history metadata'); await wait();
  assert.equal(await page.getByRole('button', { name: /^Reveal version/ }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Reveal current fields', exact: true }).count(), 0);
  mark('Write-without-read complete mapped replacement succeeds with zero value/history reads and explicit replacement/CAS confirmation');
  await click('Replace complete document without reveal'); await fillReplacement(); rv++; // Native metadata changes after the form captured its revision.
  const writesBeforeStaleReplacement = mutationRequests;
  await click('Save as new version'); await page.getByText('Conflict or external drift. Clear drafts, refresh metadata, and inspect before opening a new action.').waitFor();
  assert.equal(mutationRequests, writesBeforeStaleReplacement); assert.equal(valueRequests, readsBeforeReplacement);
  mark('Write-without-read stale CAS fails without retry or value prefetch');
  await click('Refresh metadata'); await click('Replace complete document without reveal'); await fillReplacement();
  const writesBeforeWithdrawal = mutationRequests; role = 'readonly'; await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await page.getByText('Metadata only. Fresh write access and path policy are required for values.').waitFor();
  assert.equal(await page.locator('textarea').count(), 0); assert.equal(await page.getByRole('button', { name: 'Save as new version', exact: true }).count(), 0);
  assert.equal(mutationRequests, writesBeforeWithdrawal); assert.equal(valueRequests, readsBeforeReplacement);
  mark('Fresh permission withdrawal discards a confirmed write-without-read replacement and prevents submission');
  role = 'write'; await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await page.keyboard.press('Escape'); readGranted = true; await click('Open synthetic workbench'); await page.getByRole('button', { name: 'Reveal current fields', exact: true }).waitFor();
  delayed = true; await click('Reveal current fields'); await page.evaluate(() => window.dispatchEvent(new Event('bortus-session-ended'))); await page.waitForTimeout(700);
  assert.equal(await page.locator('textarea').count(), 0); mark('Session-ended event fences pending reveal and clears all sensitive forms');
  await page.keyboard.press('Escape'); await click('Open synthetic workbench'); await page.getByRole('button', { name: 'Reveal current fields', exact: true }).waitFor();
  await click('Reveal current fields'); await page.locator('[aria-label^="Revealed version"]').waitFor();
  await page.evaluate(() => document.getElementById('switch').click()); await page.getByRole('dialog', { name: 'KV · apps/other', exact: true }).waitFor();
  assert.equal(await page.locator('textarea').count(), 0); await page.waitForTimeout(700); assert.equal(await page.locator('textarea').count(), 0); mark('Explicit path switch unmounts/fences prior value state');
} catch (error) {
  evidence.failures.push(error instanceof Error ? error.message : 'Browser assertion failed'); throw error;
} finally {
  evidence.valueRequests = valueRequests; evidence.adoptionRequests = adoptionRequests; evidence.mutationRequests = mutationRequests;
  await writeFile('../../docs/implementation-evidence/kv-workbench-browser.json', JSON.stringify(evidence, null, 2) + '\n');
  await browser.close(); await new Promise(resolve => server.close(resolve));
  console.log(JSON.stringify({ port, passedChecks: evidence.checks.length, failures: evidence.failures.length, temp }));
}
