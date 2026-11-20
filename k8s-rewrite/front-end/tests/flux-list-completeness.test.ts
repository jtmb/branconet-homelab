import test from "node:test";
import assert from "node:assert/strict";
import { requireCompleteFluxList } from "../src/lib/flux-input";
import { KubernetesCommandError } from "../src/lib/kubectl-client";

test("complete Flux discovery accepts successful empty, complete paged metadata and exact ten-thousand-item lists without truncation", () => {
  for (const value of [{ items: [] }, { items: [{}], metadata: { continue: "", remainingItemCount: 0 } }, { items: Array.from({ length: 10000 }, (_, index) => ({ metadata: { name: `source-${index}` } })) }]) {
    const before = JSON.stringify(value); requireCompleteFluxList(value); assert.equal(JSON.stringify(value), before);
  }
});

test("partial/malformed/over-quota Flux discovery cannot become successful empty or incomplete child inventory", () => {
  const marker = "synthetic-private-producer-marker";
  for (const value of [null, [], {}, { items: null }, { items: [null] }, { items: [[]] }, { items: [marker] }, { items: [], metadata: null },
    { items: [], metadata: { continue: marker } }, { items: [], metadata: { continue: null } }, { items: [], metadata: { remainingItemCount: "0" } },
    { items: [], metadata: { remainingItemCount: 1 } }, { items: Array.from({ length: 10001 }, () => ({})) }])
    assert.throws(() => requireCompleteFluxList(value), error => error instanceof KubernetesCommandError && error.status === 502 && error.message === "Invalid or incomplete Flux resource list" && !error.message.includes(marker));
});
