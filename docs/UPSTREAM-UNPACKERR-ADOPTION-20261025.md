# Unpackerr official image acceptance — October 25, 23:54 UTC

The original Flux-owned Unpackerr service runs official **0.16.1**, image
`ghcr.io/unpackerr/unpackerr:0.16.1@sha256:406586865431b40b29353d899fb75a788f5384743f7f381444db5fe55d206914`.
Containerd reports the exact published index digest; registry metadata also
binds amd64 child `sha256:7000ff3072154ea8f82d7905c6214571b8bbfb68c937ed989dab3cac39f6017f`.
The vendor build uses **Go 1.27.0**, compared with 1.27.3 in the retired custom
runtime. DockerHub/GHCR release and latest tags currently select the same
amd64 payload. No derivative image was rebuilt or published. This is vendor
ownership correction, not a zero-CVE claim; current vendor CVE review stays open.
[Vendor installation](https://unpackerr.zip/docs/install/docker/) and
[release](https://github.com/Unpackerr/unpackerr/releases/tag/v0.16.1).

Private chart pause `3438b97c97d25fcc3a78aaaa81d8b1b375b2e2ba` stopped only
Unpackerr. The full configuration backup contains 1 file and
17,148 file bytes; its 20,692-byte encrypted archive SHA256 is
`fb5dc165d03b4cdd7bdd4f462dec78b241b885081216903bb9d23764fb5e7a4d`. Complete source authentication, NAS checksum/read-back
and age decryption passed before adoption. The read-only reader was UID-deleted;
the SMB downloads corpus was neither walked nor copied.

Adoption `7e526a40d51ea7314e050bd9b1e69273295d6546` and controlled restart
`2a4adb51e107700028eb7792381044037cf7f235` both passed existing local validation,
validated and Flux. All three observation Pod identities differ. Complete
configuration HMAC/metadata, original Deployment and HelmRelease identities,
native Secret UID/version/content, original Longhorn and SMB claims/PV specs,
and deployment settings other than reviewed image/restart annotation matched.
Both new Pods retrieved Arr queue information with no observed authentication,
ERROR or FATAL lines in the bounded current log window. Raw logs and native
configuration/secret values were not written to repository evidence.

The official binary SHA256 is `f1fcaba2605ade7745ea72cc941a88772a873df8a561f621388b40196bb4d384`.
One bounded isolated ZIP check passed exact extraction/ownership, mock Radarr
queue disappearance and cleanup retaining preexisting/archive/library files.
It used loopback-only user/network namespaces, 512 MiB memory, no swap, one CPU,
64 tasks and a 180-second outer deadline. This is ZIP/mock-import acceptance,
not a real Arr import, all archive formats or NAS ACL qualification.

The first observer's startup-log expectation, an early pre-ready observation,
the index-versus-child image-ID mismatch and the legacy fixture toolchain guard
all remain recorded as failures with their exact frozen sources. The corrected
observer binds both finite published index/child identities. The fixture now
has an explicit vendor 1.27.0 profile while retaining default legacy 1.27.3.
These corrections do not change application data, extraction limits or resource
policy and do not hide the older vendor toolchain.

Recovery metadata is 266,516 encrypted bytes, SHA256
`7abbec923e74cbe49c9cb5e22563c54fb7ce4ec1420396082aa603530a5be75c`. Its full authentication, member checksums and NAS read-back
passed. It includes this stage's distinct sources, observations, failures and
verification key only inside the encrypted archive. Originals and the existing
profile-bound recovery-key backup remain; no independent restore is claimed.

The 23:52 health check found all 3 nodes Ready, 55 PVCs Bound, 34 HelmReleases and
all desired workloads available; 41 Longhorn volumes had no unhealthy attached volume.
Only the two previously retained Seerr diagnostic failures remain. Final IAB and
current vendor vulnerability review stay open; 16 derivative transitions remain.

All generated evidence stays under the existing authorized F:-backed ext4 root
in [the output inventory](TASK-OUTPUT-INVENTORY.md). Exact private result:
`operator-control/unpackerr-upstream-adoption.json`; observations/backup:
`upstream-unpackerr-20261025`. Frozen observer manifest SHA256:
`1591f838988f6c1120240a4c173e6d9ec67d26675476150648cf99fe9332d9ac`.
The source and Ansible profile are maintained in this repository. No build ran.
Verified cleanup removed 38,125,568 allocated Linux bytes; all exact paths and
retained exceptions are recorded in the inventory. No Windows recovery claim.
