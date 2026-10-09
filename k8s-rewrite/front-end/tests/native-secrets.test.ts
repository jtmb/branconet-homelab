import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import type { V1Secret } from "@kubernetes/client-node";
import {
  SecretStore,
  SecretError,
  secretFailure,
  type SecretTransport,
} from "../src/lib/cluster-secrets";
import { mergeAliases } from "../src/lib/secret-aliases";
import { isSensitiveVariable } from "../src/lib/variable-policy";
import { secretHandlers } from "../src/lib/secrets-api";
import { lookupHandler } from "../src/lib/lookup-api";
import { createSecretTransport } from "../src/lib/secret-client";
import { middleware } from "../src/middleware";
import { NextRequest } from "next/server";

const target = { namespace: "apps", name: "vpn", key: "openvpn_user" };
const encode = (value: string) => Buffer.from(value).toString("base64");
class MemoryAPI implements SecretTransport {
  objects = new Map<string, V1Secret>();
  mutations = 0;
  race = false;
  unavailable = false;
  async read(ns: string, name: string) {
    if (this.unavailable)
      throw { code: 503, body: "sensitive exception payload" };
    const obj = this.objects.get(`${ns}/${name}`);
    if (!obj) throw { code: 404 };
    return structuredClone(obj);
  }
  async list(ns: string) {
    if (this.unavailable) throw new Error("sensitive exception payload");
    return [...this.objects.values()]
      .filter((obj) => obj.metadata?.namespace === ns)
      .map((obj) => structuredClone(obj));
  }
  async create(ns: string, obj: V1Secret) {
    if (this.objects.has(`${ns}/${obj.metadata?.name}`)) throw { code: 409 };
    obj.metadata = { ...obj.metadata, resourceVersion: "1" };
    this.objects.set(`${ns}/${obj.metadata?.name}`, structuredClone(obj));
    this.mutations++;
    return structuredClone(obj);
  }
  async replace(ns: string, name: string, obj: V1Secret) {
    const existing = await this.read(ns, name);
    if (
      this.race ||
      existing.metadata?.resourceVersion !== obj.metadata?.resourceVersion
    )
      throw { code: 409, body: "sensitive exception payload" };
    obj.metadata = {
      ...obj.metadata,
      resourceVersion: String(Number(obj.metadata?.resourceVersion) + 1),
    };
    this.objects.set(`${ns}/${name}`, structuredClone(obj));
    this.mutations++;
    return structuredClone(obj);
  }
}
function setup() {
  const api = new MemoryAPI();
  api.objects.set("apps/vpn", {
    apiVersion: "v1",
    kind: "Secret",
    type: "kubernetes.io/basic-auth",
    metadata: {
      namespace: "apps",
      name: "vpn",
      resourceVersion: "7",
      labels: { imported: "yes" },
      annotations: { preserve: "yes" },
      ownerReferences: [
        { apiVersion: "v1", kind: "ConfigMap", name: "owner", uid: "owner-id" },
      ],
    },
    data: {
      openvpn_user: encode("fake imported value"),
      password: encode("fake unrelated value"),
    },
  });
  return { api, store: new SecretStore(api, ["apps"]) };
}
const status = (code: number) => (error: unknown) =>
  error instanceof SecretError && error.status === code;
test("read imported values; list is metadata only; restart reads native store", async () => {
  const { api, store } = setup();
  assert.ok((await store.read(target)).value === "fake imported value");
  assert.ok(
    !JSON.stringify(await store.list()).includes("fake imported value"),
  );
  assert.ok(!Object.hasOwn((await store.list())[0], "data"));
  assert.ok(
    (await new SecretStore(api, ["apps"]).read(target)).value ===
      "fake imported value",
  );
  assert.equal(api.mutations, 0);
});
test("create, update, key deletion preserve unrelated data/type/all metadata", async () => {
  const { api, store } = setup();
  const old = await api.read("apps", "vpn");
  await store.write(target, "fake changed", "update", "7");
  let current = await api.read("apps", "vpn");
  assert.ok(current.data?.password === old.data?.password);
  assert.ok(current.type === old.type);
  assert.deepEqual(current.metadata?.labels, old.metadata?.labels);
  assert.deepEqual(current.metadata?.annotations, old.metadata?.annotations);
  assert.deepEqual(
    current.metadata?.ownerReferences,
    old.metadata?.ownerReferences,
  );
  await store.write({ ...target, key: "extra_key" }, "", "create");
  current = await api.read("apps", "vpn");
  assert.ok(Object.hasOwn(current.data!, "extra_key"));
  await store.deleteKey(target, current.metadata!.resourceVersion!);
  current = await api.read("apps", "vpn");
  assert.ok(!Object.hasOwn(current.data!, target.key));
  assert.ok(current.data?.password === old.data?.password);
  await store.write(
    { namespace: "apps", name: "new", key: "only" },
    "fake",
    "create",
  );
  await store.deleteKey({ namespace: "apps", name: "new", key: "only" }, "1");
  assert.equal(Object.keys((await api.read("apps", "new")).data!).length, 0);
});
test("create collisions, stale updates, races and immutable objects never retry", async () => {
  const { api, store } = setup();
  await assert.rejects(store.write(target, "fake", "create"), status(409));
  await assert.rejects(store.write(target, "fake", "update"), status(428));
  await assert.rejects(
    store.write(target, "fake", "update", "stale"),
    status(409),
  );
  await assert.rejects(store.deleteKey(target, "stale"), status(409));
  api.race = true;
  await assert.rejects(store.write(target, "fake", "update", "7"), status(409));
  api.race = false;
  api.objects.get("apps/vpn")!.immutable = true;
  await assert.rejects(store.write(target, "fake", "update", "7"), status(409));
  await assert.rejects(store.deleteKey(target, "7"), status(409));
  assert.equal(api.mutations, 0);
});
test("unavailable/read denied/invalid errors are fixed and cannot leak API bodies", async () => {
  const { api, store } = setup();
  api.unavailable = true;
  await assert.rejects(store.read(target), status(503));
  await assert.rejects(store.list(), status(503));
  await assert.rejects(store.write(target, "fake", "create"), status(503));
  assert.equal(api.mutations, 0);
  for (const code of [400, 401, 403, 404, 409, 422, 500])
    assert.ok(
      !secretFailure({
        code,
        body: "sensitive exception payload",
      }).message.includes("sensitive"),
    );
  await assert.rejects(
    store.read({ ...target, namespace: "outside" }),
    status(403),
  );
  await assert.rejects(
    store.read({ ...target, name: "bad;command" }),
    status(400),
  );
});
test("explicit aliases preserve underscored keys, duplicate targets and reject alias collisions", () => {
  const refs = mergeAliases([
    [
      { ...target, alias: "secret_apps_vpn_openvpn_user" },
      { ...target, alias: "vault/path/user" },
    ],
  ]);
  assert.ok(
    refs.every((ref) => ref.key === "openvpn_user" && ref.name === "vpn"),
  );
  assert.equal(mergeAliases([refs, refs]).length, 2);
  assert.throws(
    () =>
      mergeAliases([
        refs,
        [{ ...target, alias: refs[0].alias, name: "other" }],
      ]),
    status(409),
  );
});
test("sensitive legacy DB rows are excluded while nonsecret config remains", () => {
  for (const key of [
    "secret_plex_smb-creds_password",
    "ansible_become_password",
    "system_jwt_secret",
    "github_token",
  ])
    assert.ok(
      isSensitiveVariable({ key, category: "general", encrypted: false }),
    );
  assert.ok(
    isSensitiveVariable({
      key: "legacy",
      category: "secret",
      encrypted: false,
    }),
  );
  assert.ok(
    isSensitiveVariable({
      key: "legacy",
      category: "general",
      encrypted: true,
    }),
  );
  assert.ok(
    !isSensitiveVariable({
      key: "k8s_version",
      category: "kubernetes",
      encrypted: false,
    }),
  );
  assert.ok(
    !isSensitiveVariable({
      key: "ansible_ssh_private_key_file",
      category: "ansible",
      encrypted: false,
    }),
  );
});
test("Secret handler authentication/read/write boundaries are checked before backend access", async () => {
  const { store } = setup();
  let role: "readonly" | "write" | null = null,
    calls = 0;
  const handlers = secretHandlers(
    async () => role,
    () => {
      calls++;
      return store;
    },
  );
  const valueUrl =
    "https://bortus/api/secrets?namespace=apps&name=vpn&key=openvpn_user";
  assert.equal((await handlers.GET(new Request(valueUrl))).status, 401);
  assert.equal(calls, 0);
  role = "readonly";
  assert.equal(
    (await handlers.GET(new Request("https://bortus/api/secrets"))).status,
    200,
  );
  calls = 0;
  assert.equal((await handlers.GET(new Request(valueUrl))).status, 403);
  for (const method of ["POST", "DELETE"] as const)
    assert.equal(
      (await handlers[method](new Request(valueUrl, { method, body: "{}" })))
        .status,
      403,
    );
  assert.equal(calls, 0);
  role = "write";
  const response = await handlers.GET(new Request(valueUrl));
  assert.equal(response.status, 200);
  assert.ok(response.headers.get("cache-control")?.includes("no-store"));
  assert.equal(
    (
      await handlers.POST(
        new Request(valueUrl, { method: "POST", body: "not JSON" }),
      )
    ).status,
    400,
  );
  role = "readonly";
  assert.equal((await handlers.GET(new Request(valueUrl))).status, 403);
});
test("Bearer lookup requires token, keeps response contract and redacts failures", async () => {
  let calls = 0;
  const handler = lookupHandler(
    async () => {
      calls++;
      return "fake value";
    },
    () => "fake-token",
  );
  const url = "https://bortus/api/vars/lookup?key=legacy";
  for (const auth of [undefined, "Bearer bad", "bearer fake-token"])
    assert.equal(
      (
        await handler(
          new Request(url, { headers: auth ? { authorization: auth } : {} }),
        )
      ).status,
      401,
    );
  assert.equal(calls, 0);
  const response = await handler(
    new Request(url, { headers: { authorization: "Bearer fake-token" } }),
  );
  const result = await response.json();
  assert.ok(result.key === "legacy" && result.value === "fake value");
  assert.ok(response.headers.get("cache-control")?.includes("no-store"));
  const failing = lookupHandler(
    async () => {
      throw { code: 503, body: "sensitive payload" };
    },
    () => "fake-token",
  );
  const failed = await failing(
    new Request(url, { headers: { authorization: "Bearer fake-token" } }),
  );
  assert.equal(failed.status, 503);
  assert.ok(!(await failed.text()).includes("sensitive payload"));
});
test("middleware permits exact Bearer/probe paths but protects similar paths", async () => {
  for (const pathname of [
    "/api/vars/lookup",
    "/api/health/live",
    "/api/health/ready",
  ])
    assert.ok(
      (
        await middleware(new NextRequest(`https://bortus${pathname}`))
      ).headers.has("x-middleware-next"),
    );
  for (const pathname of [
    "/api/vars/lookup/other",
    "/api/secrets",
    "/api/health/ready/other",
  ])
    assert.equal(
      (await middleware(new NextRequest(`https://bortus${pathname}`))).status,
      401,
    );
});
test("transport rejects HTTP and insecure TLS kubeconfig without API access", async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-transport-test-"));
  const previous = process.env.KUBECONFIG;
  try {
    const file = path.join(dir, "config");
    process.env.KUBECONFIG = file;
    for (const [server, insecure] of [
      ["http://localhost:1", false],
      ["https://localhost:1", true],
    ] as const) {
      await writeFile(
        file,
        JSON.stringify({
          apiVersion: "v1",
          kind: "Config",
          clusters: [
            {
              name: "test",
              cluster: { server, "insecure-skip-tls-verify": insecure },
            },
          ],
          contexts: [
            { name: "test", context: { cluster: "test", user: "test" } },
          ],
          users: [{ name: "test", user: { token: "fake" } }],
          "current-context": "test",
        }),
      );
      assert.throws(() => createSecretTransport(), status(503));
    }
  } finally {
    if (previous === undefined) delete process.env.KUBECONFIG;
    else process.env.KUBECONFIG = previous;
    await rm(dir, { recursive: true });
  }
});
