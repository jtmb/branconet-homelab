import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import net, { type AddressInfo } from "node:net";
import { once } from "node:events";
import { PrismaClient } from "@prisma/client";

test(
  "production HTTP auth, metadata migration, quarantined DB rows and unavailable native lookup",
  { timeout: 60000 },
  async () => {
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
    let child: ChildProcess | undefined,
      db: PrismaClient | undefined,
      output = "";
    try {
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
          !output.includes("fake-test-password"),
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
