import { writeFile } from "node:fs/promises";
import path from "node:path";

/** Disposable standalone server only: make finalization ordering deterministic.
 * Emits fixed operation markers, never request/error bodies or headers. */
export async function nextFinalizeProbe(directory: string, negativeControl = false) {
  const file = path.join(directory, "next-finalize-probe.cjs");
  await writeFile(file, `
const Module = require('node:module');
const load = Module._load;
const bodies = new WeakMap();
if (${JSON.stringify(negativeControl)}) {
  const originalLoader = Module._extensions['.js'];
  Module._extensions['.js'] = function(module, filename) {
    if (filename.replaceAll('\\\\', '/').endsWith('/next/dist/server/next-server.js')) {
      const source = require('node:fs').readFileSync(filename, 'utf8');
      const digest = require('node:crypto').createHash('sha256').update(source).digest('hex');
      if (digest !== '2fbb30d01fdbc56632292cc48b27c8c8bdc0b3c310d4e21d3ffd3c96798fbc18') throw Error('Negative fixture runtime verification failed');
      // Owned test process only: restore exactly the upstream-missing await.
      module._compile(source.replace('                    await requestData.body.finalize();', '                    requestData.body.finalize();'), filename);
    } else originalLoader(module, filename);
  };
}
const NativeRequest = globalThis.Request;
globalThis.Request = class extends NativeRequest {
  constructor(...args) {
    const ownership = bodies.get(args[1]?.body);
    if (ownership) console.log('BORTUS_TEST_OWNED_ROUTE_REQUEST');
    if (ownership?.pending) console.log('BORTUS_TEST_ADAPTER_BEFORE_FINALIZE');
    super(...args);
  }
};
const wrapped = new WeakMap();
Module._load = function(id, parent, main) {
  const result = load.apply(this, arguments);
  const resolved = Module._resolveFilename(id, parent).replaceAll('\\\\', '/');
  if (resolved.endsWith('/next/dist/server/body-streams.js')) {
    if (!wrapped.has(result)) wrapped.set(result, { ...result, getCloneableBody(...args) {
      const body = result.getCloneableBody(...args);
      const ownership = { pending: false };
      bodies.set(args[0], ownership);
      const finalize = body.finalize.bind(body);
      body.finalize = async () => {
        ownership.pending = true;
        console.log('BORTUS_TEST_FINALIZE_BEGIN');
        try {
          await new Promise(resolve => setTimeout(resolve, 100));
          await finalize();
        } finally {
          ownership.pending = false;
          console.log('BORTUS_TEST_FINALIZE_DONE');
        }
      };
      return body;
    } });
    return wrapped.get(result);
  }
  if (resolved.endsWith('/next/dist/server/web/spec-extension/adapters/next-request.js') && !wrapped.has(result)) {
    const adapter = result.NextRequestAdapter;
    const construct = adapter.fromNodeNextRequest;
    adapter.fromNodeNextRequest = function(...args) {
      if (bodies.get(args[0]?.body)?.pending) console.log('BORTUS_TEST_ADAPTER_BEFORE_FINALIZE');
      return construct.apply(this, args);
    };
    wrapped.set(result, result);
  }
  return result;
};
`);
  return file;
}
