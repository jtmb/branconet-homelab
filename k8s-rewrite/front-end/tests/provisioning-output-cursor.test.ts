import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import type { ChildProcess } from "node:child_process";
import { DatabaseSync } from "node:sqlite";
import { NextRequest, NextResponse } from "next/server";
import ts from "typescript";
import { ansibleSelection, AnsibleSelectionError } from "../src/lib/ansible-selection";
import { observeAnsibleProcess } from "../src/lib/ansible-progress";
import { readJobSlice } from "../src/lib/job-output";
import { createJobStream } from "../src/lib/job-stream";

const preparation = "[Generated lookup references and inventory]\n";
const flush = () => new Promise<void>(resolve => setImmediate(resolve));
type StoredJob = { id: string; output: string; status: string; finishedAt: string | null };

// Execute the actual route/producer/stream against SQLite's mapped jobs table.
// Only operator admission, preparation, process creation and the clock are controlled.
function fixture() {
  const db = new DatabaseSync(":memory:");
  db.exec("CREATE TABLE jobs (id TEXT PRIMARY KEY, output TEXT NOT NULL, status TEXT NOT NULL, finishedAt TEXT)");
  const activeJobs = new Map<string, AbortController>();
  const timers = new Map<number, { callback: () => void; delay: number }>();
  let timer = 0, failStart = false, releaseRunner!: () => void, terminalSaved!: () => void;
  const runnerGate = new Promise<void>(resolve => { releaseRunner = resolve; });
  const finalized = new Promise<void>(resolve => { terminalSaved = resolve; });
  const proc = Object.assign(new EventEmitter(), { stdout: new PassThrough(), stderr: new PassThrough(), kill: () => true });
  const emitter = observeAnsibleProcess(proc as unknown as ChildProcess);
  const read = () => db.prepare("SELECT id, output, status, finishedAt FROM jobs WHERE id = 'fixture-job'").get() as StoredJob;
  const query = (strings: TemplateStringsArray, values: unknown[]) => {
    const parameters = values.map(value => {
      assert(typeof value === "string" || typeof value === "number");
      return value;
    });
    return { statement: db.prepare(strings.join("?")), parameters };
  };
  const client = {
    $queryRaw: async (strings: TemplateStringsArray, ...values: unknown[]) => {
      const { statement, parameters } = query(strings, values);
      return statement.all(...parameters);
    },
  } as unknown as Parameters<typeof readJobSlice>[2];
  const prisma = {
    job: {
      create: async ({ data }: { data: { output: string; status: string } }) => {
        db.prepare("INSERT INTO jobs (id, output, status) VALUES (?, ?, ?)").run("fixture-job", data.output, data.status);
        return { id: "fixture-job" };
      },
      update: async ({ data }: { data: { output: string; status: string; finishedAt: Date } }) => {
        db.prepare("UPDATE jobs SET output = ?, status = ?, finishedAt = ? WHERE id = 'fixture-job'")
          .run(data.output, data.status, data.finishedAt.toISOString());
        terminalSaved();
        return read();
      },
      findUnique: async () => read(),
    },
    $executeRaw: async (strings: TemplateStringsArray, ...values: unknown[]) => {
      const { statement, parameters } = query(strings, values);
      return statement.run(...parameters).changes;
    },
    clusterState: { upsert: async () => ({}) },
  };
  const dependencies: Record<string, unknown> = {
    "next/server": { NextRequest, NextResponse },
    "@/lib/db": { default: prisma },
    "@/lib/ansible": { runAnsiblePlaybook: async () => {
      await runnerGate;
      if (failStart) throw new Error("Synthetic process admission failure");
      return emitter;
    } },
    "@/lib/active-jobs": { activeJobs },
    "@/lib/sync-vars": { syncVarsToYAML: async () => {}, syncNodesFromVars: async () => {}, syncInventoryToFile: async () => {} },
    "@/lib/cluster-cache": { invalidateCache: () => {} },
    "@/lib/permissions": { requireOperator: async () => ({ id: "fixture-admin" }) },
    "@/lib/runtime-capabilities": { runtimeCapabilities: () => ({ provisioning: true }) },
    "@/lib/ansible-selection": { ansibleSelection, AnsibleSelectionError },
  };
  const exports: Record<string, unknown> = {};
  const source = readFileSync(resolve("src/app/api/deploy/start/route.ts"), "utf8");
  runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, {
    exports, require: (name: string) => { assert(Object.hasOwn(dependencies, name)); return dependencies[name]; },
    AbortController, console,
    setTimeout: (callback: () => void, delay: number) => { const id = ++timer; timers.set(id, { callback, delay }); return id; },
    clearTimeout: (id: number) => timers.delete(id),
  });
  return {
    read, activeJobs, timers, finalized,
    start: () => (exports.POST as (request: NextRequest) => Promise<Response>)(new NextRequest("http://localhost/api/deploy/start", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ playbook: "site.yml", roles: ["kubernetes"] }),
    })),
    stream: () => createJobStream({ signal: new AbortController().signal, cursor: 0, authorize: async () => true,
      load: cursor => readJobSlice("fixture-job", cursor, client) }).getReader(),
    async begin() { releaseRunner(); await flush(); },
    progress() {
      proc.stderr.write("synthetic-private-output\n");
      proc.stdout.write("BORTUS_PROGRESS_V1 start\nBORTUS_PROGRESS_V1 role:kubernetes:running\n");
    },
    async flushProgress() {
      assert.equal(timers.size, 1);
      const [id, entry] = [...timers][0]; assert.equal(entry.delay, 500);
      timers.delete(id); entry.callback(); await flush();
    },
    async complete() { proc.stdout.write("BORTUS_PROGRESS_V1 complete:success\n"); proc.emit("close", 0); await finalized; await flush(); },
    async refuseStart() { failStart = true; releaseRunner(); await finalized; await flush(); },
    dispose() { proc.stdout.destroy(); proc.stderr.destroy(); db.close(); },
  };
}

async function frame(reader: ReadableStreamDefaultReader<Uint8Array>) {
  for (;;) {
    const value = await reader.read();
    if (value.done) return undefined;
    const text = new TextDecoder().decode(value.value);
    if (text.startsWith(":")) continue;
    return JSON.parse(text.match(/data: (.+)\n/)![1]) as { output: string; cursor: number; done: boolean; reset?: boolean };
  }
}

test("provisioning cursor preserves preparation and real producer output across SQLite flush and terminal success", { timeout: 5000 }, async () => {
  const f = fixture(); let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  try {
    assert.equal((await f.start()).status, 200);
    reader = f.stream(); const first = await frame(reader);
    assert(first); assert.equal(first.output, preparation); assert.equal(first.cursor, preparation.length);
    await f.begin(); f.progress(); await f.flushProgress();
    const intermediate = f.read();
    assert(intermediate.output.startsWith(first.output));
    assert.equal(intermediate.output.includes("[Raw runner output withheld]"), true);
    assert.equal(intermediate.status, "running"); assert.equal(intermediate.finishedAt, null);
    await f.complete(); const final = f.read();
    assert(final.output.startsWith(intermediate.output)); assert.equal(final.status, "success"); assert(final.finishedAt);
    let reconstructed = first.output, cursor = first.cursor, completed = false;
    for (;;) {
      const next = await frame(reader); if (!next) break;
      assert(!next.reset); assert(next.cursor >= cursor); cursor = next.cursor; reconstructed += next.output;
      if (next.done) completed = true;
    }
    assert.equal(reconstructed, final.output);
    assert(reconstructed.includes("[Raw runner output withheld]")); assert(reconstructed.includes("[Provisioning completed]"));
    assert(!reconstructed.includes("synthetic-private-output")); assert.equal(completed, true);
    assert.equal(f.timers.size, 0); assert.equal(f.activeJobs.size, 0);
  } finally { await reader?.cancel(); f.dispose(); }
});

test("provisioning cursor preserves preparation when the runner cannot start", { timeout: 5000 }, async () => {
  const f = fixture(); let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  try {
    assert.equal((await f.start()).status, 200);
    reader = f.stream(); const first = await frame(reader); assert(first); assert.equal(first.output, preparation);
    await f.refuseStart(); const final = f.read();
    assert.equal(final.output, preparation + "[Provisioning runner could not start]\n");
    const last = await frame(reader); assert(last); assert(!last.reset); assert.equal(last.done, true);
    assert.equal(first.output + last.output, final.output); assert.equal(final.status, "failed"); assert(final.finishedAt);
    assert.equal((await reader.read()).done, true); assert.equal(f.timers.size, 0); assert.equal(f.activeJobs.size, 0);
  } finally { await reader?.cancel(); f.dispose(); }
});
