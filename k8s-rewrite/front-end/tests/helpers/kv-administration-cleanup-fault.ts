import https from "node:https";
import { readFile, writeFile } from "node:fs/promises";
import { once } from "node:events";
import path from "node:path";
import { tmpdir } from "node:os";

/** One injected native DELETE outage, using the disposable fixture's CA. Never disables TLS verification. */
export async function administrationCleanupFault(dir: string) {
  const target = path.resolve(dir),
    temp = path.resolve(tmpdir()) + path.sep;
  if (
    !target.startsWith(temp) ||
    !path.basename(target).startsWith("bortus-admin-ui-")
  )
    throw new Error(
      "Cleanup fault requires an owned administration fixture directory",
    );
  const configPath = path.join(target, "native-config"),
    original = await readFile(configPath, "utf8"),
    config = JSON.parse(original);
  const upstream = config.clusters?.[0]?.cluster?.server;
  if (
    !/^https:\/\/127\.0\.0\.1:\d+$/.test(upstream ?? "") ||
    config.users?.[0]?.user?.token !== "synthetic-native-api-token"
  )
    throw new Error("Cleanup fault refuses non-fixture Kubernetes credentials");
  const ca = await readFile(path.join(target, "native-cert.pem")),
    key = await readFile(path.join(target, "native-key.pem"));
  let denied = 0;
  const server = https.createServer({ key, cert: ca }, (request, response) => {
    if (
      denied === 0 &&
      request.method === "DELETE" &&
      request.url?.startsWith("/api/v1/namespaces/history/secrets/kv-")
    ) {
      denied++;
      response.writeHead(503, { "Content-Type": "application/json" });
      response.end('{"kind":"Status","code":503}');
      return;
    }
    const forward = https.request(
      upstream + request.url,
      { method: request.method, headers: request.headers, ca },
      (result) => {
        response.writeHead(result.statusCode ?? 502, result.headers);
        result.pipe(response);
      },
    );
    forward.on("error", () => {
      if (!response.headersSent) response.writeHead(503);
      response.end();
    });
    request.pipe(forward);
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  config.clusters[0].cluster.server =
    "https://127.0.0.1:" + (server.address() as { port: number }).port;
  await writeFile(configPath, JSON.stringify(config));
  return {
    denied: () => denied,
    async close() {
      await writeFile(configPath, original);
      server.closeAllConnections();
      await new Promise<void>((resolve) => server.close(() => resolve()));
    },
  };
}
