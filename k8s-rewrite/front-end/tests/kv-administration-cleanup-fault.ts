import { administrationCleanupFault } from "./helpers/kv-administration-cleanup-fault";

async function main() {
  const fault = await administrationCleanupFault(process.argv[2] ?? "");
  console.log(
    "ADMIN_CLEANUP_FAULT_READY (one synthetic history DELETE outage; TLS verification retained)",
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
    await fault.close();
    process.stdin.pause();
  }
}
void main().catch(() => {
  console.error(
    "Cleanup fault refused or unavailable; no production configuration is permitted.",
  );
  process.exitCode = 1;
});
