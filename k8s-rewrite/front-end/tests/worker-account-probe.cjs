'use strict';
// Public fixture instrumentation only; no values, SQL text, arguments or errors are recorded.
const { workerData, parentPort } = require('node:worker_threads');
const { DatabaseSync, StatementSync } = require('node:sqlite');
const counts = new Int32Array(workerData.publicCounts);
const clocks = new BigInt64Array(workerData.publicCounts, 64, 2);
Atomics.store(clocks, 0, process.hrtime.bigint()); Atomics.store(counts, 8, 1);
const { DirectAccountReader } = require(require('node:path').join(process.cwd(), 'runtime/direct-account-core.cjs'));
const idle = DirectAccountReader.prototype.whenIdle, settlement = DirectAccountReader.prototype.settlementIdentity;
DirectAccountReader.prototype.whenIdle = function (...args) {
  Atomics.add(counts, 9, 1); Atomics.add(counts, 10, this.activity().active);
  return Reflect.apply(idle, this, args);
};
DirectAccountReader.prototype.settlementIdentity = function (...args) {
  Atomics.add(counts, 13, 1); Atomics.add(counts, 15, this.activity().active);
  return Reflect.apply(settlement, this, args);
};
const post = parentPort.postMessage;
parentPort.postMessage = function (...args) {
  if (args[0]?.kind === 'settled') Atomics.add(counts, 11, 1);
  if (args[0]?.kind === 'closed' || args[0]?.kind === 'discarded') Atomics.add(counts, 12, 1);
  return Reflect.apply(post, this, args);
};
const identity = DirectAccountReader.prototype.identity, schedule = global.setImmediate;
let identityDepth = 0, currentIdentity = 0;
DirectAccountReader.prototype.identity = function (...args) {
  identityDepth++; currentIdentity = Atomics.add(counts, 2, 1) + 1;
  let result;
  try { result = Reflect.apply(identity, this, args); }
  catch (error) { identityDepth--; throw error; }
  void result.then(() => { identityDepth--; }, () => { identityDepth--; });
  return result;
};
global.setImmediate = function (callback, ...args) {
  if (!identityDepth) return Reflect.apply(schedule, this, [callback, ...args]);
  const ordinal = currentIdentity;
  return Reflect.apply(schedule, this, [function (...actualArgs) {
    const receiver = this; Atomics.add(counts, 3, 1);
    function forward() {
      if (Atomics.load(counts, 4) === ordinal && Atomics.load(counts, 5) === 0) {
        Atomics.store(counts, 6, ordinal); schedule(forward); return;
      }
      Atomics.add(counts, 7, 1); Reflect.apply(callback, receiver, actualArgs);
    }
    forward();
  }, ...args]);
};
const get = StatementSync.prototype.get, close = DatabaseSync.prototype.close;
StatementSync.prototype.get = function (...args) {
  Atomics.add(counts, 0, 1); return Reflect.apply(get, this, args);
};
DatabaseSync.prototype.close = function (...args) {
  try { return Reflect.apply(close, this, args); } finally { Atomics.add(counts, 1, 1); }
};
