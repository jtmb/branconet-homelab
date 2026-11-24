import { test } from "node:test";
import assert from "node:assert/strict";
import { writeFile, readFile } from "node:fs/promises";
import { systemReportServer } from "./helpers/system-report-server";
import type { SystemReport } from "../src/lib/system-report-types";

test("production report HTTP enforces fresh authority, deduplicates cached scans and cancels exact jobs", { timeout: 60000 }, async () => {
  const fixture = await systemReportServer();
  const request = (method: string, user = "operator", suffix = "") => fetch(`${fixture.base}/api/system-report${suffix}`, { method, headers: user ? { cookie: fixture.cookies[user] } : {} });
  async function settled(): Promise<SystemReport> {
    for (let i = 0; i < 100; i++) {
      const report: SystemReport = await (await request("GET")).json();
      if (report.job?.state !== "running") return report;
      await new Promise(r => setTimeout(r, 50));
    }
    throw Error("Fixture report did not settle");
  }
  try {
    for (const method of ["GET", "POST", "DELETE"]) assert.equal((await request(method, "")).status, 401);
    for (const user of ["readonly", "scoped"]) {
      assert.equal((await request("GET", user)).status, 200);
      assert.equal((await request("POST", user)).status, 403); assert.equal((await request("DELETE", user)).status, 403);
    }
    const response = await request("GET"); assert.match(response.headers.get("cache-control")!, /no-store/);
    const initial: SystemReport = await response.json(); assert.equal(initial.runningContainers, 3); assert.equal(initial.images.length, 2);
    assert.equal(initial.images[0].state, "unscanned"); assert.equal(initial.images[0].consumers.length, 2); assert.equal(initial.images[1].state, "unsupported");
    assert.equal((await request("POST")).status, 202);
    const complete = await settled(); assert.equal(complete.images[0].state, "complete"); assert.equal(complete.images[0].findings.length, 2);
    assert.equal(complete.images[0].findings[1].url, null); assert.equal((await readFile(fixture.calls, "utf8")).trim().split("\n").length, 1);
    assert.equal((await request("POST")).status, 202); await settled(); assert.equal((await readFile(fixture.calls, "utf8")).trim().split("\n").length, 1);
    // Change only disposable DB metadata to invalidate the digest cache and hold a real subprocess.
    await writeFile(`${fixture.cache}/db/metadata.json`, JSON.stringify({ Version: 2, UpdatedAt: new Date().toISOString(), NextUpdate: new Date(Date.now() + 3600000).toISOString() }));
    await writeFile(fixture.mode, "hold");
    const [one, two] = await Promise.all([request("POST"), request("POST")]);
    const first = await one.json(), second = await two.json(); assert.equal(first.job.id, second.job.id);
    assert.equal((await request("DELETE", "operator", "?jobId=wrong")).status, 409);
    assert.equal((await request("DELETE", "operator", `?jobId=${encodeURIComponent(first.job.id)}`)).status, 202);
    const cancelled = await settled(); assert.equal(cancelled.job!.state, "cancelled"); assert.equal(cancelled.images[0].state, "cancelled");
    await writeFile(fixture.mode, "error"); assert.equal((await request("POST")).status, 202);
    const failed = await settled(); assert.equal(failed.images[0].state, "error"); assert.ok(!JSON.stringify(failed).includes("private-fixture"));
    await fixture.db.user.update({ where: { username: "operator" }, data: { engineAdmin: false } });
    assert.equal((await request("POST")).status, 403);
    await fixture.db.user.update({ where: { username: "readonly" }, data: { sessionVersion: 1 } });
    assert.equal((await request("GET", "readonly")).status, 401);
    assert.ok(!fixture.logs().includes("private-fixture-error"));
  } finally { await fixture.stop(); }
});
