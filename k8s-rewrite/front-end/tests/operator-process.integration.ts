import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { executeOperatorCommand } from "../src/lib/operator-command";

async function state(pid: number) {
  try {
    const text = await readFile(`/proc/${pid}/stat`, "utf8");
    const parts = text.slice(text.lastIndexOf(") ") + 2).split(" ");
    return { state: parts[0], group: Number(parts[2]), start: parts[19] };
  } catch (error) {
    assert.equal((error as NodeJS.ErrnoException).code, "ENOENT");
    return null;
  }
}

test("owned POSIX timeout and overflow close descendants including TERM-ignoring groups", { timeout: 12000 }, async () => {
  assert.equal(process.platform, "linux", "Actual production process-tree fixture requires Linux");
  const dir = await mkdtemp(join(tmpdir(), "bortus-owned-shell-"));
  try {
    for (const mode of ["timeout", "ignore-term", "overflow"] as const) {
      const file = join(dir, `${mode}.pid`);
      const script = `${mode === "ignore-term" ? "trap '' TERM; " : ""}sleep 60 & printf '%s %s' "$$" "$!" > ${JSON.stringify(file)}; ${mode === "overflow" ? "sleep 0.2; printf '%*s' 4097 ''; " : ""}wait`;
      const result = executeOperatorCommand(script, { encoding: "utf8", timeout: 1500, maxBuffer: 4096 });
      const rejected = assert.rejects(result, { status: mode === "overflow" ? 502 : 504 });
      let identities: number[] | undefined;
      for (let i = 0; i < 100; i++) {
        try { identities = (await readFile(file, "utf8")).split(" ").map(Number); break; }
        catch (error) { assert.equal((error as NodeJS.ErrnoException).code, "ENOENT"); }
        await new Promise(resolve => setTimeout(resolve, 10));
      }
      assert.ok(identities && identities.length === 2 && identities.every(pid => Number.isSafeInteger(pid) && pid > 1));
      const [parent, descendant] = identities;
      const before = await state(descendant);
      assert.ok(before);
      assert.equal(before.group, parent, "descendant was outside this invocation-owned process group");
      await rejected;
      const after = await state(descendant);
      assert.ok(!after || after.start !== before.start || after.state === "Z", "same-identity executable descendant survived bounded group closure");
      const leader = await state(parent);
      assert.ok(!leader || leader.state === "Z", "owned group leader remained executable");
    }
    assert.equal(await executeOperatorCommand("printf 'PUBLIC_SUCCESS\\n'; printf 'PUBLIC_STDERR' >&2", { encoding: "utf8", timeout: 1500, maxBuffer: 4096 }), "PUBLIC_SUCCESS\n");
    await assert.rejects(executeOperatorCommand("exit 1", { encoding: "utf8", timeout: 1500, maxBuffer: 4096 }), { status: 502, message: "Operator command failed" });
  } finally {
    assert.equal(join(tmpdir(), dir.split(/[\\/]/).at(-1)!), dir);
    await rm(dir, { recursive: true, force: true });
  }
});

test("operator spawn preserves UTF8 stdout and independent exact byte ceilings", { timeout: 6000 }, async () => {
  const options = { encoding: "utf8" as const, timeout: 1500, maxBuffer: 8 };
  assert.equal(await executeOperatorCommand("printf '\\360\\237'; sleep 0.05; printf '\\230\\200abcd'", options), "😀abcd");
  assert.equal(await executeOperatorCommand("printf '12345678'; printf 'abcdefgh' >&2", options), "12345678");
  for (const command of ["printf '123456789'", "printf '123456789' >&2"]) {
    await assert.rejects(executeOperatorCommand(command, options), { status: 502, message: "Operator command response exceeds the size limit" });
  }
  await assert.rejects(executeOperatorCommand("true", { ...options, env: { NODE_ENV: "test", PATH: "/bortus-owned-missing-bash" } }), { status: 503, message: "Operator shell is unavailable" });
});
