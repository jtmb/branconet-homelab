# Kubernetes 1.37.2 controller-only native binary qualification

The existing F-backed task root owns H/kubernetes1372-binaries, where H is
platform-upstream-review-20261027/autonomous-hardening-20261028. No node downloads,
binary replacements, services, builds or package repositories are part of this work.
The declared complete peak is 7GiB, admitted only with at least 15GiB Windows C free
and 15GiB retained on both physical F and the native F-backed filesystem.

Source scripts/migration/qualify-kubernetes1372-binaries.py downloads exact official
https://dl.k8s.io/release/v1.37.2/bin/linux/amd64/{kubeadm,kubelet,kubectl} plus .sha256,
.sig and .cert files. Each complete blob is checksum verified and ELF amd64 checked.
Official cosign v3.1.4 is pinned to SHA256
424e2c97d0b45fd7a6b608a87f090f35633f4c23ece5f092d48bba11aaf4bbfa,
bound to the official release checksums and GitHub asset digest. Its verify-blob
checks require krel-staging@k8s-releng-prod.iam.gserviceaccount.com and issuer
https://accounts.google.com. No certificate, SCT, transparency log or signature
bypass flag is used. Verification HOME/XDG/TUF/TEMP state stays in the private leaf.

The finite scanner source is scripts/migration/scan-kubernetes1372-binaries.py.
Its initial filesystem-mode attempts returned null; the unchanged nonempty-results
gate rejected them. Failed reports and original source remain immutable. Exact
Trivy 0.76.1 source documents that filesystem disables individual-package analyzers,
and Go binary detection requires executable mode. The additive
scripts/migration/scan-kubernetes1372-binaries-rootfs.py uses rootfs mode with the
same bounded scanner and every original named assertion, plus mandatory actual
Go 1.26.10 package detection. Verified local blobs change mode 0600 to 0500 only;
all content hashes and publisher signatures remain unchanged. No binary is executed.

The corrected scan retains 1GiB memory, no swap, 2CPU, 128 tasks, Nice10, private
credentials, explicit empty configuration/ignore input, full package results, fresh
public vulnerability DB, explicit Java identity index, CISA and all before/after
input hashes. No suppression is added. Reports remain package evidence rather
than proof of reachable exploits or complete security acceptance.

After successful complete scans, summarize.py emits authority.json using the native
role schema: signatureTool{path,sha256,cacheDirectory}, binaries{NAME:{url,sha256,
bytes,blob,checksum,signature,certificate,signatureVerification,scan}}. Each artifact
reference binds an absolute F path and SHA256. Scan projections bind the unchanged
original full results and receipt; they do not manufacture another scan. Actual
HIGH/CRITICAL IDs are observedHighCriticalVulnerabilityIDs; reviewedVulnerabilityIDs
starts empty for coordinating risk review. Node originals/backups/prestage records
are added later by root. Do not represent residual findings as accepted automatically.

Required verified binaries, cosign and its small private signature cache remain for
the native role's re-verification and actual staging consumer. Retire them after
that consumer/acceptance and authority-regeneration review. Generated DB and analysis
runtime are retired after the scan consumer with exact ownership, hashes, process
and mount checks; cleanup receipts retain measured paths/bytes. No Windows recovery
is inferred from Linux filesystem recovery.
