'use strict';
const assert=require('node:assert/strict');
const output=process.env.BORTUS_NATIVE_DIAGNOSTIC_OUTPUT;
assert(output&&output.startsWith('/results/'));
require('./observer.cjs').install(output);
