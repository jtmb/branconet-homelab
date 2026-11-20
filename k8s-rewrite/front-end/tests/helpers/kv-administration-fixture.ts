import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import { mkdtemp, readFile, writeFile, rm, cp } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { createServer, request as forward, type Server } from "node:http";
import { once } from "node:events";
import { randomUUID } from "node:crypto";
import { PrismaClient } from "@prisma/client";
import { build } from "esbuild";
import { nativeTlsFixture } from "./native-tls";
import { fakeKubectl } from "./fake-kubectl";

/** Production Next HTTP + CA-verified native mock + disposable SQLite. No operator credentials. */
export async function administrationFixture(browser: boolean | "integrated" = false) {
  const root = process.cwd(),
    dir = await mkdtemp(path.join(tmpdir(), "bortus-admin-ui-"));
  let child: ChildProcess | undefined, gateway: Server | undefined;
  const native = await nativeTlsFixture(dir),
    cli = await fakeKubectl(dir);
  const database = "file:" + path.join(dir, "admin.db").replaceAll("\\", "/"),
    aliasesFile = path.join(dir, "aliases.json");
  const aliases = Array.from({ length: 603 }, (_, index) => ({
    alias: "exact_under_scored_alias_" + String(index).padStart(4, "0"),
    namespace: "apps",
    name: "original-secret",
    key: "original_under_scored_key",
  }));
  await writeFile(aliasesFile, JSON.stringify(aliases));
  const db = new PrismaClient({ datasources: { db: { url: database } } });
  const close = async () => {
    if (gateway) {
      gateway.closeAllConnections();
      await new Promise<void>((resolve) => gateway!.close(() => resolve()));
    }
    if (child && child.exitCode === null && child.signalCode === null) {
      child.kill();
      await once(child, "exit");
    }
    await db.$disconnect();
    await native.close();
    const target = path.resolve(dir),
      temp = path.resolve(tmpdir()) + path.sep;
    if (
      !target.startsWith(temp) ||
      !path.basename(target).startsWith("bortus-admin-ui-")
    )
      throw new Error("Unsafe administration fixture cleanup target");
    await rm(target, { recursive: true, force: true });
  };
  try {
    const env: NodeJS.ProcessEnv = {
      ...process.env,
      ...cli.env,
      DATABASE_URL: database,
      BOTRUS_JWT_SECRET: "synthetic-administration-signing-only",
      BOTRUS_SECRETS_KEY: "synthetic-administration-lookup-only",
      BORTUS_SECRET_NAMESPACES: "apps",
      BORTUS_HISTORY_NAMESPACE: "history",
      BORTUS_KV_GUARDED_ADOPTION: "true",
      BORTUS_DISABLE_PROVISIONING: "true",
      BORTUS_SECRET_ALIASES_FILE: aliasesFile,
      KUBECONFIG: native.config,
      NODE_ENV: "production",
      HOSTNAME: "127.0.0.1",
    };
    delete env.RUST_LOG;
    delete env.KUBERNETES_SERVICE_HOST;
    delete env.ALLOW_REGISTRATION;
    execFileSync(
      process.execPath,
      [path.resolve("node_modules/prisma/build/index.js"), "migrate", "deploy"],
      { env, stdio: "pipe" },
    );
    const holder = createServer();
    holder.listen(0, "127.0.0.1");
    await once(holder, "listening");
    env.PORT = String((holder.address() as { port: number }).port);
    await new Promise<void>((resolve) => holder.close(() => resolve()));
    const origin = "http://127.0.0.1:" + env.PORT;
    if (browser === "integrated") {
      // Next standalone intentionally omits static assets; use this build's exact assets.
      await cp(path.resolve(".next/static"), path.resolve(".next/standalone/.next/static"), { recursive: true });
    }
    child = spawn(
      process.execPath,
      [path.resolve(".next/standalone/server.js")],
      { env, stdio: ["ignore", "ignore", "ignore"] },
    );
    const deadline = Date.now() + 30000;
    let ready = false;
    while (Date.now() < deadline) {
      if (child.exitCode !== null)
        throw new Error("Disposable administration server exited");
      try {
        if (
          (
            await fetch(origin + "/api/auth/session", {
              signal: AbortSignal.timeout(2000),
            })
          ).ok
        ) {
          ready = true;
          break;
        }
      } catch {
        /* bounded startup */
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    if (!ready)
      throw new Error("Disposable administration server startup timed out");
    let cookie = "";
    const request = (
      url: string,
      method = "GET",
      body?: unknown,
      credential = cookie,
    ) =>
      fetch(origin + url, {
        method,
        redirect: "manual",
        signal: AbortSignal.timeout(20000),
        headers: {
          ...(credential ? { cookie: credential } : {}),
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    const checked = async <T = Record<string, any>>(
      response: Response,
      status = 200,
    ): Promise<T> => {
      if (response.status !== status)
        throw new Error(
          `Synthetic administration HTTP status ${response.status}, expected ${status}`,
        );
      return response.json();
    };
    await checked(
      await request("/api/auth/register", "POST", {
        username: "admin_fixture",
        password: "synthetic-admin-fixture-password",
      }),
      201,
    );
    const login = await request("/api/auth/login", "POST", {
      username: "admin_fixture",
      password: "synthetic-admin-fixture-password",
    });
    if (login.status !== 200)
      throw new Error("Synthetic administration login failed");
    cookie = login.headers.get("set-cookie")!.split(";", 1)[0];
    const owner = await db.user.findUniqueOrThrow({
      where: { username: "admin_fixture" },
    });
    const scoped = await checked(
      await request("/api/users", "POST", {
        username: "scoped_fixture",
        password: "synthetic-scoped-fixture-password",
        role: "write",
      }),
      201,
    );
    const scopedLogin = await request("/api/auth/login", "POST", {
      username: "scoped_fixture",
      password: "synthetic-scoped-fixture-password",
    });
    const scopedCookie = scopedLogin.headers
      .get("set-cookie")!
      .split(";", 1)[0];
    const mount = await checked(
      await request("/api/kv/mounts", "POST", {
        name: "fixture-apps",
        namespaces: ["apps"],
      }),
      201,
    );
    const registered = await checked(
      await request("/api/kv/paths", "POST", {
        mountId: mount.id,
        path: "apps/service/credentials",
        namespace: "apps",
        name: "original-secret",
        fields: [{ field: "password", key: "original_under_scored_key" }],
        retention: 2,
      }),
      201,
    );
    const route = "/api/kv/paths/" + registered.id;
    const privateMarker = "synthetic-other-key-annotation-never-render";
    native.seed(
      "apps",
      "original-secret",
      {
        original_under_scored_key: Buffer.from(
          "synthetic-native-original",
        ).toString("base64"),
        unrelated: Buffer.from(privateMarker).toString("base64"),
      },
      {
        metadata: {
          annotations: {
            "kubectl.kubernetes.io/last-applied-configuration": privateMarker,
          },
          labels: { original: "retained" },
        },
      },
    );
    const preview = await checked(await request(route + "/adopt"));
    let current = await checked(
      await request(route + "/adopt", "POST", {
        resourceVersion: preview.resourceVersion,
        expectedHead: 0,
        legacyAliases: aliases.map((row) => row.alias),
      }),
    );
    for (let version = 2; version <= 3; version++)
      current = await checked(
        await request(route + "/data", "PUT", {
          resourceVersion: current.resourceVersion,
          expectedHead: current.head,
          fields: [
            {
              field: "password",
              encoding: "utf8",
              value: "synthetic-native-version-" + version,
            },
          ],
        }),
      );
    // Age the synthetic orphan only. Real native values/metadata are never involved.
    for (const object of native.objects.values())
      if (object.metadata?.namespace === "history")
        object.metadata.creationTimestamp = new Date(Date.now() - 3 * 86400000);
    const policies = Array.from({ length: 205 }, (_, index) => ({
      id: randomUUID(),
      principal: "user:" + scoped.id,
      mountId: mount.id,
      prefix: "fixture/metadata/" + index,
      effect: "allow",
      actions: '["list"]',
    }));
    await db.kvPolicy.createMany({ data: policies });
    await db.kvIdentity.createMany({
      data: Array.from({ length: 105 }, (_, index) => ({
        id: randomUUID(),
        name: "metadata_identity_" + index,
        ownerId: owner.id,
        ownerSessionVersion: owner.sessionVersion,
        credentialHash: "synthetic-unusable-credential-hash-" + index,
        expiresAt: new Date(Date.now() + 86400000),
      })),
    });
    await db.kvAudit.createMany({
      data: Array.from({ length: 205 }, () => ({
        actorId: owner.id,
        pathId: registered.id,
        mountId: mount.id,
        path: registered.path,
        namespace: "apps",
        name: "original-secret",
        action: "fixture-metadata",
        outcome: "committed",
      })),
    });
    const consumerObject = {
      apiVersion: "apps/v1",
      kind: "Deployment",
      metadata: {
        namespace: "apps",
        name: "fixture-consumer",
        uid: "consumer-uid",
        resourceVersion: "consumer-rv-1",
      },
      spec: {
        template: {
          metadata: { annotations: {} },
          spec: {
            containers: [
              { name: "app", image: "example.invalid/synthetic:v1" },
            ],
          },
        },
      },
    };
    await writeFile(
      path.join(cli.bin, "deployment.json"),
      JSON.stringify(consumerObject),
    );
    await writeFile(
      path.join(cli.bin, "allow-rotation-reload"),
      "synthetic-only",
    );
    const counts: Record<string, number> = {},
      nativeBaseline = native.calls.length;
    const ambiguousOperationId = randomUUID();
    await db.kvOperation.create({
      data: {
        id: ambiguousOperationId,
        actorId: owner.id,
        mountId: mount.id,
        pathId: registered.id,
        path: registered.path,
        namespace: registered.namespace,
        name: registered.name,
        action: "update",
        previousVersion: 99,
        newVersion: 100,
        outcome: "ambiguous",
      },
    });
    let delayToken = false;
    const control = async (action: string) => {
      if (
        action === "withdraw-admin" ||
        action === "restore-admin" ||
        action === "readonly"
      )
        await db.user.update({
          where: { id: owner.id },
          data: {
            role: action === "readonly" ? "readonly" : "write",
            engineAdmin: action === "restore-admin",
          },
        });
      else if (action === "delay-token") delayToken = true;
      else if (action === "stale-policies")
        await db.kvPolicy.updateMany({ data: { revision: { increment: 1 } } });
      else if (action === "deny-rotate")
        await db.kvPolicy.create({
          data: {
            principal: "user:" + owner.id,
            mountId: mount.id,
            prefix: registered.path,
            effect: "deny",
            actions: '["rotate"]',
          },
        });
      else if (action === "allow-rotate")
        await db.kvPolicy.deleteMany({
          where: {
            principal: "user:" + owner.id,
            effect: "deny",
            actions: '["rotate"]',
          },
        });
      else if (action === "reload-fixture") {
        const row = await db.kvRotation.findFirstOrThrow({
          where: { pathId: registered.id, state: "awaiting-ack" },
        });
        await writeFile(
          path.join(cli.bin, "rotation-reload.json"),
          JSON.stringify({
            ...consumerObject,
            metadata: {
              ...consumerObject.metadata,
              resourceVersion: "consumer-rv-2",
            },
            spec: {
              template: {
                ...consumerObject.spec.template,
                metadata: { annotations: { "bortus.io/rotation-id": row.id } },
              },
            },
          }),
        );
      } else throw new Error("Unknown synthetic fixture control");
    };
    if (browser) {
      if (browser === true) {
      const source = `import React from 'react'; import {createRoot} from 'react-dom/client'; import KvAdministration from './src/components/secrets/kv-administration'; createRoot(document.getElementById('root')).render(<main className="mx-auto max-w-5xl p-3 text-zinc-100"><h1 className="mb-3 text-xl font-semibold">Synthetic BORTUS administration qualification</h1><p className="mb-4 break-all text-xs text-zinc-400">owner=${owner.id} mount=${mount.id} path=${registered.id}</p><KvAdministration selectedPathId=${JSON.stringify(registered.id)} /><a className="mt-4 block text-indigo-300" href="/away">Navigate away</a></main>);`;
      await build({
        stdin: { contents: source, loader: "tsx", resolveDir: root },
        outfile: path.join(dir, "bundle.js"),
        bundle: true,
        platform: "browser",
        jsx: "automatic",
        define: { "process.env.NODE_ENV": '"production"' },
      });
      execFileSync(
        process.execPath,
        [
          path.resolve("node_modules/tailwindcss/lib/cli.js"),
          "-i",
          path.resolve("src/app/globals.css"),
          "--content",
          path.resolve("src/components/secrets/kv-administration.tsx"),
          "-o",
          path.join(dir, "style.css"),
        ],
        { stdio: "pipe" },
      );
      }
      gateway = createServer(async (incoming, response) => {
        const url = new URL(incoming.url ?? "/", origin);
        if (
          url.pathname === "/__fixture/control" &&
          incoming.method === "POST"
        ) {
          let raw = "";
          for await (const chunk of incoming) {
            raw += chunk;
            if (raw.length > 1024) break;
          }
          try {
            await control(JSON.parse(raw).action);
            response.writeHead(204);
          } catch {
            response.writeHead(400);
          }
          response.end();
          return;
        }
        if (url.pathname === "/__fixture/status") {
          response.setHeader("Content-Type", "application/json");
          response.end(
            JSON.stringify({
              requests: counts,
              nativeWrites: native.calls
                .slice(nativeBaseline)
                .filter((call) => call.method !== "GET").length,
              metadataNativeReads: native.calls
                .slice(nativeBaseline)
                .filter((call) => call.method === "GET").length,
              ownerId: owner.id,
              mountId: mount.id,
              pathId: registered.id,
              ambiguousOperationId,
              identities: await db.kvIdentity.count(),
              rotations: await db.kvRotation.count(),
            }),
          );
          return;
        }
        if (browser === true && (url.pathname === "/" || url.pathname === "/away")) {
          response.setHeader("Content-Type", "text/html");
          response.end(
            url.pathname === "/away"
              ? '<!doctype html><title>Fixture away</title><a href="/">Return to administration fixture</a>'
              : '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synthetic BORTUS administration</title><link rel="stylesheet" href="/style.css"></head><body style="background:#09090b"><div id="root"></div><script src="/bundle.js"></script></body></html>',
          );
          return;
        }
        if (browser === true && (url.pathname === "/bundle.js" || url.pathname === "/style.css")) {
          response.setHeader(
            "Content-Type",
            url.pathname.endsWith("js") ? "application/javascript" : "text/css",
          );
          response.end(await readFile(path.join(dir, url.pathname.slice(1))));
          return;
        }
        counts[incoming.method + " " + url.pathname] =
          (counts[incoming.method + " " + url.pathname] ?? 0) + 1;
        const upstream = forward(
          origin + incoming.url,
          {
            method: incoming.method,
            headers: {
              ...incoming.headers,
              cookie,
              host: "127.0.0.1:" + env.PORT,
            },
          },
          async (result) => {
            response.writeHead(result.statusCode ?? 502, result.headers);
            if (
              delayToken &&
              incoming.method === "POST" &&
              url.pathname === "/api/kv/identities"
            ) {
              delayToken = false;
              result.pause();
              setTimeout(() => {
                if (!response.destroyed) result.pipe(response);
                else result.destroy();
              }, 4000);
            } else result.pipe(response);
          },
        );
        response.once("close", () => upstream.destroy());
        upstream.on("error", () => {
          if (!response.destroyed) {
            if (!response.headersSent) response.writeHead(502);
            response.end();
          }
        });
        incoming.pipe(upstream);
      });
      gateway.listen(0, "127.0.0.1");
      await once(gateway, "listening");
    }
    return {
      request,
      checked,
      db,
      native,
      dir,
      owner,
      mount,
      registered,
      policies,
      scopedCookie,
      cli,
      control,
      close,
      origin,
      ambiguousOperationId,
      browserUrl: gateway
        ? "http://127.0.0.1:" + (gateway.address() as { port: number }).port + (browser === "integrated" ? "/secrets/kv" : "")
        : null,
    };
  } catch (error) {
    await close();
    throw error;
  }
}
