// Inject with qualify-seerr.py; never import the application's server or entities.
'use strict';
const fs = require('node:fs');
const crypto = require('node:crypto');
const http = require('node:http');
const https = require('node:https');
const sqlite3 = require('/app/node_modules/sqlite3');
const SOURCE = '564bfb08b54caa374bddaf820abfd226e5e69151';
const TABLES = ['user', 'media_request', 'media', 'season', 'season_request', 'issue', 'issue_comment', 'user_settings', 'user_push_subscription'];
const REQUIRED_USERS = ['id', 'email', 'username', 'password', 'plexId', 'plexUsername', 'plexToken', 'permissions', 'avatar', 'createdAt', 'updatedAt'];
const IDENT = /^[A-Za-z_][A-Za-z0-9_]*$/;
const HEX = /^[a-f0-9]{64}$/;
const quote = s => { if (!IDENT.test(s)) throw Error('schema'); return '"' + s + '"'; };
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const canonical = value => JSON.stringify(value);
const readJSON = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const result = { format: 1, upstreamSource: SOURCE, checks: {}, fullPreservation: false, acceptanceComplete: false };
let db;
const all = sql => new Promise((resolve, reject) => db.all(sql, (e, rows) => e ? reject(Error('sqlite')) : resolve(rows)));
const exec = sql => new Promise((resolve, reject) => db.exec(sql, e => e ? reject(Error('sqlite')) : resolve()));

// No redirects, environment proxies, URLs in output, raw response logging or retry.
function getJSON(url, headers = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    if (!['http:', 'https:'].includes(u.protocol) || u.username || u.password || u.hash || u.search && !(u.hostname === '127.0.0.1' && u.search === '?checkUpdateAvailable=false')) return reject(Error('url'));
    let size = 0;
    const chunks = [];
    const request = (u.protocol === 'https:' ? https : http).get(u, { headers: { Accept: 'application/json', ...headers }, rejectUnauthorized: true }, response => {
      if (response.statusCode !== 200) { response.resume(); return reject(Error('http')); }
      response.on('data', chunk => {
        size += chunk.length;
        if (size > 1024 * 1024) response.destroy(Error('size'));
        else chunks.push(chunk);
      });
      response.on('error', () => reject(Error('http')));
      response.on('end', () => { try { resolve(JSON.parse(Buffer.concat(chunks))); } catch { reject(Error('json')); } });
    });
    request.setTimeout(15000, () => request.destroy(Error('timeout')));
    request.on('error', () => reject(Error('http')));
  });
}
function serviceURL(host, port, ssl, base, route) {
  if (typeof host !== 'string' || !host || /[\s/@?#]/.test(host) || !Number.isInteger(Number(port)) || Number(port) < 1 || Number(port) > 65535) throw Error('url');
  if (base && (!base.startsWith('/') || base.startsWith('//') || /[?#\\]/.test(base))) throw Error('url');
  const authority = host.includes(':') && !host.startsWith('[') ? '[' + host + ']' : host;
  return new URL((ssl ? 'https' : 'http') + '://' + authority + ':' + port + (base || '').replace(/\/$/, '') + route);
}
async function main() {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  if (typeof input.key !== 'string' || input.key.length < 32) throw Error('input');
  const b = input.baseline;
  if (!b || !b.userPreservation || !b.counts || b.sqliteQuickCheck !== 'ok' || b.archiveDerived !== true || b.upstreamSource !== SOURCE || !HEX.test(b.archiveSHA256)) throw Error('baseline');
  const digest = value => crypto.createHmac('sha256', input.key).update(canonical(value)).digest('hex');
  if (process.getuid() !== 1000 || process.getgid() !== 1000 || process.cwd() !== '/app') throw Error('runtime');
  result.checks.runtime = readJSON('/app/package.json').version === '3.5.1';
  db = await new Promise((resolve, reject) => { const d = new sqlite3.Database('/app/config/db/db.sqlite3', sqlite3.OPEN_READONLY, e => e ? reject(Error('sqlite')) : resolve(d)); });
  await exec('PRAGMA query_only=ON; PRAGMA busy_timeout=5000; BEGIN');
  result.checks.sqliteQuickCheck = equal((await all('PRAGMA quick_check')).map(r => Object.values(r)[0]), ['ok']);
  result.checks.foreignKeys = (await all('PRAGMA foreign_key_check')).length === 0;
  result.counts = {};
  result.countMatches = {};
  for (const [name, expected] of Object.entries(b.counts)) {
    if (!TABLES.includes(name) || !Number.isSafeInteger(expected) || expected < 0) throw Error('baseline');
    result.counts[name] = (await all('SELECT COUNT(*) AS n FROM ' + quote(name)))[0].n;
    result.countMatches[name] = result.counts[name] === expected;
  }
  if (!['user', 'media_request', 'media', 'season_request', 'issue', 'issue_comment'].every(t => Object.hasOwn(b.counts, t))) throw Error('baseline');
  const ub = b.userPreservation;
  if (!equal(ub.columns, REQUIRED_USERS) || !Array.isArray(ub.ids) || !HEX.test(ub.hmacSHA256) || !ub.perColumn || !REQUIRED_USERS.every(c => HEX.test(ub.perColumn[c]))) throw Error('baseline');
  const users = await all('SELECT ' + ub.columns.map(quote).join(',') + ' FROM "user" ORDER BY id');
  result.users = {
    count: users.length, ids: users.map(u => u.id),
    countMatch: users.length === ub.count, idsMatch: equal(users.map(u => u.id), ub.ids),
    hmacMatch: digest(users) === ub.hmacSHA256,
    perColumnMatches: Object.fromEntries(ub.columns.map(c => [c, digest(users.map(u => u[c])) === ub.perColumn[c]])),
  };
  result.history = {};
  // Optional archive-derived metadata, computed on the same ordered projection.
  // No automatic transformations/exclusions: Root reviews any migrated delta.
  for (const [name, v] of Object.entries(b.historyPreservation || {})) {
    if (!TABLES.includes(name) || name === 'user' || !Array.isArray(v.columns) || !v.columns.includes('id') || new Set(v.columns).size !== v.columns.length || !Array.isArray(v.ids) || !v.perColumn || !v.perRow) throw Error('baseline');
    if (!v.columns.every(c => IDENT.test(c) && HEX.test(v.perColumn[c]))) throw Error('baseline');
    const rows = await all('SELECT ' + v.columns.map(quote).join(',') + ' FROM ' + quote(name) + ' ORDER BY id');
    result.history[name] = { count: rows.length, idsMatch: equal(rows.map(r => r.id), v.ids), perColumnMatches: Object.fromEntries(v.columns.map(c => [c, digest(rows.map(r => r[c])) === v.perColumn[c]])), rowsMatch: rows.length === Object.keys(v.perRow).length && rows.every(r => HEX.test(v.perRow[r.id]) && digest(v.columns.map(c => r[c])) === v.perRow[r.id]) };
  }
  const admin = (await all('SELECT plexToken FROM "user" WHERE id=1'))[0];
  await exec('ROLLBACK');
  await new Promise((resolve, reject) => db.close(e => e ? reject(Error('sqlite')) : resolve()));
  db = undefined;
  const settings = readJSON('/app/config/settings.json');
  function at(pointer) {
    let value = settings;
    for (const segment of pointer.slice(1).split('/').map(s => s.replace(/~1/g, '/').replace(/~0/g, '~'))) {
      if (!value || !Object.hasOwn(value, segment)) return undefined;
      value = value[segment];
    }
    return value;
  }
  result.settings = { migratedToPlex: settings.main?.mediaServerType === 1, initialized: settings.public?.initialized === true,
    lunaSeaAbsent: !Object.hasOwn(settings.notifications?.agents || {}, 'lunasea'),
    arrTagMigrationRecorded: (settings.migrations || []).includes('0007_migrate_arr_tags'), preservation: {} };
  for (const [pointer, expected] of Object.entries(b.settingsPreservation || {})) {
    if (!pointer.startsWith('/') || !HEX.test(expected)) throw Error('baseline');
    const value = at(pointer);
    result.settings.preservation[pointer] = value !== undefined && digest(value) === expected;
  }
  // Keep literal mismatches visible. Only two cold-HMAC-bound operational clocks
  // may separately pass an explicitly supplied, initial-preservation-bound proof.
  result.settings.runtimeScanAdvances = {};
  if (input.runtimeScanProof !== undefined) {
    const proof = input.runtimeScanProof;
    const pointers = ['/plex/libraries/0/lastScan', '/plex/libraries/1/lastScan'];
    if (!proof || proof.format !== 1 || !proof.oldValues || !equal(Object.keys(proof.oldValues).sort(), [...pointers].sort()) || !Number.isSafeInteger(proof.firstPreservedReceiptMS) || !HEX.test(proof.proofSHA256) || !HEX.test(proof.firstPreservedReceiptSHA256) || !HEX.test(proof.baselineSHA256) || proof.archiveSHA256 !== b.archiveSHA256) throw Error('runtime-proof');
    result.runtimeScanProof = { proofSHA256: proof.proofSHA256,
      firstPreservedReceiptSHA256: proof.firstPreservedReceiptSHA256,
      baselineSHA256: proof.baselineSHA256, archiveSHA256: proof.archiveSHA256 };
    for (const pointer of pointers) {
      const original = proof.oldValues[pointer];
      if (!Number.isSafeInteger(original) || original < 0 || digest(original) !== b.settingsPreservation[pointer]) throw Error('runtime-proof');
      if (result.settings.preservation[pointer] === true) continue;
      const current = at(pointer);
      const enabled = at(pointer.replace(/\/lastScan$/, '/enabled'));
      const integerMilliseconds = Number.isSafeInteger(current) && current >= 0;
      const monotonicAdvance = integerMilliseconds && current > original;
      const afterInitialPreservation = integerMilliseconds && current >= proof.firstPreservedReceiptMS;
      const currentTimeBound = integerMilliseconds && current <= Date.now();
      result.settings.runtimeScanAdvances[pointer] = { originalTimestamp: original,
        currentTimestamp: integerMilliseconds ? current : null, integerMilliseconds,
        originalValueHMACMatches: true, monotonicAdvance, afterInitialPreservation,
        currentTimeBound, enabledLibrary: enabled === true,
        reviewedOperationalAdvance: monotonicAdvance && afterInitialPreservation && currentTimeBound && enabled === true };
    }
  }
  result.settings.absenceMatches = Array.isArray(b.settingsAbsent) && b.settingsAbsent.every(p => at(p) === undefined);
  result.settings.arrayLengthsMatch = !!b.settingsArrayLengths && Object.entries(b.settingsArrayLengths).every(([p, n]) => Array.isArray(at(p)) && at(p).length === n);
  result.settings.priorMigrationsRetained = Array.isArray(b.settingsPriorMigrations) && b.settingsPriorMigrations.every(m => settings.migrations?.includes(m));
  const status = await getJSON('http://127.0.0.1:5055/api/v1/status?checkUpdateAvailable=false');
  const publicSettings = await getJSON('http://127.0.0.1:5055/api/v1/settings/public');
  const appdata = await getJSON('http://127.0.0.1:5055/api/v1/status/appdata');
  result.checks.startupAPI = status.version === '3.5.1' && status.commitTag === readJSON('/app/committag.json').commitTag && status.restartRequired === false && publicSettings.initialized === true && publicSettings.mediaServerType === 1 && appdata.appDataPermissions === true && appdata.appDataPath === '/app/config';
  if (!admin?.plexToken || !settings.plex?.machineId) throw Error('plex-config');
  const plex = await getJSON(serviceURL(settings.plex.ip, settings.plex.port, settings.plex.useSsl, '', '/'), { 'X-Plex-Token': admin.plexToken, 'X-Plex-Client-Identifier': settings.clientId });
  result.checks.plex = plex.MediaContainer?.machineIdentifier === settings.plex.machineId;
  result.integrations = {};
  for (const kind of ['radarr', 'sonarr']) {
    if (!Array.isArray(settings[kind]) || !settings[kind].length || settings[kind].length > 8) throw Error('arr-config');
    result.integrations[kind] = [];
    for (const config of settings[kind]) {
      if (!config.apiKey || !Number.isSafeInteger(config.id)) throw Error('arr-config');
      const status = await getJSON(serviceURL(config.hostname, config.port, config.useSsl, config.baseUrl, '/api/v3/system/status'), { 'X-Api-Key': config.apiKey });
      result.integrations[kind].push({ id: config.id, healthy: typeof status.version === 'string' && status.version.length > 0 && status.appName?.toLowerCase() === kind });
    }
  }
  const allTrue = values => Object.values(values).every(v => v === true);
  result.checks.accounts = result.users.countMatch && result.users.idsMatch && result.users.hmacMatch && allTrue(result.users.perColumnMatches);
  result.checks.historyCounts = allTrue(result.countMatches);
  result.checks.historyFingerprints = TABLES.filter(t => t !== 'user').every(t => result.history[t]?.idsMatch && result.history[t]?.rowsMatch && allTrue(result.history[t].perColumnMatches));
  // Credentials/config protected as original leaf pointers; all supplied checks
  // must match. Root must include every original retained leaf, not just these.
  const pointers = Object.keys(result.settings.preservation);
  result.checks.settingsFingerprints = ['/clientId', '/main/apiKey', '/plex/ip', '/plex/port', '/plex/machineId', '/radarr/0/apiKey', '/sonarr/0/apiKey'].every(p => pointers.includes(p)) && Object.entries(result.settings.preservation).every(([p, literal]) => literal === true || result.settings.runtimeScanAdvances[p]?.reviewedOperationalAdvance === true) && result.settings.absenceMatches && result.settings.arrayLengthsMatch && result.settings.priorMigrationsRetained;
  result.checks.migrationSettings = result.settings.migratedToPlex && result.settings.initialized && result.settings.lunaSeaAbsent && result.settings.arrTagMigrationRecorded;
  result.checks.integrations = Object.values(result.integrations).every(a => a.every(v => v.healthy));
  result.fullPreservation = result.checks.accounts && result.checks.historyCounts && result.checks.historyFingerprints && result.checks.settingsFingerprints;
  result.helperChecksPassed = allTrue(result.checks);
  // UI, original routing, tag reconciliation, rollback, and restart are Root gates.
  process.stdout.write(JSON.stringify(result) + '\n');
  process.exitCode = result.helperChecksPassed ? 0 : 3;
}
main().catch(async () => {
  if (db) await new Promise(resolve => db.close(() => resolve()));
  process.stdout.write(JSON.stringify({ ...result, failed: true, error: 'qualification-failed' }) + '\n');
  process.exitCode = 1;
});
