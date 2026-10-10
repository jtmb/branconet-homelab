import { administrationFixture } from "./helpers/kv-administration-fixture";

async function main() {
  const fixture = await administrationFixture(true);
  console.log(
    "ADMIN_UI_FIXTURE_READY " +
      JSON.stringify({
        browserUrl: fixture.browserUrl,
        ownerId: fixture.owner.id,
        mountId: fixture.mount.id,
        pathId: fixture.registered.id,
        ambiguousOperationId: fixture.ambiguousOperationId,
      }),
  );
  process.stdin.resume();
  try {
    await new Promise<void>((resolve) => {
      process.once("SIGINT", resolve);
      process.once("SIGTERM", resolve);
      process.stdin.on("data", (chunk) => {
        if (chunk.toString().trim() === "stop") resolve();
      });
    });
  } finally {
    await fixture.close();
    process.stdin.pause();
  }
}
void main().catch(() => {
  console.error(
    "Synthetic administration fixture failed; no production state was used.",
  );
  process.exitCode = 1;
});
