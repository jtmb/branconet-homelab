# Patched ELF image build adapter

The separate `build-bortus-patched-kubectl-image.py` composes the unchanged
release-context validator and five-label image receipt with a completed custom
kubectl build. Default release builder, Dockerfile and export/preload ABIs are
unchanged. Root/app owns the separately reviewed Dockerfile change; this adapter
does not edit frontend source or put a binary in Git.

The raw Git source archive/manifest remains the main Docker stdin context. A
second named BuildKit context `bortus_kubectl` contains only `/kubectl`. Its
exact expected SHA is a nonsecret build argument. The consumer source contract
requires the reviewed COPY, ARG and sha256sum check; there is no mutable URL or
upstream release substitution. Actual image content/security/runtime acceptance
still requires root's independent post-build qualification.

The adapter hash-binds an independently pinned completed security-build receipt,
its ELF, version output, Go build metadata and exact source/vendor diff. It
also verifies the compact receipt's metadata origin/path/count/SHA, bounded
metadata sidecar, complete ZIP path inventory, payload hashes and every CRC.
Recorded origin pointers are validated as metadata; supplied local files are
independently pinned and copied, never blindly opened through a receipt pointer.
It requires the qualified upstream source/Go archives and all five module pins,
every actual build command completed0, and exact custom dirty version. The ELF
must be64-bit little-endian x86-64, bounded and checksum-identical. A public stub
fixture qualifying this contract is not actual Go or binary security proof.

The source-bound Dockerfile consumer is exactly:

```dockerfile
COPY --from=bortus_kubectl /kubectl /usr/local/bin/kubectl
ARG BORTUS_KUBECTL_SHA256
RUN echo "${BORTUS_KUBECTL_SHA256}  /usr/local/bin/kubectl" | sha256sum --check && chmod 755 /usr/local/bin/kubectl
```

The callable is `build(context, manifest, commit, context_sha, manifest_sha,
security_receipt, receipt_sha, binary, version, build_info, vendor_diff,
diff_metadata, runtime_parent)`. The CLI exposes corresponding required flags,
including `--security-receipt`, `--receipt-sha`, `--binary`, `--version`,
`--build-info`, `--vendor-diff` and `--diff-metadata`. Root supplies independently
pinned public artifacts, holds exclusive builder/tag ownership and verifies
named BuildKit context support before dispatch. The existing immutable source
context producer remains unchanged.

Local run ownership comes from the existing release Run; inputs are bounded,
nofollow, owned and inode-stable. Only the fixed james@192.168.0.4:2002 SSH
transport is used with strict known hosts, BatchMode and no forwarded agent.
A fresh exclusive0700 stage under the verified owned home retains public binary
transfer/build intents. Its named-context directory contains only the600 ELF;
receipts and empty Docker config are outside that context. Transfer and fresh
pre-Docker hashing refuse substitutions, extra files, symlinks or an existing
stage. Existing image tags refuse; no overwrite/adoption/replay is supported.
SSH stage logs are bounded to128MiB each; remote tag output is bounded to64KiB.
Transfer, metadata/query and build waits are at most120s,30s and2400s respectively.
Every owned child pipe, session and direct process is independently closed/reaped.

Both local and remote pending intents are fsynced before Docker dispatch. Source
and ELF hashes are checked around streaming/build; lost replies or failed flushes
retain pending/uncertain state. Only owned SSH/Docker CLI sessions are stopped
and reaped on timeout. Docker daemon work may still be uncertain after lost
reply; no remote automatic retry, image removal or cleanup mutation follows.
The root coordinator must hold exclusive builder/tag/run ownership; there is
no atomic Docker tag compare-and-set.

`record.json` retains the existing five-label/completed receipt shape accepted
by export/preload. Separate protected `injection-binding.json` binds that exact
source/context/owner/config image ID to all custom-binary proof hashes. Root must
carry and independently verify this sidecar, both completed records and actual
launcher terminal0; legacy export consumers alone do not qualify the patch.
Base completion flushes first while the binding remains pending; final binding
flush is last. A failed final flush cannot qualify the pair, even if one visible
record already says completed. Config image ID remains distinct from OCI manifest/runtime
digest. Security, runtime and deployment flags remain false. See
[custom build](BORTUS-KUBECTL-SECURITY-BUILD.md) and
[release builder](BORTUS-RELEASE-IMAGE.md).

## 2026-10-12: integrated patched-binary image adapter

The [root qualification](../evidence/bortus-patched-kubectl-image-root-20261012.json) independently verifies all10 raw native files,50 retained originals and1,879 CRC-valid ZIP members. Three source/test files and the dedicated image-adapter doc are integrated; later root build/scan sections are preserved. All21 POSIX orchestration controls pass without skips in2.510s (2.620s wall), with seven original sources unchanged and the owned test child reaped. The first root freeze check incorrectly counted newly generated test-fixture copies as original sources; that failed harness result remains retained, and no source/test behavior was altered.

Root separately validates all six actual compiled artifacts in3.138s: complete247,076,441-byte source diff ZIP,12,741,184-byte metadata sidecar/all31,916 paths, ELF, completed build receipt, actual version and Go build metadata. Their identities and bytes remain unchanged. These checks call no build, transfer, SSH or Docker operation. The default builder/export/five-label contracts and frontend Dockerfile remain unchanged.

A future source-linked build must carry both completed image and injection receipts, exact owner/config/context identities and actual launcher terminal0. The adapter supplies the separately verified kubectl through a named BuildKit context and checks its SHA in the image consumer; interrupted or mismatched outcomes cannot qualify. Actual consumer/source image construction, full image/runtime/performance, latest-data and live schema/RBAC/admission/rollback gates remain open.

## 2026-10-12: actual e50 source-bound image build completed

The [root build receipt](../evidence/bortus-patched-app-build-e50-root-20261012.json) records actual helper exit 0 in 307.112 seconds. The canonical e50 source context includes the approved named-context kubectl consumer and pinned Trixie runtime base. Completed build and injection sidecars bind the same source, owner, context, manifest and config image ID. Root verifies all eight stage-log hashes, exact five-label inspection and absence of the owned supervisor/helper/observed children. Inputs remain unchanged.

The config image ID is `sha256:db6a14d34ee75d8477e03d7efd0323100ca8b85941b6a46f96edda80d3e86bbc`; it is not a qualified OCI/runtime digest. The sidecar binds the separately reviewed kubectl ELF SHA `a3c4741294f061550b30bd2e3f357197ffbac37eefc5a45d686fe9cd29032b75`. Actual archive/layer contents, full image security, runtime and deployment acceptance remain pending. Performance evaluation is separate; this image retains the eight-request production cap.

## 2026-10-12: actual e50 export and effective image contents verified

The [independent root export review](../evidence/bortus-patched-app-export-e50-root-20261012.json) records actual export/supervisor exit 0 in 66.877 seconds. Root verifies the complete 1,197,207,552-byte archive SHA, 71 outer members, Linux/amd64 config and exact five source labels, all 17 ordered layer hashes/diff IDs and 41,240 layer entries. Effective final files contain the exact reviewed custom kubectl and native selector ELF, all eleven canonical migrations, Prisma schema/support files and entrypoint. Source content and nonroot runtime/entrypoint settings match. Owned supervisor/helper/observed children are absent. The config image ID remains distinct from an OCI runtime digest.

Full-image security scanning is separate and in progress; image/application runtime, performance, latest-data, guarded schema/RBAC/admission and live/rollback acceptance remain open. This export neither executes the image nor deploys it.
