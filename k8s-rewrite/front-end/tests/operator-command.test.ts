import { test } from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { KubernetesCommandError, operatorCommandFailure } from "../src/lib/kubectl-client";
import { clusterRoute } from "../src/lib/cluster-http";

const execute = promisify(execFile);
const marker = "PUBLIC_OPERATOR_FAILURE_MARKER";

async function failedCommand(command: string, options: { timeout?: number; maxBuffer?: number } = {}) {
  try {
    await execute(process.execPath, ["-e", command], { timeout: 2000, maxBuffer: 1024, ...options });
    assert.fail("command unexpectedly succeeded");
  } catch (error) {
    assert.notEqual((error as Error).name, "AssertionError");
    return operatorCommandFailure(error);
  }
}

test("actual exit1 stdout, stderr, both and neither produce fixed502 without captured output", async () => {
  for (const [stdout, stderr] of [[true, false], [false, true], [true, true], [false, false]]) {
    const script = `${stdout ? `process.stdout.write(${JSON.stringify(marker)});` : ""}${stderr ? `process.stderr.write(${JSON.stringify(marker)});` : ""}process.exitCode=1;`;
    const error = await failedCommand(script);
    assert.ok(error instanceof KubernetesCommandError);
    assert.equal(error.status, 502);
    assert.equal(error.message, "Operator command failed");
    const response = await clusterRoute(async () => { throw error; });
    assert.equal(response.status, 502);
    assert.deepEqual(await response.json(), { error: "Operator command failed" });
    assert.ok(!JSON.stringify(error).includes(marker));
  }
});

test("successful child stdout is unchanged and successful stderr does not become stdout", async () => {
  const result = await execute(process.execPath, ["-e", `process.stdout.write('PUBLIC_SUCCESS\\n');process.stderr.write(${JSON.stringify(marker)});`]);
  assert.equal(result.stdout, "PUBLIC_SUCCESS\n");
  assert.equal(result.stderr, marker);
});

test("actual timeout, missing executable and stdout/stderr bounds remain typed and redacted", async () => {
  const timeout = await failedCommand("setInterval(()=>{},1000)", { timeout: 100 });
  assert.equal(timeout.status, 504);
  assert.equal(timeout.message, "Operator command timed out");
  for (const stream of ["stdout", "stderr"]) {
    const overflow = await failedCommand(`process.${stream}.write(${JSON.stringify(marker)}.repeat(10000));`);
    assert.equal(overflow.status, 502);
    assert.equal(overflow.message, "Operator command response exceeds the size limit");
    assert.ok(!JSON.stringify(overflow).includes(marker));
  }
  let missing: unknown;
  try { await execute(`${process.execPath}.bortus-nonexistent-command`, []); }
  catch (error) { missing = error; }
  assert.ok(missing);
  const unavailable = operatorCommandFailure(missing);
  assert.equal(unavailable.status, 503);
  assert.equal(unavailable.message, "Operator shell is unavailable");
});
