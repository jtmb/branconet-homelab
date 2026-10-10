import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, rm, writeFile, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { nativeTlsFixture } from "./helpers/native-tls";
import { fakeKubectl } from "./helpers/fake-kubectl";
import { repositoryUrl, publicRepositoryUrl, publicFluxConditions, fluxReadiness } from "../src/lib/flux-input";
import { KubernetesCommandError } from "../src/lib/kubectl-client";

test("repository locations allow credential-free HTTPS/SSH and reject embedded authentication without echo", () => {
  for (const url of ["https://example.invalid/org/repo.git", "ssh://git@example.invalid:2222/org/repo.git", "git@example.invalid:org/repo.git"]) assert.equal(repositoryUrl(url), url);
  const privateMarker = "synthetic-private-url-marker";
  for (const url of [undefined, {}, "http://example.invalid/repo.git", "file:///tmp/repo", `https://${privateMarker}@example.invalid/repo.git`, `https://git:${privateMarker}@example.invalid/repo.git`,
    `ssh://git:${privateMarker}@example.invalid/repo.git`, `https://example.invalid/repo.git?token=${privateMarker}`, `ssh://git@example.invalid/repo.git#${privateMarker}`,
    `git@example.invalid:repo.git?${privateMarker}`, `https://example.invalid/\\${privateMarker}`, " https://example.invalid/repo.git", "https://example.invalid/repo.git\n"])
    assert.throws(() => repositoryUrl(url), error => error instanceof KubernetesCommandError && error.status === 400 && !error.message.includes(privateMarker));
});

test("Flux conditions preserve structured readiness and withhold arbitrary controller values", () => {
  const marker = "synthetic-private-controller-value";
  const conditions = publicFluxConditions([{ type: "Ready", status: "False", reason: marker, message: marker, body: marker }, { type: marker, status: marker, reason: marker }]);
  assert(!JSON.stringify(conditions).includes(marker)); assert.equal(conditions[0].type, "Ready"); assert.equal(conditions[0].status, "False"); assert.equal(conditions[1].type, "Other");
  assert.equal(fluxReadiness({ status: "True", message: marker }), "Ready"); assert.equal(fluxReadiness({ status: "True" }, { status: "False" }), "Not Ready");
  assert.equal(fluxReadiness({ status: "True" }, undefined), "Unknown"); assert.equal(publicRepositoryUrl(`https://${marker}@example.invalid/repo.git`), "");
  assert.equal(publicFluxConditions(Array.from({ length: 100 }, () => ({ type: "Ready", status: "True" }))).length, 32);
  assert.equal(publicFluxConditions([{ type: Object.create(null), status: "True" }])[0].type, "Other");
});

test("private Flux credentials use verified native bodies, never SQLite/argv/errors; imported auth is retained", async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-flux-credentials-"));
  const native = await nativeTlsFixture(dir), cli = await fakeKubectl(dir);
  const changed = { ...cli.env, DATABASE_URL: "file:" + path.join(dir, "metadata.db").replaceAll("\\", "/"), KUBECONFIG: native.config, BORTUS_SECRET_NAMESPACES: "flux-system" };
  const prior = Object.fromEntries(Object.keys(changed).map(key => [key, process.env[key]])); Object.assign(process.env, changed);
  let db: (typeof import("../src/lib/db"))["default"] | undefined;
  try {
    const migrateEnv = { ...process.env }; delete migrateEnv.RUST_LOG;
    execFileSync(process.execPath, [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"], { env: migrateEnv, stdio: "pipe" });
    db = (await import("../src/lib/db")).default;
    const { addRepo, createFluxSecret, getFluxStatus, getGitRepoDetail, listRepos } = await import("../src/lib/flux");
    const credentials = ["synthetic-private-https-token", "synthetic-private-ssh-key\nsecond line\n"];
    for (const [index, authMethod] of ["https", "ssh"].entries()) {
      const name = "private-fixture-" + authMethod, credential = credentials[index];
      // Fake apply fails after native auth creation; inspect retained partial state and fixed failure.
      await assert.rejects(addRepo({ name, url: "https://example.invalid/repo.git", authMethod, authData: credential }), error => error instanceof KubernetesCommandError && !error.message.includes(credential) && !error.message.includes("private-command"));
      const secret = native.objects.get("flux-system/" + name + "-auth")!;
      assert.equal(Buffer.from(secret.data![authMethod === "ssh" ? "identity" : "password"], "base64").toString(), credential);
      const row: { authData: string } = await db.gitRepo.findUniqueOrThrow({ where: { name } }); assert.equal(row.authData, ""); assert(!JSON.stringify(row).includes(credential));
    }
    const before = { calls: native.calls.length, rows: await db.gitRepo.count(), cli: (await cli.calls()).length };
    await assert.rejects(addRepo({ name: "rejected-url", url: "https://synthetic-private-https-token@example.invalid/repo.git", authMethod: "none" }), error => error instanceof KubernetesCommandError && error.status === 400);
    assert.equal(native.calls.length, before.calls); assert.equal(await db.gitRepo.count(), before.rows); assert.equal((await cli.calls()).length, before.cli);
    native.seed("flux-system", "imported-auth", { identity: Buffer.from("synthetic imported identity").toString("base64"), unrelated: Buffer.from("synthetic retained key").toString("base64") });
    const imported = JSON.stringify(native.objects.get("flux-system/imported-auth"));
    const collision = await createFluxSecret("imported", "ssh", credentials[1]); assert.equal(collision.success, false); assert(!JSON.stringify(collision).includes(credentials[1])); assert.equal(JSON.stringify(native.objects.get("flux-system/imported-auth")), imported);
    const argv = JSON.stringify(await cli.calls()); for (const credential of credentials) assert(!argv.includes(credential)); assert(!argv.includes("from-literal"));
    assert.equal(native.calls.filter(call => call.method === "PUT" || call.method === "DELETE").length, 0);
    const marker = "synthetic-private-controller-value", unsafeUrl = `https://${marker}@example.invalid/repo.git`;
    const source = { apiVersion: "source.toolkit.fluxcd.io/v1", kind: "GitRepository", metadata: { name: "legacy-source", uid: "fixture-uid", annotations: { "last-applied": marker }, managedFields: [{ value: marker }] },
      spec: { url: unsafeUrl, secretRef: { name: "imported-auth" }, ref: { branch: "main" } }, status: { conditions: [{ type: "Ready", status: "False", reason: marker, message: marker }] } };
    await writeFile(path.join(cli.bin, "gitrepositories.json"), JSON.stringify({ items: [source] }));
    await writeFile(path.join(cli.bin, "gitrepository.json"), JSON.stringify(source));
    await writeFile(path.join(cli.bin, "kustomizations.json"), '{"items":[]}');
    await writeFile(path.join(cli.bin, "events.json"), `LAST SEEN  TYPE  REASON  OBJECT  MESSAGE\n${marker}  Warning  ${marker}  GitRepository/legacy-source  ${marker}\n2026-10-01T00:00:00Z  Normal  ${marker}  GitRepository/legacy-source  ${marker}\n`);
    const legacy = await db.gitRepo.create({ data: { name: "legacy-source", url: unsafeUrl, authData: marker } });
    for (const projection of [await getFluxStatus(), await getGitRepoDetail("legacy-source"), await listRepos()]) assert(!JSON.stringify(projection).includes(marker));
    const detail = (await getGitRepoDetail("legacy-source"))!;
    assert.equal(detail.url, ""); assert.equal(detail.events[0].lastTimestamp, ""); assert.equal(detail.events[0].age, "Unknown");
    assert.equal(detail.events[1].lastTimestamp, "2026-10-01T00:00:00.000Z"); assert.notEqual(detail.events[1].age, "Unknown");
    assert.equal((await db.gitRepo.findUniqueOrThrow({ where: { id: legacy.id } })).url, unsafeUrl);
    assert.equal(JSON.parse(await readFile(path.join(cli.bin, "gitrepository.json"), "utf8")).spec.secretRef.name, "imported-auth");
  } finally {
    await db?.$disconnect(); await native.close();
    for (const [key, value] of Object.entries(prior)) { if (value === undefined) delete process.env[key]; else process.env[key] = value; }
    if (!path.resolve(dir).startsWith(path.resolve(tmpdir()) + path.sep) || !path.basename(dir).startsWith("bortus-flux-credentials-")) throw new Error("Unsafe fixture cleanup target");
    await rm(dir, { recursive: true, force: true });
  }
});
