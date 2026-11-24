const fs = require('node:fs');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');

// Nodemailer 10 ships its own declarations. email-templates still imports the
// pre-10 DefinitelyTyped Mail class; adapt only that declaration to the actual API.
if (process.argv[2] === '--mail-types') {
  const resolve = createRequire('/app/package.json');
  const path = resolve.resolve('@types/email-templates/index.d.ts');
  const mailPackage = resolve.resolve('nodemailer/package.json');
  if (JSON.parse(fs.readFileSync(mailPackage, 'utf8')).version !== '10.0.6') {
    throw new Error('Unexpected Nodemailer version for the declaration adaptation');
  }
  // Resolve from the application, rather than email-templates' pnpm directory:
  // its local @types/nodemailer dependency would otherwise select the old types.
  const bundledTypes = require('node:path').join(require('node:path').dirname(mailPackage), 'dist/cjs/nodemailer');
  const original = fs.readFileSync(path);
  if (crypto.createHash('sha256').update(original).digest('hex') !==
      '8df874f9810e859fa19d7c6de1a28b2f328130456d69f2d2a4c36e89eb811d64') {
    throw new Error('Unexpected email-templates declaration; review the pinned version');
  }
  let types = original.toString('utf8');
  types = types.replace('/// <reference types="nodemailer"/>\n\n', '');
  types = types.replace(/^import (?:JSONTransport|Mail|SendmailTransport|SESTransport|SMTPPool|SMTPTransport|StreamTransport) = require\([^\n]+\);\n/gm, '');
  types = `import type { Mail, SendMailOptions, TransportConfig } from ${JSON.stringify(bundledTypes)};\n` + types;
  types = types.replace(/    type NodeMailerTransportOptions =[\s\S]*?        \| string;/,
    '    type NodeMailerTransportOptions = Mail | TransportConfig | string;');
  types = types.replace(/Mail\.Options/g, 'SendMailOptions');
  if (types === original.toString('utf8') || types.includes('Mail.Options') ||
      !types.includes('type NodeMailerTransportOptions = Mail | TransportConfig | string;')) {
    throw new Error('Email declaration adaptation did not match its pinned source');
  }
  fs.writeFileSync(path, types);
  console.log('Adapted email-templates declarations to Nodemailer 10 bundled types');
  process.exit(0);
}

// Axios 1.20 exposes a wider response-header type. Keep image parsing on the
// actual string contract and let malformed headers use the existing cache miss.
const imageProxyPath = '/app/server/lib/imageproxy.ts';
const imageProxyOriginal = fs.readFileSync(imageProxyPath);
if (crypto.createHash('sha256').update(imageProxyOriginal).digest('hex') !==
    '2eb1c0eb2d7bdca374f9e33e0f777e8c2fea6a583b4f223c559be2b5f699b5cc') {
  throw new Error('Unexpected pinned image proxy source; review the header adaptation');
}
let imageProxySource = imageProxyOriginal.toString('utf8');
const headerReplacements = [
  ["      const contentType = response.headers['content-type'] || '';",
    `      const contentType = response.headers['content-type'] ?? '';
      if (typeof contentType !== 'string') {
        throw new Error('Unexpected image content-type header');
      }`],
  [`      let maxAge = Number(
        (response.headers['cache-control'] ?? '0').split('=')[1]
      );`,
    `      const cacheControl = response.headers['cache-control'] ?? '0';
      if (typeof cacheControl !== 'string') {
        throw new Error('Unexpected image cache-control header');
      }
      let maxAge = Number(cacheControl.split('=')[1]);`],
];
for (const [original, adapted] of headerReplacements) {
  if (imageProxySource.split(original).length !== 2) {
    throw new Error('Image header adaptation did not match its pinned source');
  }
  imageProxySource = imageProxySource.replace(original, adapted);
}
fs.writeFileSync(imageProxyPath, imageProxySource);

const pkg = JSON.parse(fs.readFileSync('/app/package.json', 'utf8'));
const patch = JSON.parse(fs.readFileSync('/tmp/security-overrides.json', 'utf8'));
Object.assign(pkg.dependencies, patch.dependencies);
Object.assign(pkg.devDependencies, patch.devDependencies);
// Native addons build in the build stage; node-gyp is not an application runtime.
pkg.devDependencies['node-gyp'] = pkg.dependencies['node-gyp'];
delete pkg.dependencies['node-gyp'];
pkg.pnpm ??= {};
pkg.pnpm.overrides = { ...pkg.pnpm.overrides, ...patch.overrides };
fs.writeFileSync('/app/package.json', JSON.stringify(pkg, null, 2) + '\n');
