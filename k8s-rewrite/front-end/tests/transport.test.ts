import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtemp, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import https from "node:https";
import { once } from "node:events";
import type { AddressInfo } from "node:net";
import { createSecretTransport } from "../src/lib/secret-client";
import { SecretStore } from "../src/lib/cluster-secrets";

test("real TLS client sends value bodies to a mock Kubernetes API and preserves CAS updates", async (t) => {
  const openssl =
    spawnSync("openssl", ["version"]).status === 0
      ? "openssl"
      : "C:/Program Files/Git/usr/bin/openssl.exe";
  if (spawnSync(openssl, ["version"]).status !== 0) {
    t.skip("OpenSSL is required to create temporary test TLS credentials");
    return;
  }
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-tls-test-"));
  const previous = process.env.KUBECONFIG;
  let server: https.Server | undefined;
  try {
    const key = path.join(dir, "key.pem"),
      cert = path.join(dir, "cert.pem");
    execFileSync(
      openssl,
      [
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        key,
        "-out",
        cert,
        "-days",
        "1",
        "-subj",
        "/CN=localhost",
        "-addext",
        "subjectAltName=IP:127.0.0.1,DNS:localhost",
      ],
      { stdio: "ignore" },
    );
    let object: any = null;
    const seenUrls: string[] = [];
    let authPassed = true;
    server = https.createServer(
      { key: await readFile(key), cert: await readFile(cert) },
      async (request, response) => {
        seenUrls.push(request.url || "");
        authPassed &&=
          request.headers.authorization === "Bearer fake-transport-token";
        let body = "";
        for await (const part of request) body += part;
        let result: unknown,
          code = 200;
        if (request.method === "GET" && request.url?.includes("/secrets/vpn")) {
          if (!object) {
            code = 404;
            result = { kind: "Status", code: 404, message: "Not found" };
          } else result = object;
        } else if (request.method === "GET")
          result = {
            apiVersion: "v1",
            kind: "SecretList",
            metadata: {},
            items: object ? [object] : [],
          };
        else if (request.method === "POST") {
          if (object) {
            code = 409;
            result = { kind: "Status", code: 409 };
          } else {
            object = JSON.parse(body);
            object.metadata.resourceVersion = "1";
            result = object;
            code = 201;
          }
        } else if (request.method === "PUT") {
          const input = JSON.parse(body);
          if (
            input.metadata.resourceVersion !== object.metadata.resourceVersion
          ) {
            code = 409;
            result = { kind: "Status", code: 409 };
          } else {
            object = input;
            object.metadata.resourceVersion = String(
              Number(object.metadata.resourceVersion) + 1,
            );
            result = object;
          }
        }
        response.writeHead(code, { "Content-Type": "application/json" });
        response.end(JSON.stringify(result));
      },
    );
    server.listen(0, "127.0.0.1");
    await once(server, "listening");
    const port = (server.address() as AddressInfo).port;
    const file = path.join(dir, "config");
    process.env.KUBECONFIG = file;
    await writeFile(
      file,
      JSON.stringify({
        apiVersion: "v1",
        kind: "Config",
        clusters: [
          {
            name: "test",
            cluster: {
              server: `https://127.0.0.1:${port}`,
              "certificate-authority": cert,
            },
          },
        ],
        contexts: [
          { name: "test", context: { cluster: "test", user: "test" } },
        ],
        users: [{ name: "test", user: { token: "fake-transport-token" } }],
        "current-context": "test",
      }),
    );
    const store = new SecretStore(createSecretTransport(), ["apps"]),
      target = { namespace: "apps", name: "vpn", key: "openvpn_user" };
    await store.write(target, "fake TLS value", "create");
    assert.ok((await store.read(target)).value === "fake TLS value");
    await store.write({ ...target, key: "other" }, "fake preserved", "create");
    const before = (await store.list())[0];
    await store.write(target, "fake updated", "update", before.resourceVersion);
    assert.ok(
      (await store.read({ ...target, key: "other" })).value ===
        "fake preserved",
    );
    const current = (await store.list())[0];
    await store.deleteKey(target, current.resourceVersion!);
    assert.ok((await store.list())[0].keys.includes("other"));
    assert.ok(authPassed);
    assert.ok(
      seenUrls.every(
        (url) =>
          !url.includes("fake TLS value") && !url.includes("fake updated"),
      ),
    );
  } finally {
    if (previous === undefined) delete process.env.KUBECONFIG;
    else process.env.KUBECONFIG = previous;
    if (server) {
      server.closeAllConnections();
      await new Promise<void>((resolve) => server!.close(() => resolve()));
    }
    await rm(dir, { recursive: true, force: true });
  }
});
