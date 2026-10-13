'use strict';
// Trusted source-linked core; diagnostics must never print operation arguments or rows.
const { parentPort } = require('node:worker_threads');
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const coreFile = path.join(__dirname, 'direct-account-core.cjs'), receiptFile = path.join(__dirname, 'direct-account-build.json');
for (const file of [coreFile, receiptFile]) {
  const stat = fs.lstatSync(file); if (!stat.isFile() || stat.isSymbolicLink()) throw Error('ACCOUNT_READ_UNAVAILABLE');
}
const receipt = JSON.parse(fs.readFileSync(receiptFile, 'utf8'));
if (crypto.createHash('sha256').update(fs.readFileSync(coreFile)).digest('hex') !== receipt.coreSHA256) throw Error('ACCOUNT_READ_UNAVAILABLE');
const { DirectAccountReader } = require('./direct-account-core.cjs');
const now = () => Number(process.hrtime.bigint()) / 1_000_000;
let core, schemaDirectory, active = false;
parentPort.on('message', async message => {
  if (message?.kind === 'discard' && !active && Number.isSafeInteger(message.id)) {
    active = true;
    let closeFailed = false;
    try { await core?.close(); } catch { closeFailed = true; }
    active = false;
    parentPort.postMessage({ kind: 'discarded', id: message.id, closeFailed }); return;
  }
  if (message?.kind === 'close' && !active) {
    let closeFailed = false;
    try { await core?.close(); } catch { closeFailed = true; }
    parentPort.postMessage({ kind: 'closed', closeFailed }); return;
  }
  if (active || message?.kind !== 'read' || !Number.isSafeInteger(message.id) || typeof message.subject !== 'string' ||
      !['session', 'account'].includes(message.projection) || typeof message.config !== 'string' ||
      typeof message.file !== 'string' || typeof message.schemaDirectory !== 'string' || !Number.isFinite(message.deadline) ||
      message.deadline > now() + 5000 || !(message.fence instanceof SharedArrayBuffer) || message.fence.byteLength !== 4) {
    process.exitCode = 125; parentPort.close(); return;
  }
  active = true;
  let refused = true, row;
  try {
    if (!core) {
      schemaDirectory = message.schemaDirectory;
      core = new DirectAccountReader(() => process.env.DATABASE_URL, schemaDirectory, now);
    }
    if (schemaDirectory !== message.schemaDirectory) throw Error('ACCOUNT_READ_UNAVAILABLE');
    const fence = new Int32Array(message.fence);
    row = await core.readInEnvelope(message.subject, message.projection, {
      config: message.config, file: message.file, deadline: message.deadline, revoked: () => Atomics.load(fence, 0) !== 0 });
    refused = false;
  } catch { /* Fixed refusal only; error messages and rows never enter diagnostics. */ }
  await core?.whenIdle();
  const identity = core?.settlementIdentity();
  const closeFailed = core?.activity().closeFailed ?? false;
  active = false;
  parentPort.postMessage({ kind: 'settled', id: message.id, refused, row, identity, closeFailed });
});
