import { z } from "zod/v3";
import { isIP } from "node:net";
import { validateResourceName } from "./kubectl-client";
export const nodeInput = z.object({
  name: z.string().trim().max(100).optional(),
  hostname: z.string().refine(value => { try { validateResourceName(value); return true; } catch { return false; } }, "Invalid hostname"),
  ipAddress: z.string().refine(value => isIP(value) > 0, "Invalid IP address"),
  role: z.enum(["worker", "master", "control-plane"]).default("worker"),
});
