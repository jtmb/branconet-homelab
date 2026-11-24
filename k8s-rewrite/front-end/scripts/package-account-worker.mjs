import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const root = process.cwd(), target = path.join(root, '.next/standalone');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const receipt = JSON.parse(fs.readFileSync(path.join(root, 'runtime/direct-account-build.json'), 'utf8'));
if (hash(fs.readFileSync(path.join(root, 'src/lib/direct-account-core.ts'))) !== receipt.sourceSHA256 ||
    hash(fs.readFileSync(path.join(root, 'runtime/direct-account-core.cjs'))) !== receipt.coreSHA256 ||
    hash(fs.readFileSync(path.join(root, 'runtime/direct-account-reader-worker.cjs'))) !== receipt.workerSHA256) throw Error('Account worker source binding refused');
for (const relative of ['runtime/direct-account-reader-worker.cjs', 'runtime/direct-account-core.cjs',
  'runtime/direct-account-build.json', 'prisma/schema.prisma']) {
  const bytes = fs.readFileSync(path.join(root, relative)), output = path.join(target, relative);
  fs.mkdirSync(path.dirname(output), { recursive: true }); fs.writeFileSync(output, bytes);
  if (hash(fs.readFileSync(output)) !== hash(bytes)) throw Error('Account worker standalone binding refused');
}
