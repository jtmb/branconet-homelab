import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';

const ts = createRequire(import.meta.url)('typescript');
assert.equal(process.version, 'v22.23.3');
assert.equal(ts.version, '5.9.3');
export function declaration(relative, hash, name, expected) {
  const source = readFileSync(new URL(`../../src/lib/${relative}`, import.meta.url), 'utf8').replaceAll('\r\n', '\n');
  assert.equal(createHash('sha256').update(source).digest('hex'), hash);
  const ast = ts.createSourceFile(relative, source, ts.ScriptTarget.ES2022, true);
  const nodes = ast.statements.filter(node => (ts.isClassDeclaration(node) || ts.isFunctionDeclaration(node)) && node.name?.text === name);
  assert.equal(nodes.length, 1);
  const text = nodes[0].getText(ast);
  assert.equal(text, expected);
  const compiled = ts.transpileModule(text.replace(/^export /, ''), { reportDiagnostics: true,
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None, useDefineForClassFields: true } });
  assert.equal(compiled.diagnostics?.length ?? 0, 0);
  // Only this exact declaration is evaluated. No application import,
  // initializer, real Error/Next/DB/account implementation is evaluated.
  return bindings => vm.runInNewContext(`(${compiled.outputText.trim()})`, bindings, { timeout: 1000 });
}
