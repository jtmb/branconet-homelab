/**
 * Shared module for tracking active Ansible job controllers.
 * Both start/route.ts and stop/route.ts import from here.
 * Uses globalThis to survive Next.js webpack module duplication
 * across separate App Router route bundles.
 */
const g = globalThis as unknown as {
  __activeJobs?: Map<string, AbortController>;
};
export const activeJobs: Map<string, AbortController> =
  g.__activeJobs ?? (g.__activeJobs = new Map());
