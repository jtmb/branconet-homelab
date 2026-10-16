import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import ts from 'typescript';
const root = process.cwd();
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const source = fs.readFileSync(path.join(root, 'src/lib/direct-account-core.ts'));
const result = ts.transpileModule(source.toString('utf8'), {
  fileName: 'direct-account-core.ts', reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, strict: true, esModuleInterop: true }
});
if (result.diagnostics?.some(d => d.category === ts.DiagnosticCategory.Error)) throw Error('Account worker compilation refused');
const out = path.join(root, 'runtime/direct-account-core.cjs');
fs.mkdirSync(path.dirname(out), { recursive: true }); fs.writeFileSync(out, result.outputText);
const worker = fs.readFileSync(path.join(root, 'runtime/direct-account-reader-worker.cjs'));
const receipt = { scope: 'Source-linked worker core; semantic types remain a separate required gate.',
  typescript: ts.version, sourceSHA256: hash(source), coreSHA256: hash(fs.readFileSync(out)), workerSHA256: hash(worker) };
fs.writeFileSync(path.join(root, 'runtime/direct-account-build.json'), JSON.stringify(receipt, null, 2) + '\n');
