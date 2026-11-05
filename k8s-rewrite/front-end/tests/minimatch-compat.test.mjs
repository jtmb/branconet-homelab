import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import minimatchDefault, { minimatch, Minimatch } from "minimatch";
import { patchMinimatch } from "../scripts/patch-minimatch-compat.mjs";

const require = createRequire(import.meta.url);

test("fixed minimatch retains callable CommonJS and default/named ESM imports", () => {
  const legacy = require("minimatch");
  assert.equal(require("minimatch/package.json").version, "11.0.1");
  assert.equal(typeof legacy, "function");
  assert.equal(legacy, legacy.minimatch);
  assert.equal(minimatchDefault, minimatch);
  for (const match of [legacy, minimatchDefault]) {
    assert.equal(match("src/app/page.tsx", "src/**/*.{ts,tsx}"), true);
    assert.equal(match("docs/page.md", "src/**/*.{ts,tsx}"), false);
    assert.equal(match.defaults({ dot: true })(".config.js", "*.js"), true);
  }
  assert.equal(new Minimatch("**/*.tsx", { dot: true }).match("src/.hidden/page.tsx"), true);
  assert.equal(legacy.makeRe, undefined, "obsolete regex compilation is not restored");
});

test("import rule enforces forbidden internal paths with the fixed matcher", () => {
  const { Linter } = require("eslint");
  const plugin = require("eslint-plugin-import");
  const linter = new Linter();
  const config = [{ plugins: { imports: plugin }, rules: {
    "imports/no-internal-modules": ["error", { forbid: ["**/internal/**"] }],
  } }];
  for (const statement of ["import value from './internal/private.js';", "const value = require('./internal/private.js');"]) {
    const errors = linter.verify(statement, config, { filename: "src/probe.js" });
    assert.equal(errors.length, 1);
    assert.equal(errors[0].ruleId, "imports/no-internal-modules");
    assert.match(errors[0].message, /is not allowed/);
  }
  assert.deepEqual(linter.verify("import value from './public/open.js';", config, { filename: "src/probe.js" }), []);
});

test("authenticated compatibility patch is idempotent after installation", () => {
  assert.deepEqual(patchMinimatch(), { files: 3, changed: 0 });
});
