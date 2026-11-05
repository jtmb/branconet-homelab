import { writeFile } from "node:fs/promises";
import { systemReportServer } from "./helpers/system-report-server";
void (async () => {
  const fixture = await systemReportServer(4088);
  await writeFile("docs/qa-fixture.json", JSON.stringify({ base: fixture.base, dir: fixture.dir, mode: fixture.mode, cache: fixture.cache, scanner: fixture.scanner, kubectl: fixture.kubectl.bin }, null, 2));
  console.log(`Disposable UI fixture: ${fixture.base}; operator / public-fixture-password. Synthetic cluster/scanner data only.`);
  for (const signal of ["SIGINT", "SIGTERM"] as const) process.on(signal, () => { void fixture.stop().finally(() => process.exit()); });
  process.stdin.on("data", data => { if (data.toString().trim() === "stop") void fixture.stop().finally(() => process.exit()); });
})();
