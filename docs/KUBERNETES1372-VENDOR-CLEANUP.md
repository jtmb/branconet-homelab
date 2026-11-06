# Terminal native vendor cleanup

`scripts/migration/reconcile-kubernetes-vendor.py` prepares and consumes one
explicit cleanup plan under `H/kubernetes1372-vendor-cleanup`. It defaults to
`inventory`; subsequent phases are `windows` and `apply`. This source has not
been executed. Run Linux inventory/apply only through the established protected
root launcher, and Windows handles through native Windows Python.

All phases require `--success kubernetes-maintenance-receipts/RUN_ID-result.json`
and `--success-sha256 SHA256`. The result must prove terminal successful native
apply and exactly three completed native host records bound to the same intact
authority. Before Linux inventory and again before deletion, read-only SSH
verifies all three installed binary versions on every original node, actual
Go1.26.10 build information, target SHA/size, original path/owner/mode/mtime/xattr
bindings, and the original cluster node UIDs with Ready v1.37.2 kubelets and
independent containerd2.4.2. No frozen runtime success is replayed.

Intrinsic authority SHA256 is
`bb96c82be216747db666b2ef9d10a927688df7e7119b6f3f2775605b6d5e9859`.
The only executable targets are its exact kubeadm, kubelet and kubectl blob
paths, and its pinned cosign v3.1.4 file under `H/kubernetes1372-binaries`.
The plan records complete metadata, actual logical/allocated byte counts, all
paths, owner, F UUID, source hash, exact official download URLs, checksums and
retained signature/certificate/scan references. Cosign's exact official release
URL and checksum-list binding are checked. No arbitrary caller path or glob can
select executable targets.

The authority's private signature cache is eligible only if its entire tree
matches the inspected fixed directory/file set, all files are regular, and its
JSON content is recognized TUF metadata. The trusted-root file must match the
cached signed targets hash and length. Its regeneration recipe is online TUF
refresh through the pinned cosign verification command with the original exact
publisher identity/issuer and no bypass flags. An unknown directory, file,
failure/log record or unrecognized metadata preserves the **entire cache** as a
named exception; the four independently qualified executables remain separate
candidates. Signatures, certificates, checksum lists, scan reports, original
authorities and verification/failure receipts are never cache targets.

The original complete Linux reference guard is loaded only at its fixed SHA256
`3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87`.
It checks the entire vendor leaf for processes, open files, mappings, active
systemd units and mount namespaces. Windows must subsequently open every planned
file/directory with exclusive native handles. Apply repeats Linux references,
live runtime verification, exact target identities/hashes and protected hashes.
Every existing file under H outside the selected targets and this cleanup leaf
is hash-protected. An observed safety failure records its exact target(s) and
prohibits retry through this helper; an apply intent is also never replayed.

Files are unlinked individually only after their exact checks; cache directories
are removed only after becoming empty. No recursive deletion, native installed
runtime path, node write, original rollback file, snapshot or user data is in
scope. The final receipt lists actual removed paths/bytes and retained exceptions,
and its SHA256 is printed for the coordinator to retain. Linux allocated recovery
is reported separately; Windows recovery is not claimed.

Raw original installed binaries remain protected until the next accepted
security-patch/recovery generation. They are unique original rollback sources,
not regenerated official downloads. This helper never selects them. Verification
performed during source preparation was Python parsing and whitespace review
only, with no generated plan or cleanup execution.
