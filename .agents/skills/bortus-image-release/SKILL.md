---
name: bortus-image-release
description: Use when building, publishing, or rolling a new BORTUS (dashboard) container image. Covers the committed-source build contract, image tagging, node preload under imagePullPolicy Never, and the ErrImageNeverPull failure mode.
---

# BORTUS image release

## The contract

`prepare-bortus-release-context.py` builds the Docker context from a **git
commit** (`git ls-tree`/`cat-file`), not the working tree. Uncommitted
changes to `k8s-rewrite/front-end/` cannot be released — commit the scoped
change first (see root-repo commit hygiene below), then build from that
exact SHA.

## Image tagging — the ErrImageNeverPull trap

The deployment uses `imagePullPolicy: Never`. Every build script must tag
the image with the **fully-qualified published repository**,
`jtmb92/bortus:release-<commit>` — not a bare `bortus:release-<commit>`.
An unqualified tag exports as `docker.io/library/bortus:release-<commit>`
on `docker image save`, which matches no reference the published registry
image uses, so nodes can't resolve it after preload and every pod goes
`ErrImageNeverPull`. (`build-bortus-release-image.py` hit exactly this in
2026-11-16/17; the fix and a regression test asserting the tag is qualified
are already in that file — check it hasn't regressed before trusting a new
build script.)

## Build host

The pipeline's fixed build host is `node01`. Docker is **not** normally
running there (it's a control-plane node) — check with
`systemctl is-active docker` (no sudo needed for a read) before assuming a
build will work, and stop+disable it again after the build completes so it
doesn't sit running on a control-plane node between releases (adding Docker's
own iptables chains next to kube-proxy indefinitely). Confirm the cluster's
`FORWARD` policy and pod-to-pod connectivity are unaffected before and after.

## Preload (required before every re-pin)

1. `stage-bortus-release-image.py export` — produces the archive and its
   hash.
2. `stage-bortus-release-image.py preload` — imports on **all three nodes**
   via the sudo-password-on-stdin SSH pattern, and **also** `ctr images tag`
   both the platform manifest digest and the registry index digest on every
   node. Skipping the explicit re-tag step is what causes
   `ErrImageNeverPull` even when the export itself was correct.
3. Add the new digest to **every** Flux-owned admission Deny policy
   (`bortus-kv-guard-*`) that allowlists images — the validator refuses an
   unlisted digest.
4. Re-pin through the normal `private-chart-delivery` path, then watch the
   rollout. If it goes `ErrImageNeverPull`, **roll back immediately**
   (re-pin the previous known-good digest) rather than debugging with the
   service down — a single-replica `Recreate` deployment has no fallback
   pod.
5. After rollout, run `verify-certificates-ui-release.py` (or the
   equivalent live-acceptance script) — a build existing and being pinned is
   not the same as the feature actually being served; confirm the specific
   routes exist inside the *running* pod's image, not just the exported
   archive.

## Don't re-run completed phases

Each stage writes a receipt; if a later phase fails, reconcile the existing
receipt before retrying an earlier one. Never rebuild/re-export an image
that already has a recorded passing build+export receipt for the exact
source commit.
