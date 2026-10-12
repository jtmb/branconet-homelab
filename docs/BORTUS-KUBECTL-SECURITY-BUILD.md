# Custom kubectl security build

`scripts/migration/build-bortus-kubectl-security.py` is separate from the unchanged
release image builder and Dockerfile. It consumes local public archives already
downloaded and independently verified by root. It has no download, image injection,
SSH, deployment, kubeconfig or cluster API interface. Actual compilation remains
root-owned; local fixtures qualify orchestration only.

The reviewed upstream source is Kubernetes v1.37.1, peeled commit
`f78e722310e50bcaca9276be22276d9e91d91308`, source archive SHA-256
`d58492a058ac7cb1db0829a9e12317024f48d4bcbf56344b32b11276f9bdc2cf`.
Go1.26.9 Linux amd64 archive is pinned to
`42d158b4d8f7b61ac0a830567c940a86098fb7aac52e467a5ebec03ef5cc2f8d`.
Upstream v1.37.2 checksum returned404 at the research checkpoint; this helper
does not invent that release. The result is a custom v1.37.1 security patch,
reported as `v1.37.1-bortus.security.1-dirty`, never an official upstream binary.

The helper pins x/net0.60.0, x/crypto0.57.0, x/sys0.48.0, x/term0.46.0 and
x/text0.42.0 using upstream pin-dependency and update-vendor scripts. It retains
the complete original source inventory/bytes and exact changed-path before/after
bytes, including vendor changes. Fresh Go module output and binary build metadata
must agree with the pins; Go1.26.9 and x/net0.60.0 are required in the binary.
The retained diff also includes any go.mod/go.sum updates by the explicit module
inventory query; it is frozen after pin qualification and before compilation.
Module inventory explicitly uses `go list -mod=mod -m all`; default automatic
vendoring cannot compute `all` after the vendor directory exists. Before any
dependency fetch/build, the supplied real Go must pass a tiny no-network local
module/replace/vendor fixture using that exact query. Local controlled-child
tests check wiring; they do not claim to have executed a real Go toolchain.
Build dispatch calls upstream `hack/make-rules/build.sh cmd/kubectl`, the same
script used by its Makefile; no host make installation is needed. Upstream
dependency scripts still require their normal bash/Git/jq/rsync prerequisites.
The security database identifies fixes for the four scanned kubectl High entries;
this is not a zero-vulnerability or image security acceptance claim.

```sh
python3 -B scripts/migration/build-bortus-kubectl-security.py \
  --source-archive /approved/inputs/kubernetes-src.tar.gz \
  --go-archive /approved/inputs/go1.26.9.linux-amd64.tar.gz \
  --runtime-parent /approved/owned/runtime --run-id <new-12hex> --timeout 2400
```

The existing owned parent permits0755 without group/world write. A fresh0700
run is created exclusively and its parent entry flushed; logs and receipts are600.
Any existing run refuses, including prior failure or uncertainty. Inputs are
owned regular nofollow/nonblocking files, hash-bound with stable inode/size/times
before/after copying. Archives are bounded to512MiB compressed,2GiB tree,
128MiB/member and100000 entries. Paths, duplicate headers, unsafe parent/link
chains and special files refuse before extraction. Safe links resolve only to
terminal regular files or directories in the same tree; hardlinks require
regular files, and link chains refuse. No archive-created link is traversed.
The exact official source archive is flat and is placed inside one synthetic
owned `kubernetes` directory without rewriting TarInfo offsets. A wrapped source
archive refuses; the Go archive still requires its literal `go` root. The three
official cluster/gce directory symlinks and two file symlinks are retained.

Fresh empty HOME, GOPATH, GOCACHE and temporary directories isolate the build.
No ambient environment, Git credentials, SSH agent, operator config or module
credential settings are forwarded. Public module proxy/checksum services are
fixed; GOTOOLCHAIN=local prevents implicit toolchain downloads. All commands use
GOMAXPROCS=2 and a parent GOFLAGS=-p=2; upstream dependency scripts override or
unset GOFLAGS during their module/workspace steps. The separate build stage
retains -p=2. GOMEMLIMIT=4GiB is a soft Go heap limit, not a cgroup/RSS cap.
SOURCE_DATE_EPOCH pins the reviewed upstream tag timestamp.
The upstream version-file override binds the explicit custom dirty version,
avoiding git-archive's automatic clean/archive version inference. These inputs
improve reproducibility; no independently repeated bit-identical build is claimed.
All commands use
one original absolute budget of at most3600s. Each command has a fsynced pending
intent before its owned process session starts, bounded retained logs, actual exit
and completion/uncertainty metadata. Failure stops only owned children/session;
the250ms reap margin is closure only. Lost reply, timeout or failed confirmation
cannot grant success or authorize automatic retry/adoption.

Root must independently review the actual source/vendor diff, output checksum,
version/build metadata and default binary scanner result. A separately qualified
image injection contract must bind those bytes to a new app source/context/image,
then renew relevant image/runtime/function/performance gates. Current image
contracts and their retained default scan counts remain unchanged. See
[release image builder](BORTUS-RELEASE-IMAGE.md).


Root [integrated helper qualification](../evidence/bortus-kubectl-security-build-root-20261012.json) verifies all9 selected raw native files and84 retained originals, then passes18 controls without skips against the current checkout. Actual unittest time1.805s/root wall1.891s; frozen source hashes stay unchanged. These are controlled Python/bash child/archive/version fixtures, not actual Go compiler acceptance. Default image builder remains unchanged. Root separately dispatched the exact helper on the existing build host with two-core affinity, pinned public archives, fresh HOME/module/cache and one2400s budget. Supervisor/helper PID/start identities were observed live in preparation; no final binary, scan, image injection or cluster deployment is yet accepted.


### Actual custom-build preparation failure, retained without replay

The [actual build receipt](../evidence/bortus-kubectl-actual-preparation-failed-20261012.json) records terminal1 before the compiler stage. Actual Go1.26.9 version/offline module ABI, five dependency pins, upstream vendor regeneration and the full module query passed. Full source diff ZIP275523080bytes/43022members is CRC-valid. The detailed37388-path list would make the main record3757314bytes, above its unchanged1MiB bound; a later failure save also remains bounded, leaving the prior5960-byte pending record. All observed commands and supervisor are absent.

31730 newly inventoried paths are upstream module cache under `_output`;5465 changes are mode-only. The original full diff/archives/logs stay intact and this owner is never reopened, adopted or replayed. The next source correction stores detailed diff metadata separately under a finite bound and retains compact count/SHA identity in the main record. Local18-control success did not cover this real source size. No compiler, final binary, image injection or cluster change is accepted.
