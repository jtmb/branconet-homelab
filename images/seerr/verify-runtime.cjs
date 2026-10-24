// Run in the built image without production configuration or network delivery.
const assert = require('node:assert/strict');
const fs = require('node:fs');

async function main() {
  assert.equal(process.getuid(), 1000);
  for (const [name, version] of Object.entries({
    next: '16.4.3', axios: '1.20.0', sharp: '0.35.5', nodemailer: '10.0.6',
    'ip-address': '10.7.4',
  })) {
    // Package exports can hide package.json (Sharp does); read the installed
    // application dependency's metadata without importing a private subpath.
    const metadata = JSON.parse(fs.readFileSync(`/app/node_modules/${name}/package.json`, 'utf8'));
    assert.equal(metadata.name, name);
    assert.equal(metadata.version, version, name);
  }
  const sqlite3 = require('sqlite3');
  const db = new sqlite3.Database(':memory:');
  await new Promise((resolve, reject) => db.get('SELECT 42 AS answer', (error, row) => {
    if (error) return reject(error);
    try { assert.equal(row.answer, 42); resolve(); } catch (failure) { reject(failure); }
  }));
  await new Promise((resolve, reject) => db.close(error => error ? reject(error) : resolve()));
  const bcrypt = require('bcrypt');
  assert.equal(await bcrypt.compare('synthetic-runtime-check', await bcrypt.hash('synthetic-runtime-check', 4)), true);
  const sharp = require('sharp');
  const pixel = await sharp({ create: { width: 1, height: 1, channels: 3, background: '#112233' } }).png().toBuffer();
  assert.equal((await sharp(pixel).metadata()).width, 1);
  const nodemailer = require('nodemailer');
  const mail = await nodemailer.createTransport({ jsonTransport: true }).sendMail({
    from: 'runtime-check@example.invalid', to: 'runtime-check@example.invalid',
    subject: 'Synthetic local serialization', text: 'No SMTP connection is used.',
  });
  assert.equal(JSON.parse(mail.message).subject, 'Synthetic local serialization');
  assert.ok(fs.existsSync('/app/dist/index.js'));
  assert.ok(fs.existsSync('/app/.next/BUILD_ID'));
  assert.ok(fs.existsSync('/sbin/tini'));
  console.log(JSON.stringify({ nativeSQLite: true, bcrypt: true, sharp: true,
    mailSerializationOnly: true, compiledApplication: true, uid: process.getuid() }));
}
main().catch(error => { console.error('Runtime compatibility check failed:', error.name, error.code || ''); process.exitCode = 1; });
