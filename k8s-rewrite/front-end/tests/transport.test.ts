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
    let listMode = "normal", listReads = 0, metadataMode = "normal", metadataReads = 0;
    let deleteBody: any;
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
        } else if (request.method === "GET" && request.headers.accept?.includes("PartialObjectMetadataList")) {
          metadataReads++;
          result = { apiVersion: "meta.k8s.io/v1", kind: "PartialObjectMetadataList", metadata: {continue:metadataMode==="repeat" || metadataMode==="pages" && !request.url?.includes("continue=") ? "next-page" : ""},
            items: Array.from({length:metadataMode==="oversize"?101:metadataMode==="pages"||metadataMode==="repeat"?100:object?1:0},(_,index)=>({apiVersion:"meta.k8s.io/v1",kind:"PartialObjectMetadata",
              metadata:{name:"item-"+metadataReads+"-"+index,namespace:"apps",uid:"metadata-uid",resourceVersion:"1"},...(metadataMode==="values"?{data:{private:"must not fall back"}}:{})})) };
        } else if (request.method === "GET" && listMode !== "normal") {
          listReads++;
          const offset = Number(new URL(request.url || "/", "https://localhost").searchParams.get("continue") || 0);
          result = { apiVersion: "v1", kind: "SecretList", metadata: { continue: listMode === "repeat" ? "next-page" : offset < 39 ? String(offset + 1) : "" },
            items: Array.from({ length: listMode === "oversize" ? 2 : 1 }, (_, index) => ({ ...object, metadata: { ...object.metadata, name: "item-" + listReads + "-" + index } })) };
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
        } else if (request.method === "DELETE") {
          deleteBody = JSON.parse(body);
          code = deleteBody.preconditions?.uid === "fixture-history-uid" && deleteBody.preconditions?.resourceVersion === "7" ? 200 : 409;
          result = { apiVersion: "v1", kind: "Status", code };
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
    for (const key of ["__proto__", "constructor", "toString"]) {
      await store.write({ ...target, key }, "synthetic special-key bytes", "create");
      assert.equal((await store.read({ ...target, key })).value, "synthetic special-key bytes");
      assert(Object.hasOwn(object.data, key), "The actual TLS JSON body retains valid native key spelling");
    }
    const transport = createSecretTransport();
    await transport.probe("apps");
    metadataMode="pages";metadataReads=0;const metadata=await transport.listMetadata("apps");assert.equal(metadata.length,200);assert.equal(metadataReads,2);assert(!JSON.stringify(metadata).includes("fake TLS value"));
    metadataMode="repeat";metadataReads=0;await assert.rejects(transport.listMetadata("apps"),/Invalid Kubernetes Secret pagination/);assert.equal(metadataReads,2);
    metadataMode="oversize";await assert.rejects(transport.listMetadata("apps"),/exceeds the validated limits/);
    metadataMode="values";await assert.rejects(transport.listMetadata("apps"),/Invalid metadata-only Secret response/);metadataMode="normal";
    listMode = "pages"; listReads = 0;
    assert.equal((await transport.list("apps")).length, 40); assert.equal(listReads, 40);
    listMode = "repeat"; listReads = 0;
    await assert.rejects(transport.list("apps"), /Invalid Kubernetes Secret pagination/); assert.equal(listReads, 2);
    listMode = "oversize";
    await assert.rejects(transport.list("apps"), /exceeds the validated limits/);
    await assert.rejects(transport.delete("history", "candidate", "", "7"), (error: any) => error.status === 428);
    await assert.rejects(transport.delete("history", "candidate", "wrong-uid", "7"), (error: any) => error.status === 409);
    await transport.delete("history", "candidate", "fixture-history-uid", "7");
    assert.deepEqual(deleteBody.preconditions, { uid: "fixture-history-uid", resourceVersion: "7" });
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
