import { spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { constants } from "node:fs";
import { open, readFile, statfs } from "node:fs/promises";
import { isAbsolute } from "node:path";

export interface ProvisioningLease {
  fd: number;
  ownsJobId(id: string): boolean;
  newJobId(): string;
  release(): Promise<void>;
}

export type ProvisioningLock =
  | { state: "held"; lease: ProvisioningLease }
  | { state: "busy" | "unknown" };

// Only local Linux filesystems with native flock semantics.
const LOCAL_FILESYSTEMS = new Set([0xef53, 0x58465342, 0x9123683e, 0x01021994]);

/** Lock an existing private local directory; nothing needs to be written to it. */
export async function acquireProvisioningLock(
    directory = process.env.BORTUS_PROVISIONING_LOCK_DIR): Promise<ProvisioningLock> {
  if (process.platform !== "linux" || !directory || !isAbsolute(directory)) return { state: "unknown" };
  let handle: Awaited<ReturnType<typeof open>> | undefined;
  try {
    handle = await open(directory, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
    const info = await handle.stat({ bigint: true });
    if (info.uid !== BigInt(process.getuid!()) || (info.mode & 0o022n) !== 0n) return { state: "unknown" };
    if (!LOCAL_FILESYSTEMS.has((await statfs(`/proc/self/fd/${handle.fd}`)).type >>> 0)) return { state: "unknown" };
    const boot = (await readFile("/proc/sys/kernel/random/boot_id", "ascii")).trim();
    if (!/^[a-f0-9-]{36}$/.test(boot)) return { state: "unknown" };
    const prefix = "lease1-" + createHash("sha256").update(`${boot}:${info.dev}:${info.ino}:${info.ctimeNs}`).digest("hex") + "-";
    const fd = handle.fd;
    const code = await new Promise<number | null>(resolve => {
      const child = spawn("/usr/bin/flock", ["-n", "-E", "75", "3"],
        { stdio: ["ignore", "ignore", "ignore", fd] });
      child.once("error", () => resolve(null));
      child.once("close", resolve);
    });
    if (code !== 0) return { state: code === 75 ? "busy" : "unknown" };
    const locked = handle;
    handle = undefined;
    return { state: "held", lease: {
      fd,
      ownsJobId: id => id.startsWith(prefix) && /^[a-f0-9-]{36}$/.test(id.slice(prefix.length)),
      newJobId: () => prefix + randomUUID(),
      release: () => locked.close(),
    } };
  } catch {
    return { state: "unknown" };
  } finally {
    await handle?.close().catch(() => {});
  }
}
