# Local operator OCI scanning

GitHub Actions remains disabled. The existing worker1 scanners and their original
database pins, receipts and artifacts remain unchanged. This opt-in path runs on
Ubuntu WSL and records `executionHostKind: wsl-local-operator`; source provenance
remains either an existing completed historical CI artifact or an explicit local
operator build. It makes no new Actions request and never deploys an image.

The existing exact OCI manifest/config/layer verification, original CI proof
checks and local build proof checks are retained. Reports serialize Trivy Results
only, with every analyzer enabled, no ignore/suppression file, no Secret scanner
and no image environment/config/history in the structured report.

## Fresh public inputs

`refresh-trivy-databases.py` fetches a new exclusive native generation from pinned
public `mirror.gcr.io/aquasec/trivy-db` and `trivy-java-db` manifests. It verifies
each complete compressed blob and extracted database/metadata SHA, schema,
bounded archive members and gzip footer. It preserves all old generations and
the new original compressed blobs/manifests. It runs in a measured 1 GiB, no-swap,
two-CPU, 128-task user unit with a 20-minute outer deadline, physical C: capacity
checks and an 8 GiB fresh-generation allocation bound.

The current reviewed generation is
`trivy-db-generation-20261024-e06eced058164f38a7a36670fd89e986`.
Its vulnerability database UpdatedAt is `2026-10-24T19:09:13.779511838Z`; its Java
index UpdatedAt is `2026-10-24T01:07:32.115560183Z`. All source bytes are pinned in
`scan-local-oci.py`. The scanner preserves the existing 24-hour vulnerability
database age bound. Expired input requires a newly reviewed generation.

## Setup and scan

Run an immutable reviewed native copy of both adjacent scanner/controller files
as the existing WSL operator. The explicit setup copies the verified Trivy binary
and fresh databases into its own private native cache without replacing old or
conflicting files. Source/helper hashes bind a new immutable input seal.

```sh
python3 scripts/migration/run-local-oci-scan.py --apply --phase setup
python3 scripts/migration/run-local-oci-scan.py --apply --phase scan \
  --service pihole --source-kind local-operator --local-run-id RUN_32HEX \
  --local-provenance-sha256 SEALED_LOCAL_PROVENANCE_SHA256 \
  --archive-sha256 OCI_ARCHIVE_SHA256 --root-descriptor sha256:ROOT_HEX
```

Seal a successful local build first with `receive-local-image.py`, using its
exact original final receipt SHA. That receiver retains originals, creates a new
exclusive protected native artifact copy, and repeats source/blob/tar/resource
checks plus physical C: capacity admission and observations during transfer.

For historical CI artifacts, use `--source-kind github-actions` and exact
`--ci-run-id`, `--ci-artifact-id`, `--ci-provenance-sha256` with the archive/root
identities. This reads already retained proof and OCI files, without an API call.

Each setup or scan uses its own labelled user service. It measures 1 GiB memory,
no swap, two CPUs, 128 tasks and nice 10. A private network namespace, private
users/devices, no-new-privileges, read-only system/home, protected database files
and inaccessible SSH, Windows user files and runtime sockets isolate the task.
The outer deadline stays 900 seconds and Trivy's observation stays 480 seconds.

The native filesystem retains 25% plus 8 GiB free, including existing scan input
reserve; actual physical C: retains a separate 8 GiB reserve plus pending work.
The private scanner tree stays below 8 GiB allocated. Capacity, source and input
checks continue through each run. Strata and shared Docker state remain intact.

Observe the returned unit/PID and attempt receipt to a terminal state; an
observation timeout never permits a duplicate run. Scan success is evidence for
the exact archive/database combination and does not prove runtime compatibility,
data preservation, route behavior, browser acceptance or absence of unknown
vulnerabilities.

## Exact official patch candidates

`scan-upstream-patches.py` separately scans four fixed official registry digests:
phpMyAdmin5.2.3/PHP8.3.36, WordPress7.1.3/PHP8.3.36, Redis8.6.7 and nginx1.30.6.
It never imports or starts an image. This is a candidate assessment, not adoption.
It reuses and authenticates the existing local tool/databases in place, with
read-only DB bindings and the same exclusive local scan lock. No database copies,
Actions calls, production credentials or image environment reports are involved.

Each explicit `--apply --service NAME` starts a new private native attempt in a
1GiB/no-swap/two-CPU/128-task/nice10 user unit. It preserves the900-second unit
deadline,480-second observation,24-hour vulnerability-DB age,64MiB Results-only
report,16MiB diagnostic and filesystem/physical-C reserves. Its own allocation
is bounded to2GiB. Registry access requires networking; operator home and Windows
user files remain hidden. Only the owner's systemd bus sockets are bound to
measure the actual existing unit/cgroup; this does not grant another identity.
All analyzers remain enabled, with an empty ignore/config and pinned template.

The source, exact command, effective cgroup and input proofs, full unsuppressed
Results hash and fixable critical/high counts bind every successful receipt.
Failures remain failures in separate attempts. Do not launch another scan until
the current unit is terminal. These compatible-version candidates still require
data/route/runtime checks and chart validation followed by Flux for adoption.

## Ansible entry point

`playbooks/local-oci-scan.yml` uses `connection: local` and delegates the same
controller command to localhost. It never contacts the cluster. Defaults are
disabled; check mode starts no unit. Set `local_oci_scan_apply=true`, phase and
the corresponding exact public identity variables in a protected settings file.
No sudo password or production credential is required.

## Dedicated native F profile

CoreDNS, Jackett, Plex, Unpackerr, Homepage, http-echo, qbittorrent-current and pihole-exporter accept the explicit offloaded storage profile
for local-operator artifacts; Jackett also retains its historical offline CI
proof path. All previous frozen helpers and C-backed originals remain unchanged.
New Unpackerr/Homepage/http-echo/qbittorrent-current/pihole-exporter receivers stay on native F; previous services retain their
original sealed paths. The profile preserves the exact size/source checks,
1 GiB/no-swap/two-CPU/128-task bounds, 24-hour DB age and scanner deadlines.

Each offloaded process fully hashes fixed tool/database inputs once. Subsequent
checks reuse that hash only while device, inode, length, UID, mode, link count,
nanosecond mtime and ctime all match. Any identity change forces a full hash;
changes during hashing refuse. Page-cache advice releases completed input ranges
to avoid caching both loop filesystem and backing file under the same 1 GiB
cgroup. Archive and source/provenance verification remain complete. The sealed
receipt records this policy. This optimization does not suppress any analyzer,
package metadata or vulnerability finding.
