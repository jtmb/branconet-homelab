import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { mkdtemp, writeFile, rm, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import net, { type AddressInfo } from "node:net";
import { once } from "node:events";
import { PrismaClient } from "@prisma/client";
import { fakeKubectl } from "./helpers/fake-kubectl";

test(
  "production HTTP auth, metadata migration, quarantined DB rows and unavailable native lookup",
  { timeout: 60000 },
  async (context) => {
    const dir = await mkdtemp(path.join(tmpdir(), "bortus-http-test-"));
    const database = `file:${path.join(dir, "test.db").replaceAll("\\", "/")}`;
    const env: NodeJS.ProcessEnv & {
      KUBECONFIG: string;
      BORTUS_SECRET_ALIASES_FILE: string;
    } = {
      ...process.env,
      DATABASE_URL: database,
      BOTRUS_JWT_SECRET: "fake-test-signing-material-only",
      BOTRUS_SECRETS_KEY: "fake-lookup-token",
      BORTUS_SECRET_NAMESPACES: "apps",
      BORTUS_DISABLE_PROVISIONING: "true",
      KUBECONFIG: path.join(dir, "config"),
      BORTUS_SECRET_ALIASES_FILE: path.join(dir, "aliases.json"),
      NODE_ENV: "production",
      HOSTNAME: "127.0.0.1",
    };
    // Some host RUST_LOG settings are incompatible with the Prisma schema engine logger.
    delete env.RUST_LOG;
    delete env.KUBERNETES_SERVICE_HOST;
    let child: ChildProcess | undefined,
      db: PrismaClient | undefined,
      output = "";
    try {
      const fixture = await fakeKubectl(dir);
      Object.assign(env, fixture.env);
      const createdAt = "2026-10-01T00:00:00Z";
      const applicationPod = { metadata: { name: "api-worker-rs-0", namespace: "apps", uid: "pod-worker", creationTimestamp: createdAt, labels: { app: "worker", tier: "backend" }, ownerReferences: [{ kind: "ReplicaSet", uid: "rs-worker", controller: true }] }, spec: { nodeName: "test-node", containers: [{ name: "app", image: "example.invalid/test:v1" }] }, status: { phase: "Running", containerStatuses: [{ name: "app", ready: true, restartCount: 7 }], initContainerStatuses: [{ name: "init", restartCount: 2 }] } };
      const fixtureData = {
        nodes: { items: [{ metadata: { name: "test-node", uid: "node-test" }, status: { conditions: [{ type: "Ready", status: "True" }] } }] },
        pods: { items: [applicationPod, { metadata: { name: "dns", namespace: "kube-system", labels: { app: "dns" } } }, { metadata: { name: "infra-override", namespace: "apps", labels: { "branconet.io/type": "system" } } }] },
        deployments: { items: [
          { metadata: { name: "api", namespace: "apps", uid: "dep-api", generation: 1 }, spec: { replicas: 0 }, status: { observedGeneration: 1 } },
          { metadata: { name: "api-worker", namespace: "apps", uid: "dep-worker", generation: 2 }, spec: { replicas: 2 }, status: { observedGeneration: 1, replicas: 1, readyReplicas: 1 } },
        ] },
        replicasets: { items: [{ metadata: { name: "api-worker-rs", namespace: "apps", uid: "rs-worker", ownerReferences: [{ kind: "Deployment", uid: "dep-worker", controller: true }] } }] },
      };
      for (const [resource, data] of Object.entries(fixtureData)) await writeFile(path.join(fixture.bin, `${resource}.json`), JSON.stringify(data));
      const cli = path.resolve("node_modules/prisma/build/index.js");
      execFileSync(process.execPath, [cli, "migrate", "deploy"], {
        env,
        stdio: "pipe",
      });
      const diff = execFileSync(
        process.execPath,
        [
          cli,
          "migrate",
          "diff",
          "--from-url",
          database,
          "--to-schema-datamodel",
          "prisma/schema.prisma",
          "--script",
        ],
        { env, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
      );
      assert.ok(diff.includes("empty migration"));
      db = new PrismaClient({ datasources: { db: { url: database } } });
      await db.variable.createMany({
        data: [
          {
            key: "k8s_version",
            value: "v-test",
            category: "kubernetes",
            encrypted: false,
          },
          {
            key: "secret_apps_vpn_openvpn_user",
            value: "fake stale DB marker",
            category: "secret",
            encrypted: true,
          },
          {
            key: "unmapped_password",
            value: "fake unmapped DB marker",
            category: "general",
            encrypted: false,
          },
        ],
      });
      await writeFile(
        env.KUBECONFIG,
        JSON.stringify({
          apiVersion: "v1",
          kind: "Config",
          clusters: [
            { name: "test", cluster: { server: "https://127.0.0.1:1" } },
          ],
          users: [{ name: "test", user: { token: "fake-native-token" } }],
          contexts: [
            { name: "test", context: { cluster: "test", user: "test" } },
          ],
          "current-context": "test",
        }),
      );
      await writeFile(
        env.BORTUS_SECRET_ALIASES_FILE,
        JSON.stringify([
          {
            alias: "secret_apps_vpn_openvpn_user",
            namespace: "apps",
            name: "vpn",
            key: "openvpn_user",
          },
        ]),
      );
      const holder = net.createServer();
      holder.listen(0, "127.0.0.1");
      await once(holder, "listening");
      const port = (holder.address() as AddressInfo).port;
      await new Promise<void>((resolve) => holder.close(() => resolve()));
      child = spawn(
        process.execPath,
        [path.resolve(".next/standalone/server.js")],
        {
          env: { ...env, PORT: String(port) },
          stdio: ["ignore", "pipe", "pipe"],
        },
      );
      child.stdout?.on("data", (chunk) => {
        output += chunk.toString();
      });
      child.stderr?.on("data", (chunk) => {
        output += chunk.toString();
      });
      const base = `http://127.0.0.1:${port}`;
      let started = false;
      for (let i = 0; i < 60; i++) {
        try {
          if ((await fetch(`${base}/api/health/live`)).ok) {
            started = true;
            break;
          }
        } catch {}
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      assert.ok(started, "production server did not start");
      assert.equal((await fetch(`${base}/api/secrets`)).status, 401);
      assert.equal(
        (await fetch(`${base}/api/vars/lookup?key=k8s_version`)).status,
        401,
      );
      const request = (
        url: string,
        method = "GET",
        data?: unknown,
        cookie?: string,
      ) =>
        fetch(`${base}${url}`, {
          method,
          headers: {
            ...(cookie ? { cookie } : {}),
            ...(data === undefined
              ? {}
              : { "Content-Type": "application/json" }),
          },
          body: data === undefined ? undefined : JSON.stringify(data),
        });
      // Exercise the actual route's bootstrap race before the remaining fixture setup.
      const bootstrap = await Promise.all(Array.from({ length: 4 }, (_, i) => request("/api/auth/register", "POST", {
        username: `race_bootstrap_${i}`, password: "fake-test-password",
      })));
      assert.equal(bootstrap.filter(response => response.status === 201).length, 1);
      assert.equal(bootstrap.filter(response => response.status === 403).length, 3);
      assert.equal(await db.user.count({ where: { role: "write" } }), 1);
      await db.user.deleteMany(); // Disposable fixture DB only; start the normal flow below.
      assert.equal((await request("/api/cluster/info-extra")).status, 401);
      const first = await request("/api/auth/register", "POST", {
        username: "testwriter",
        password: "fake-test-password",
      });
      assert.equal(first.status, 201);
      const writer = first.headers.get("set-cookie")!.split(";")[0];
      assert.equal(
        (await db.user.findUnique({ where: { username: "testwriter" } }))?.role,
        "write",
      );
      await db.appSetting.upsert({
        where: { key: "allow_registration" },
        create: { key: "allow_registration", value: "true" },
        update: { value: "true" },
      });
      const second = await request("/api/auth/register", "POST", {
        username: "testreader",
        password: "fake-test-password",
      });
      assert.equal(second.status, 201);
      const reader = second.headers.get("set-cookie")!.split(";")[0];
      assert.equal(
        (await db.user.findUnique({ where: { username: "testreader" } }))?.role,
        "readonly",
      );
      const callCount = (await fixture.calls()).length;
      const invalidStorage = await request("/api/cluster/volumes?kind=wrong", "GET", undefined, writer);
      assert.equal(invalidStorage.status, 400);
      assert.equal((await fixture.calls()).length, callCount);
      assert.equal((await request("/api/nodes", "POST", { hostname: "bad host", ipAddress: "invalid" }, writer)).status, 400);
      assert.equal((await request("/api/nodes", "POST", { hostname: "inventory-one", ipAddress: "127.0.0.3", role: "worker" }, reader)).status, 403);
      const inventoryCreate = await request("/api/nodes", "POST", { name: "", hostname: "inventory-one", ipAddress: "127.0.0.3", role: "worker" }, writer);
      assert.equal(inventoryCreate.status, 200);
      const inventoryNode = await inventoryCreate.json();
      assert.equal((await request("/api/nodes/" + inventoryNode.id, "PUT", { hostname: "inventory-renamed", ipAddress: "::1", role: "worker" }, writer)).status, 200);
      assert.equal(await db.node.count({ where: { hostname: "inventory-one" } }), 0);
      assert.equal(await db.node.count({ where: { hostname: "inventory-renamed" } }), 1);
      assert.equal((await request("/api/nodes/" + inventoryNode.id, "DELETE", undefined, reader)).status, 403);
      assert.equal((await request("/api/nodes/" + inventoryNode.id, "DELETE", undefined, writer)).status, 200);
      assert.equal((await request("/api/nodes/" + inventoryNode.id, "DELETE", undefined, writer)).status, 404);
      for (const resource of ["--raw=/api/v1/secrets", "apps --server=https://example.invalid", "a..b", "apps/name"]) {
        const response = await request(`/api/cluster/namespaces/${encodeURIComponent(resource)}/yaml`, "GET", undefined, reader);
        assert.equal(response.status, 400);
      }
      for (const replicas of [-1, 1.5, 10001, null]) {
        assert.equal((await request("/api/cluster/deployments/apps/demo/scale", "POST", { replicas }, writer)).status, 400);
      }
      assert.equal((await fixture.calls()).length, callCount, "invalid input spawned kubectl");
      const yamlRead = await request("/api/cluster/namespaces/apps/yaml", "GET", undefined, reader);
      assert.equal(yamlRead.status, 200);
      assert.ok((await yamlRead.json()).yaml.includes("kind: Namespace"));
      const argv = (await fixture.calls()).at(-1)!;
      assert.deepEqual(argv.slice(2), ["get", "namespace", "apps", "-o", "yaml"]);
      for (const [url, method, data] of [
        ["/api/cluster/deployments/apps/demo/scale", "POST", { replicas: 0 }],
        ["/api/cluster/deployments/apps/demo/action", "POST", { action: "restart" }],
        ["/api/cluster/pods/apps/demo/delete", "DELETE", undefined],
        ["/api/cluster/deployments/apps/demo/delete", "DELETE", undefined],
        ["/api/cluster/namespaces/apps/delete", "DELETE", undefined],
        ["/api/cluster/namespaces/apps/yaml", "PUT", { yaml: 'apiVersion: v1\nkind: Namespace\nmetadata:\n  name: apps\n  resourceVersion: "1"\n' }],
      ] as const) {
        const response = await request(url, method, data, writer);
        assert.equal(response.status, 502, url);
        const result = await response.text();
        assert.ok(!result.includes("private-command") && !result.includes('"success":true'));
      }
      const reclaim = await request("/api/cluster/volumes/reclaim", "PATCH", { volumes: [{ name: "example-pv", policy: "Retain" }] }, writer);
      assert.equal(reclaim.status, 207);
      const reclaimBody = await reclaim.json();
      assert.equal(reclaimBody.success, false);
      assert.ok(!JSON.stringify(reclaimBody).includes("private-command"));
      const readPaths = [
        ["/api/cluster/nodes/test-node/yaml", "Node"], ["/api/cluster/ingresses/apps/web/yaml", "Ingress"],
        ["/api/cluster/services/apps/web/yaml", "Service"], ["/api/cluster/volumes/apps/data/yaml", "PersistentVolumeClaim"],
      ];
      for (const [url, kind] of readPaths) {
        const response = await request(url, "GET", undefined, reader);
        assert.equal(response.status, 200, url);
        assert.ok((await response.json()).yaml.includes(`kind: ${kind}`));
      }
      const logs = await request("/api/cluster/pods/apps/demo/logs?tail=50&container=app&previous=true", "GET", undefined, reader);
      assert.equal(logs.status, 200);
      assert.equal((await logs.json()).logs, "fixture log line\n");
      assert.ok((await fixture.calls()).at(-1)!.includes("--limit-bytes=262144"));
      assert.equal((await request("/api/cluster/pods/apps/demo/logs?tail=1001", "GET", undefined, reader)).status, 400);
      assert.equal((await request("/api/cluster/pods/apps/demo/exec", "POST", { command: "echo fixture" }, reader)).status, 403);
      const execResult = await request("/api/cluster/pods/apps/demo/exec", "POST", { command: "echo fixture; pwd" }, writer);
      assert.equal(execResult.status, 502);
      assert.deepEqual((await fixture.calls()).at(-1)!.slice(2), ["exec", "demo", "-n", "apps", "--", "sh", "-lc", "echo fixture; pwd"]);
      assert.equal((await request("/api/cluster/nodes/test-node/action", "POST", { action: "drain" }, writer)).status, 400);
      assert.equal((await request("/api/cluster/nodes/test-node/action", "POST", { action: "cordon" }, reader)).status, 403);
      assert.equal((await request("/api/cluster/nodes/test-node/action", "POST", { action: "drain", confirmName: "test-node" }, writer)).status, 502);
      const drainArgs = (await fixture.calls()).at(-1)!;
      assert.ok(drainArgs.includes("--timeout=20s") && !drainArgs.includes("--force") && !drainArgs.includes("--delete-emptydir-data"));
      assert.equal((await request("/api/cluster/ingresses/apps/web/delete", "DELETE", undefined, writer)).status, 502);
      const sessionCapabilities = await (await request("/api/auth/session", "GET", undefined, reader)).json();
      assert.equal(sessionCapabilities.capabilities.provisioning, false);
      if (process.platform === "win32") assert.equal(sessionCapabilities.capabilities.operatorShell, false);
      const invalidYaml = await request("/api/cluster/namespaces/apps/yaml", "PUT", { yaml: "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: apps\n" }, writer);
      assert.equal(invalidYaml.status, 428);
      const fluxCreate = await request("/api/flux/repos", "POST", { name: "failed-source", url: "https://example.invalid/repository.git" }, writer);
      assert.equal(fluxCreate.status, 502);
      assert.ok(!(await fluxCreate.text()).includes("private-command"));
      const failedRepo = await db.gitRepo.findUnique({ where: { name: "failed-source" } });
      assert.ok(failedRepo, "partial repository metadata must remain available for recovery");
      const fluxDelete = await request(`/api/flux/repos/${failedRepo.id}`, "DELETE", undefined, writer);
      assert.equal(fluxDelete.status, 200);
      const deletion = await fluxDelete.json();
      let progress;
      for (let attempt = 0; attempt < 20; attempt++) {
        progress = await (await request(`/api/flux/repos/${deletion.deleteId}/delete-progress`, "GET", undefined, writer)).json();
        if (progress.done) break;
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      assert.ok(progress?.done && progress.error);
      assert.equal(progress.steps.find((step: { step: string }) => step.step === "flux_crds").status, "error");
      assert.ok(!JSON.stringify(progress).includes("private-command"));
      assert.ok(await db.gitRepo.findUnique({ where: { id: failedRepo.id } }), "failed deletion removed the recovery record");
      assert.equal((await request("/api/cluster/nodes", "POST", { hostname: "must-not-create", ipAddress: "127.0.0.2" }, reader)).status, 403);
      assert.equal(await db.node.count({ where: { hostname: "must-not-create" } }), 0);
      assert.equal((await request("/api/cluster/diagnostics", "GET", undefined, reader)).status, 403);
      await request("/api/cluster/refresh", "POST", undefined, writer);
      const beforeCold = (await fixture.calls()).length;
      const coldStarted = performance.now();
      const cold = await request("/api/cluster/pods", "GET", undefined, reader);
      assert.equal(cold.status, 200);
      const podBody = await cold.json();
      const coldMs = performance.now() - coldStarted;
      assert.equal(podBody.pods.length, 3);
      assert.equal(podBody.availability.state, "healthy");
      assert.equal((await fixture.calls()).length - beforeCold, 1, "pod list fetched unrelated resource types");
      const warmCount = (await fixture.calls()).length;
      const warmMs = [];
      for (let index = 0; index < 12; index++) {
        const start = performance.now();
        await (await request("/api/cluster/pods", "GET", undefined, reader)).json();
        warmMs.push(performance.now() - start);
      }
      const warm = await Promise.all(Array.from({ length: 20 }, () => request("/api/cluster/pods", "GET", undefined, reader)));
      assert.ok(warm.every(response => response.status === 200));
      assert.equal((await fixture.calls()).length, warmCount);
      await request("/api/cluster/refresh", "POST", undefined, writer);
      const beforeConcurrent = (await fixture.calls()).length;
      const concurrentMs = await Promise.all(Array.from({ length: 20 }, async () => {
        const start = performance.now();
        await (await request("/api/cluster/pods", "GET", undefined, reader)).json();
        return performance.now() - start;
      }));
      assert.equal((await fixture.calls()).length - beforeConcurrent, 1, "cold concurrent reads lost coalescing");
      const appPods = await (await request("/api/cluster/pods?type=app&namespace=apps&labelSelector=app%3Dworker", "GET", undefined, reader)).json();
      assert.equal(appPods.pods.length, 1);
      const systemPods = await (await request("/api/cluster/pods?type=system", "GET", undefined, reader)).json();
      assert.equal(systemPods.pods.length, 2);
      assert.equal((await request("/api/cluster/pods?type=invalid", "GET", undefined, reader)).status, 400);
      const deploymentBody = await (await request("/api/cluster/deployments", "GET", undefined, reader)).json();
      assert.equal(deploymentBody.deployments.find((deployment: any) => deployment.name === "api").restarts, 0);
      assert.equal(deploymentBody.deployments.find((deployment: any) => deployment.name === "api").state, "Scaled down");
      const worker = deploymentBody.deployments.find((deployment: any) => deployment.name === "api-worker");
      assert.equal(worker.restarts, 9);
      assert.equal(worker.ready, "1/2");
      assert.equal(worker.state, "Reconciling");
      const detail = await (await request("/api/cluster/deployments/apps/api-worker", "GET", undefined, reader)).json();
      assert.deepEqual(detail.pods.map((pod: any) => pod.metadata.uid), ["pod-worker"]);
      await writeFile(path.join(fixture.bin, "failure.txt"), "pods");
      await request("/api/cluster/refresh", "POST", undefined, writer);
      const stale = await request("/api/cluster/pods", "GET", undefined, reader);
      assert.equal(stale.status, 200);
      assert.ok(stale.headers.get("warning"));
      assert.equal((await stale.json()).availability.state, "stale");
      const backedOff = (await fixture.calls()).length;
      await Promise.all(Array.from({ length: 20 }, () => request("/api/cluster/pods", "GET", undefined, reader)));
      assert.equal((await fixture.calls()).length, backedOff);
      await writeFile(path.join(fixture.bin, "failure.txt"), "services");
      const missingPrimary = await request("/api/cluster/services", "GET", undefined, reader);
      assert.equal(missingPrimary.status, 503);
      assert.equal((await missingPrimary.json()).availability.state, "unavailable");
      const outageBefore = (await fixture.calls()).length;
      const outageMs = [];
      for (let index = 0; index < 12; index++) {
        const start = performance.now();
        const response = await request("/api/cluster/services", "GET", undefined, reader);
        assert.equal(response.status, 503);
        await response.json();
        outageMs.push(performance.now() - start);
      }
      assert.equal((await fixture.calls()).length, outageBefore, "outage backoff spawned repeated processes");
      await unlink(path.join(fixture.bin, "failure.txt"));
      await request("/api/cluster/refresh", "POST", undefined, writer);
      const empty = await request("/api/cluster/services", "GET", undefined, reader);
      const emptyBody = await empty.json();
      assert.equal(empty.status, 200);
      assert.deepEqual(emptyBody.services, []);
      assert.equal(emptyBody.availability.state, "empty");
      const diagnostics = await (await request("/api/cluster/diagnostics", "GET", undefined, writer)).json();
      assert.equal(diagnostics.commands.maxConcurrent, 4);
      assert.ok(diagnostics.resources.pods.failures >= 1);
      const percentiles = (values: number[]) => {
        const sorted = [...values].sort((a, b) => a - b);
        return { p50: sorted[Math.ceil(sorted.length * 0.5) - 1], p95: sorted[Math.ceil(sorted.length * 0.95) - 1] };
      };
      const evidence = {
        capturedAt: new Date().toISOString(), node: process.version, platform: process.platform,
        fixture: "disposable production HTTP + 50ms metadata-only fake CLI; no real cluster/image acceptance",
        source: process.env.BORTUS_EVIDENCE_SOURCE || "current working tree",
        coldPods: { ms: coldMs, cliCalls: 1 }, warmPods: { samples: 12, ms: percentiles(warmMs), cliCalls: 0 },
        concurrentWarmPods: { requests: 20, cliCalls: 0 }, concurrentColdPods: { requests: 20, cliCalls: 1, ms: percentiles(concurrentMs) },
        outageServices: { requests: 12, status: 503, ms: percentiles(outageMs), additionalCliCalls: 0 },
        pool: diagnostics.commands,
        limitations: ["Windows/Node24 synthetic metadata rather than Node22/Linux image", "no real API/RBAC or cold-container memory/peak-process measurement", "timings observational with no controlled host CPU isolation"],
      };
      context.diagnostic(`Cache fixture evidence: ${JSON.stringify(evidence)}`);
      if (process.env.BORTUS_TEST_EVIDENCE_PATH) await writeFile(process.env.BORTUS_TEST_EVIDENCE_PATH, JSON.stringify(evidence, null, 2) + "\n");
      const values = await request("/api/vars", "GET", undefined, reader);
      assert.equal(values.status, 200);
      const body = await values.text();
      assert.ok(body.includes("k8s_version"));
      assert.ok(
        !body.includes("DB marker") && !body.includes("unmapped_password"),
      );
      for (const method of ["POST", "DELETE"])
        assert.equal(
          (await request("/api/secrets", method, {}, reader)).status,
          403,
        );
      assert.equal(
        (
          await request(
            "/api/secrets?namespace=apps&name=vpn&key=openvpn_user",
            "GET",
            undefined,
            reader,
          )
        ).status,
        403,
      );
      const bearer = (key: string) =>
        fetch(`${base}/api/vars/lookup?key=${key}`, {
          headers: { authorization: "Bearer fake-lookup-token" },
        });
      const config = await bearer("k8s_version");
      assert.equal(config.status, 200);
      assert.ok((await config.json()).value === "v-test");
      const unavailable = await bearer("secret_apps_vpn_openvpn_user");
      assert.equal(unavailable.status, 503);
      assert.ok(!(await unavailable.text()).includes("DB marker"));
      assert.equal((await bearer("unmapped_password")).status, 404);
      assert.equal((await request("/api/health/ready")).status, 503);
      assert.equal(
        (await request("/api/deploy/start", "POST", {}, writer)).status,
        501,
      );
      const alias = {
        alias: "legacy_user",
        namespace: "apps",
        name: "vpn",
        key: "openvpn_user",
      };
      assert.equal(
        (await request("/api/secret-references", "POST", alias, writer)).status,
        201,
      );
      const hyphenated = { ...alias, alias: "secret_apps_vpn-creds_openvpn_user" };
      assert.equal((await request("/api/secret-references", "POST", hyphenated, writer)).status, 201);
      assert.equal((await request("/api/vars", "POST", { key: hyphenated.alias, value: "fake native only", mode: "update", resourceVersion: "1" }, writer)).status, 503);
      assert.equal(await db.variable.count({ where: { key: hyphenated.alias } }), 0);
      assert.equal(
        (
          await request(
            "/api/secret-references",
            "POST",
            { ...alias, name: "other" },
            writer,
          )
        ).status,
        409,
      );
      assert.equal(
        (
          await request(
            "/api/vars",
            "POST",
            { key: "new_password", value: "fake rejected", encrypted: false },
            writer,
          )
        ).status,
        400,
      );
      assert.equal(
        await db.variable.count({ where: { key: "new_password" } }),
        0,
      );
      const created = await request("/api/users", "POST", {
        username: "revocation_subject", password: "fake-subject-password", role: "readonly",
      }, writer);
      assert.equal(created.status, 201);
      const subject = await created.json();
      const loginSubject = async (password: string) => {
        const response = await request("/api/auth/login", "POST", { username: "revocation_subject", password });
        assert.equal(response.status, 200);
        return response.headers.get("set-cookie")!.split(";")[0];
      };
      const oldCookie = await loginSubject("fake-subject-password");
      assert.equal((await request("/api/nodes", "GET", undefined, oldCookie)).status, 200);
      assert.equal((await request(`/api/users/${subject.id}`, "PATCH", { password: "fake-reset-password" }, writer)).status, 200);
      assert.equal((await request("/api/nodes", "GET", undefined, oldCookie)).status, 401);
      assert.equal((await request("/api/auth/session", "GET", undefined, oldCookie)).status, 200);
      assert.equal((await (await request("/api/auth/session", "GET", undefined, oldCookie)).json()).authenticated, false);
      const newCookie = await loginSubject("fake-reset-password");
      assert.equal((await request("/api/nodes", "GET", undefined, newCookie)).status, 200);
      assert.equal((await request(`/api/users/${subject.id}`, "DELETE", undefined, writer)).status, 200);
      for (const route of ["/api/nodes", "/api/users", "/api/cluster/pods", "/api/secrets"])
        assert.equal((await request(route, "GET", undefined, newCookie)).status, 401);
      assert.equal((await (await request("/api/auth/session", "GET", undefined, newCookie)).json()).authenticated, false);
      const revokedPage = await fetch(`${base}/pods`, { headers: { cookie: newCookie }, redirect: "manual" });
      assert.equal(revokedPage.status, 307);
      assert.ok(revokedPage.headers.get("location")?.endsWith("/welcome"));
      await db.user.update({
        where: { username: "testwriter" },
        data: { role: "readonly" },
      });
      assert.equal(
        (await request("/api/secret-references", "POST", alias, writer)).status,
        403,
      );
      const legacy = await db.variable.findUnique({
        where: { key: "secret_apps_vpn_openvpn_user" },
      });
      assert.ok(legacy?.value === "fake stale DB marker");
      assert.ok(
        !output.includes("fake stale DB marker") &&
          !output.includes("fake unmapped DB marker") &&
          !output.includes("fake-test-password") && !output.includes("private-command"),
      );
    } finally {
      if (child && child.exitCode === null) {
        child.kill();
        await once(child, "exit");
      }
      await db?.$disconnect();
      await rm(dir, { recursive: true, force: true });
    }
  },
);
