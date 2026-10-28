# xTeVe to maintained Threadfin

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
The full five-milestone goal remains active. This is one application transition.

## Delivery and preservation

Selected upstream: `ghcr.io/volschin/threadfin:v3.4.0@sha256:79ba430d81feccaa36865cc9ecc905e5cb5d16f593965e30cb2feda128b43216`.
Its amd64 manifest is `sha256:c08ba41338bf9660406e6528e765050c5d3b7484483b7ca34f6edbae1d37c748`.
No derivative image was built. The existing xteve release, Services, native
Secret, two Longhorn claims and SMB IPTV claim remain the delivery identities.

Original state remains at the root of `xteve-data-0`. The selected runtime uses
only its separate `threadfin-20261026-0a4e4fd891c1` directory. The original
`/config` mount is read-only. All 108 original mapping keys, 29 active channels,
channel numbers, names, categories, guide choices, logos, provider choices,
tuner identity and existing authentication are compared with keyed hashes.
There are zero existing application accounts; none were fabricated.

The native parser regenerates provider metadata. A guarded, repository-backed
copy maps only `tvg-id`, `_uuid.key`, `_uuid.value`, `_values` and the equivalent
dummy-guide label, matching channels bijectively by exact URL and provider.
It retains all other user fields. Settings version 2.1.0 maps to the successor's
native 0.5.0 metadata version; automatic updates remain disabled. The observer
requires the exact copy proof tied to the original baseline, rather than
treating changed channel IDs or counts as acceptable drift.

A bounded nonroot Nginx companion preserves old XMLTV paths and the public
discovery brand literal used by existing tuner clients. This `DeviceAuth`
literal is protocol branding, not a user credential. Existing Service ports
remain 34400; their target is the same-Pod compatibility gateway on 34401.
The original SSDP gateway remains unchanged.

## Recovery and failed attempts

Complete cold state and config archives passed full NAS read-back and age
authentication before cutover. No original or failed state was removed.

| Archive | Ciphertext bytes | SHA-256 |
| --- | ---: | --- |
| Complete original state | 138724628 | `a08f07dcc9ea2daecf6be681b3a8bd5e63a4595ebf9122b21bce11ba693295b3` |
| Complete original config | 10452 | `1ae278990cf82d04f439ce69d58f998fad320be435558c01e44fb43fa855f2ed` |

The first isolated copy, `threadfin-20261026-d19cde2b3889`, initially failed
the vendor metadata-version check. After the explicit metadata mapping it
started, but preservation failed: only five channels remained active and 51
mapping IDs changed. Production was rolled back through Flux at
`d7d96f6b1d02adfce3de492ff58c6507f11461b8`; the original 108 mappings and
29 active channels passed again. The failed prefix and all diagnostic receipts
remain protected evidence. No failure receipt was overwritten.

The corrected copy's canary passed the complete preservation comparison and
all nine routes. It also passed the configured FFmpeg remux: all 100 synthetic
video frame hashes remained equal, with valid stereo 48 kHz AC3 audio. This
test created no disk files and opened no real provider stream. The successful
canary Pod, ConfigMap and NetworkPolicy were removed using UID preconditions
before production publication. Original state was re-observed immediately
before publication and still matched the copy's baseline.

## Current acceptance

Chart revision `7535d57b63c88f9ba6868f48585a439d35092a1b` enabled the corrected
state and compatibility routes. Production passed complete comparison with
Pod UID `260533a8-023c-464e-b6d8-27695e322fc4`. The distinct Flux restart at
`0de054992e5938543855d099efc1e484feee72be` passed again with Pod UID
`2beb92f4-b66c-4ce7-926a-d1e6e04bc691`. Both containers have zero restarts;
the observed immutable main image matches the selected upstream digest.
Private main, validated and live source agree on the restart revision.

All 108 mapping identities and 29 active channels remain, along with settings,
authentication, tuner identity, native Secret, PVC/PV and Service identities.
The nine routes passed against the internal Service and again through all three
published node addresses (27 checks). The API remains disabled with HTTP 423.
The 18:15 UTC health check found three Ready nodes without pressure, 55 Bound
PVCs, all 34 HelmReleases and Kustomizations Ready, no unavailable Deployment
or DaemonSet, and 41 healthy attached Longhorn volumes. The four failed
diagnostic Pods are explicitly retained failure evidence, not healthy workloads.

Exact private evidence is under the existing authorized F:-backed root:
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`.
Receipts: `upstream-xteve-20261026/transition-baseline.json`,
`transition-final-original-baseline.json`, `compatible-state-copy-r2.json`,
`canary-preservation-r4.json`, `canary-configured-ffmpeg.json` and
`canary-retirement.json`, `production-after-r4.json`,
`production-restart-r4.json` and `published-node-routes.json`. Frozen observer source is
`control-source/upstream-xteve-20261026/qualify-upstream-threadfin-r4.py`.
The source, complete encrypted backups, failed prefixes and unique receipts
are retained. Generated publisher exports and empty Ansible scratch were
reconciled, removing **1065947136 allocated Linux bytes** across 4683 paths.
[Exact removed paths, checks and retained exceptions](TASK-OUTPUT-INVENTORY.md#threadfin-checkpoint-reconciliation-october-26-1816-utc).
No Windows disk recovery is claimed.

The distinct encrypted metadata archive is 9751060 bytes, SHA-256
`c91775a5fd70066e45a644f76c50305b07b5e3cbf606bf9284aa1f5af13dd3a5`.
Every member was verified locally; the complete NAS read-back passed age
authentication. Its inventory includes the exact executed sources, observations,
copy proofs, unique failures, current scan, publisher and cleanup receipts.
Original cold ciphertexts are not duplicated inside the metadata archive.

Rollback remains the retained `d7d96f6b1d02adfce3de492ff58c6507f11461b8`
chart behavior: original immutable xTeVe image, compatibility disabled, original
root state rather than the successor subdirectory. Preserve both directories
and the cold backups. Recheck post-cutover user changes before any rollback;
an image switch alone is not a new-data restore procedure.

## Security and remaining gates

The selected vendor artifact's completed scan reports 0 Critical, 8 High,
287 Medium, 16 Low and 1 Unknown rows, with no current KEV intersection.
Four High IDs occur in two bundled Go targets: CVE-2026-111943,
CVE-2026-78667, CVE-2026-78669 and CVE-2026-97031. These remain vendor findings;
this transition is not a clean-security or unknown-zero-day claim.

Real provider playback, long-running streaming and personal UI acceptance are
not established by the synthetic remux or metadata comparisons. Final Codex
IAB acceptance occurs only after all implementation. Plex, ruckus-db,
WordPress, platform/fleet security, owned publication and trusted TLS remain
separate open work. GitHub Actions stays disabled; BORTUS application work
remains in its separate owner chat.
