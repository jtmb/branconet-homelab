# Platform residual review — 2026-10-25

This initial read-only observation and remediation review now includes the completed, separately authorized Ubuntu Pro client patch on both workers. Its exact applied result is recorded below; no platform upgrade or new scan was performed by this review. Published Go/module/distro fixes still remain in current platform images; several have no newer stable vendor patch release. Longhorn 1.13.0 is an available coordinated storage upgrade, and newer individual Flux controllers have explicit API/RBAC migration requirements. Neither is classified as an impossible fix or an authorized independent image swap.

Observations began at 14:56 UTC on 2026-10-25. Strict known-host SSH read installed package metadata, cached APT indexes, service executable identities, version commands and selected Kubernetes metadata. APT simulations used `-s` without sudo. No APT refresh/install, reboot, container execution, image download, build, scan, workload change, credentials or Secret contents were involved.

## Hosts: installed and active identities

| Host | Address | Node UID | Installed/running state |
| --- | --- | --- | --- |
| masternode | 192.168.0.4 | `f2df6169-4592-4544-b62c-74d89f598648` | Ubuntu 22.04.4 LTS; kernel `5.15.0-198-generic`; Kubernetes 1.37.1; containerd 2.4.2 |
| workernode1 | 192.168.0.6 | `e8d4555f-7cea-445f-b84f-6416964045a9` | Same |
| workernode2 | 192.168.0.5 | `eda66e65-f388-4b97-b64f-a709cda81894` | Same |

All three Nodes reported Ready. Active `containerd-k8s.service` runs `/opt/containerd-k8s/bin/containerd`, version `v2.4.2`, commit `b7a25261e029d68978bbf290df0a62fc819b3c51`; NodeInfo independently reports `containerd://2.4.2`. Its sibling runc is `1.5.2`, commit `v1.5.2-0-g29dd3dc`, Go 1.26.8, libseccomp 2.6.1, libpathrs 0.2.6. The official [containerd releases](https://github.com/containerd/containerd/releases/tag/v2.4.2) and [runc releases](https://github.com/opencontainers/runc/releases/tag/v1.5.2) show those as latest stable in the observed release listings; runc 1.6.0-rc.1 is a prerelease. This does not prove their embedded dependencies free of vulnerabilities. In particular, newer Go security patches exist; no new host-binary scan or reachability analysis was performed.

`containerd.service` and `docker.service` are inactive with MainPID 0 on every node. Legacy installed packages are containerd.io 1.6.21-1 / Docker CE 24.0.2 on master, and containerd.io 1.7.19-1 / Docker CE 27.1.1 on workers. They are retained software, not the active Kubernetes runtime. Cached Docker repository candidates containerd.io 2.4.2 and Docker CE 29.9.2 would migrate this inactive package stack across major versions. Do not conflate that with patching the active custom runtime. Master also retains an old bionic Docker repository cache; it was not changed. The workers' legacy `/usr/bin/runc` prints a 1.7.19 banner but a `v1.1.13` commit; this inconsistent legacy banner is not used to identify active runc.

Installed kernel package `5.15.0-198.208` and linux-generic `5.15.0.198.171` match cached candidates. So do libc6 `2.35-0ubuntu3.15`, OpenSSL/libssl3 `3.0.2-0ubuntu1.30`, openssh-server `1:8.9p1-3ubuntu0.18`, and systemd `249.11-0ubuntu3.23`. No node has `/run/reboot-required`. These are cached comparisons, not an all-CVE or livepatch assessment. Older installed kernels remain untouched.

### Concrete cached security action

Both workers have `ubuntu-advantage-tools` and `ubuntu-pro-client-l10n` at `30~22.04`. The trusted cached Jammy security index offers `37.2ubuntu~22.04.1`; the overall Jammy updates candidate is `38ubuntu0~22.04`. [USN-8555-1](https://ubuntu.com/security/notices/USN-8555-1) explicitly fixes CVE-2026-9494 (credential exposure through arguments), CVE-2026-11386 (contract-input validation), and CVE-2026-12391 (collect-logs symlink handling). Master already has the security version. No Pro configuration, attachment status or credential was read.

On each worker, the read-only simulation `apt-get -s install --only-upgrade ubuntu-advantage-tools ubuntu-pro-client-l10n` resolves to **two upgrades, one newly installed package (`ubuntu-pro-client`), zero removals**, all at `38ubuntu0~22.04`. The new package is the official package split: the updated tools package depends on it and l10n requires its matching version. This is a bounded supported host-package action for the owner, not a recommendation to attach Pro or change subscriptions. Execution and post-update verification remain outstanding.

Subsequent implementation deliberately narrows execution to security-pocket **37.2ubuntu~22.04.1**, not candidate 38. The separate [USN-8555-1 worker patch](UBUNTU-PRO-SECURITY-PATCH-20261025.md) records its exact pins, passing real read-only preflights and parent-controlled execution path. The candidate-38 simulation above remains historical evidence, not the selected transaction.

**Applied follow-up, 2026-10-25:** the parent completed that exact 37.2 transaction on both workers (`ok=13`, `failed=0`, `unreachable=0` each). Independent receipt re-verification confirms all three final package versions, only the approved package split/upgrades, unchanged kernel/boot/runtime/config/service identities and unchanged three-Node Ready/no-pressure observations. The worker Ubuntu Pro action is now complete; the initial version/cache observations above are retained historical findings. Log and exact before/after/verified receipt bindings are in the linked patch document. No other platform residual is cleared by this host-package result.

The exhaustive cached check compared every security-origin version newer than each installed package, not merely the preferred candidate's origin. It found these two rows per worker and none on master. The initial candidate-only `cachedSecurityUpdates` fields are empty because updates supersede the security versions; use the later `all-cached-security-versions-*` evidence. There are 97 total cached upgrades on master and 100 on each worker, mostly ordinary updates; these totals are not security finding counts. For example, libseccomp2 `2.5.3-2ubuntu2` → `2.5.3-2ubuntu3~22.04.1` is an updates-origin candidate and is not the active runc's bundled libseccomp 2.6.1.

Jammy security cached Release date is 2026-10-23 07:44:16 UTC. Jammy updates dates are October 24 06:25:18 on master and 01:05:48 on workers; Docker Jammy is October 22. No refresh was authorized, so later published host updates remain outside this cached observation.

## Current platform release boundaries

| Platform | Observed current | Primary publication observed | Concrete route / boundary |
| --- | --- | --- | --- |
| Calico | 3.33.0 node, calico and third-party CNI | [3.33.0](https://github.com/projectcalico/calico/releases/tag/v3.33.0), October 1; no newer 3.33 stable patch in current release list | Go 1.27.3 and listed module/EL9 package fixes exist. A same-source rebuild is a possible engineering route requiring the complete CNI/node component and network-policy qualification; latest vendor tag does not make the residuals unfixed. No such build was made here. |
| Flux bundle | 2.9.6 | [2.9.6](https://github.com/fluxcd/flux2/releases/tag/v2.9.6), October 1, latest published stable bundle in listing | Current bundled controllers retain fixes below. Individual source/notification 1.10.0 releases exist, but require coordinated CRD/RBAC/config review; do not swap compiled dependencies or standalone controller images opportunistically. |
| Longhorn | 1.12.1 | [1.13.0](https://github.com/longhorn/longhorn/releases/tag/v1.13.0) stable September 29; [1.12.2-rc1](https://github.com/longhorn/longhorn/releases/tag/v1.12.2-rc1) prerelease October 15 | Evaluate the complete stable 1.13.0 stack and exact scan before a storage maintenance upgrade. Its newer version alone is not proof that all listed package rows close. No published stable 1.12.2 was observed; the RC explicitly disallows upgrade from/to RC/preview/sprint releases. |
| Kubernetes | 1.37.1 control plane, kube-proxy and host binaries | [1.37.1](https://github.com/kubernetes/kubernetes/releases/tag/v1.37.1), September 23; [patch schedule](https://kubernetes.io/releases/patch-releases/) still lists 1.37.2 as next | Available toolchain/module fixes below are not a published 1.37.2 artifact. 1.38.0-alpha.2 is a prerelease, not a compatible patch substitute. A custom same-source control-plane rebuild would need coordinated binaries/images and cluster qualification; none is proposed as an untested drop-in. |
| cert-manager | 1.21.3 | [1.21.3](https://github.com/cert-manager/cert-manager/releases/tag/v1.21.3), October 23, latest stable observed | Exact adopted digests match retained successful scans with no C/H. Unknown rows remain. No newer patch action demonstrated. |
| etcd | 3.7.3-0 Kubernetes image | [etcd 3.7.3](https://github.com/etcd-io/etcd/releases/tag/v3.7.3), October 22, latest stable observed | Exact adopted index matches retained scan with 5 Unknown and no C/H. Older 3.6/3.5 release trains are not upgrades. No newer patch action demonstrated. |

Flux source-controller 1.10.0 changes object identity defaults and removes `serviceaccounts/token` create permission from default RBAC; explicit authorization bindings may be needed. Notification-controller 1.10.0 introduces v1 Alert/Provider APIs: conversion drops deprecated `Alert.spec.summary`, `Provider.spec.interval`, static Azure Event Hub JWT and TLS/proxy fields formerly supplied through `secretRef`. Its notes give replacement fields and the Flux 2.10 migration procedure. These are concrete integration differences, not a claim that the new versions cannot be used. [Source controller changelog](https://github.com/fluxcd/source-controller/blob/v1.10.0/CHANGELOG.md), [notification controller changelog](https://github.com/fluxcd/notification-controller/blob/v1.10.0/CHANGELOG.md).

Longhorn 1.13 requires Kubernetes ≥1.34 (this cluster meets it), introduces a three-replica global-manager Deployment, and changes storage/network-policy behavior. V2 live upgrade requires a source version ≥1.12.2 plus topology/health prerequisites; current 1.12.1 does not satisfy that source-version requirement. The documented alternative is an offline V2 transition with volumes detached and replicas stopped. This review did not discover volume-engine topology, so it does not presume the cluster uses V2 or claim every volume must be detached. Perform the owner-controlled engine inventory and preservation/maintenance planning before choosing the path. [Official V2 upgrade prerequisites](https://longhorn.io/docs/1.13.0/deploy/upgrade/v2-instance-upgrade/#prerequisites).

## Retained exact-image findings and available package fixes

Counts below are scanner package/target rows, not unique exploitable CVEs. The older platform rows come from the **October 23 audit**; only third-party CNI has a new October 25 closure scan. Reusing a fresh scanner DB elsewhere does not retroactively refresh these reports. Current runtime digests and exact report bindings are retained in `remaining-image-inventory-20261025.json` and the evidence below.

| Component(s) | Retained C/H rows | C/H rows with published fixed version |
| --- | ---: | ---: |
| Calico calico / node | 10 / 23 | 10 / 18 |
| Calico third-party CNI (October 25 exact scan) | 24 | 24 |
| Flux helm / image-automation / image-reflector / kustomize | 11 / 13 / 13 / 13 | Same |
| Flux notification / source / source-watcher | 16 / 16 / 11 | Same |
| Kubernetes apiserver / controller-manager / proxy / scheduler | 13 / 17 / 19 / 17 | 13 / 17 / 18 / 17 |
| Longhorn engine / instance-manager / manager / share-manager / UI | 72 / 76 / 42 / 37 / 18 | Same |
| Longhorn attacher / registrar / provisioner / resizer / snapshotter / liveness | 35 / 25 / 39 / 24 / 26 / 25 | Same |

Published fixed-version rows are **available dependency fixes**, not evidence of a tested replacement vendor image. Principal targets, preserving the applicable dependency line where possible:

- Go stdlib: current 1.26.3–1.26.8 builds → **1.26.10**; Calico 1.27.1 → **1.27.3**. Official [Go release history](https://go.dev/doc/devel/release) confirms October 8 security fixes in 1.26.9/1.27.2 and October 19 crypto/x509 fixes in 1.26.10/1.27.3. Calico third-party CNI's 24 H rows are four advisories repeated across six executables. Longhorn provisioner uses Go 1.24.2 and needs a supported compiler line, not a fictional current 1.24 patch.
- Kubernetes: x/crypto 0.54.0 → 0.55.0, x/net 0.57.0 → 0.60.0, x/text 0.40.0 → 0.41.0; gRPC 1.82.1 has advisory fixes at 1.82.2 **and** 1.83.1, so 1.83.2 is the combined stable target for those rows. kube-proxy also has Debian libpcre2-8-0 `10.42-1+deb12u1` → `10.42-1+deb12u2`.
- Calico calico/node: x/net 0.58/0.59 → 0.60.0. Node EL9 rows include ca-certificates `2025.2.80_v9.0.305-91.el9` → `2026.2.92_v9.0.319-90.3.el9_8`, libpcap `14:1.10.0-4.el9` → `14:1.10.0-4.el9_8.1`, openssl-libs `1:3.5.8-1.el9_8` → `1:3.5.8-2.el9_8`, and pcre2/pcre2-syntax `10.40-6.el9` → `10.40-7.el9_8`. These do not close the five remaining no-fixed-version node rows listed below.
- Flux: shared Go and x/net/x/crypto/x/text/gRPC fixes; go-git 5.19.1 → 5.19.2, klauspost/compress 1.18.5/1.18.6 → 1.18.7, fulcio 1.8.5 → 1.8.6, x/mod 0.37 → 0.40, oras-go/v2 2.6.1 → 2.6.2 where present. Alpine rows include libssl3/libcrypto3 3.5.7-r0 → 3.5.8-r0, brotli-libs 1.2.0-r0 → 1.2.1-r0, libexpat 2.8.5-r0 → 2.9.0-r0 and pcre2 10.48-r0 → 10.49-r0. Full package/component mappings remain in the inventory, not inferred across all images.
- Longhorn: shared Go/module targets above; CSI resizer additionally OpenTelemetry SDK 1.40.0 → 1.43.0. SUSE rows include glibc `2.38-150600.14.52.1` → `.61.1`, libexpat `2.7.1-150700.3.12.1` → `2.8.5-150700.3.15.1`, cifs-utils `6.15-150400.3.24.1` → `.27.1`, OpenSSL3 `3.2.3-150700.5.40.1` → `3.5.0-150700.5.53.2`, and PCRE2 `10.42-150600.1.26` → `10.42-150600.3.3.1`. Python, bind, ACL/attr, jq, kbd, SASL, rpcbind and X11 rows also have fixed versions in the retained complete mapping. Update these through the correct vendor base/component build, not host APT or independently chosen CSI binaries.

### No-fixed-version and unknown boundaries

Calico node retains five H rows: libpcap CVE-2026-6554, and CVE-2026-53613/CVE-2026-53615 each on util-linux and util-linux-core. The exact retained report has empty fixed versions. Fresh Red Hat CVE pages/API were inaccessible during this review; therefore **current upstream fix status is unverified**, not proven universally unfixed. These rows must remain visible until vendor data or a fresh exact scan resolves them.

kube-proxy retains libssl3 CVE-2026-84782. The [current Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-84782) still marks installed Bookworm `3.0.20-1~deb12u2` and newer Bookworm security `3.0.22-1~deb12u1` vulnerable; the published fixed versions shown are Trixie `3.5.7-1~deb13u3` and unstable `3.6.5-1`. That is a concrete absence of a published Bookworm fix in the observed tracker, not permission to mix distro libraries. This DTLS advisory is package-presence evidence, not a demonstrated kube-proxy attack path.

Live cert-manager index digests are controller `9f4f96a33c7774cef24466fcd85031997531a03a8d117f151126baa8d1290dcc`, cainjector `083d0e906f8eb44e255fe4ff817ae54e49f9ed82e22f1011bb4e9e4f4b8a641f`, webhook `055ac8e9de6a0ba6763794838fe38944acc650f68ebe1b01dd8be079e580f458`; each retained scan has one Unknown and no other rows. The successful five-component receipt also includes acmesolver (zero rows) and startupapicheck (one Unknown); it does not erase the prior failed attempt. Current etcd index `0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910`, amd64 `b4a41c6864baf573f5213dce18b2a95e1002ec6c5a1a26ad900c2ea166ac6d0b`, has five Unknown. None of this is a blanket clean/zero-day claim.

BORTUS application delivery belongs to its separate owner. Its retained registry 401 acquisition/scan failure means **unknown coverage**, not zero vulnerabilities. No owner artifacts were loaded or changed. Accepted application behavior checks and in-progress source recipe builds were not repeated or modified here.

## Evidence and limits

Private nonsecret evidence directory (the reused task output root): `/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/public-inputs/platform-residual-review/`. It contains host/runtime JSON for all three IPs, exhaustive cached security-version observations, both APT simulations, live platform status/spec image mappings, official release API snapshots with response hashes, two upstream Flux changelogs, and the six retained no-fixed-version rows. Small public metadata only; no public layers or generated dependencies were acquired.

Its `evidence-manifest.json` binds 26 evidence files by length and SHA256; manifest SHA256 is `2f66adb7281fff9f4ae1d857240fbb3aaf716f3ebd5a33972f55c1b529b5da4d`.

The original audit is master `/home/james/.local/share/branconet-migration/audit20261023-20261023T203418Z/reports/aggregate.json`, SHA256 `75873bb4a61a70c0fe364e40aed9736440cb2ddb97cfa11e2fa753ff6102e34e`. Exact component mappings, full fixed-version lists and report hashes are in the unchanged `docs/remaining-image-inventory-20261025.json`.

Additional retained receipts:

- cert-manager successful: master `/home/james/.local/share/branconet-migration/vendor-cert-manager-scan-20261024/attempts/7a0e48b9c421/receipt.json`; prior failed `1084eb6ad8eb` preserved.
- etcd: master `/home/james/.local/share/branconet-migration/vendor-core-scan-20261024/attempts/fc40e27815d6/receipt.json`; Results SHA256 `dd149147a218e80a41c666ce0375b352f061a8a4be16865c23b7b629d150b64e`.
- Calico third-party CNI: controller `/home/brajam/.local/share/branconet-migration/upstream-patch-scans-20261025/822a73b0488944088473ed9b3a2f7a03/receipt.json`; image `quay.io/calico/third-party-cni-plugins@sha256:0f32f48279484c0d6f0e0d0e767b2d0e1a6c6ca34cb3421a61b989d992f3df41`, Results SHA256 `200eb39b383acea46dade986a97f0faf30fd050fdbf9731c692c6df136f54875`.

The existing scanner DB validity window ends at 19:09 UTC; this review ran no scanner and makes no post-expiry freshness claim. APT caches, older report dates, missing Red Hat refresh and unscanned host binaries are explicit coverage limits. No package/API source here authorizes a disruptive upgrade; parent ownership and preservation checks remain in force.
