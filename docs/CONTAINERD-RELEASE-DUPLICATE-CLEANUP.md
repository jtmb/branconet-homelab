# Exact containerd vendor release duplicates

Completed on master and worker2 after terminal three-node Kubernetes success.
Accepted receipts under `H/containerd-release-duplicate-cleanup` record
128,000,000 and 127,987,712 allocated Linux bytes removed respectively,
including proven-empty directories. Installed runtimes and all protected inputs
were preserved. This is Linux filesystem recovery, not Windows disk recovery.
The completed generation must not be replayed; the procedure below describes
the guarded workflow and its original measured candidates.

Scope: master and worker2, exactly `/opt/containerd-k8s/releases/v2.4.2/containerd.tar.gz` and the four files `bin/containerd`, `bin/containerd-shim-runc-v2`, `bin/containerd-stress`, `bin/ctr`. Empty bin/release directories may be removed only after the exact files. Installed `/opt/containerd-k8s/bin`, CNI, configs, services, data, old timestamped backups and historical failed targets are excluded.

Official source: https://github.com/containerd/containerd/releases/download/v2.4.2/containerd-static-2.4.2-linux-amd64.tar.gz
Checksum: https://github.com/containerd/containerd/releases/download/v2.4.2/containerd-static-2.4.2-linux-amd64.tar.gz.sha256sum
SHA256: da656542e754c699a0f438eab925e6ffdbd6346a4428e659f83dc058f04dcffe

Regeneration: in one explicitly owned future leaf, fetch that exact URL with `curl --fail --location`, verify the pinned SHA256 with `sha256sum --check`, then extract only the four recorded `bin/` files using tar. No regeneration, runtime reinstall or service restart is part of cleanup. The copies have no remaining identified installation consumer after terminal native upgrade56f152 success; qualification still proves full reference absence before retirement.

CLI: `controller.py qualify --node masternode --password-stdin`, followed only after review by `controller.py apply --node masternode --password-stdin`; same finite phases for workernode2. Ansible opt-in: `containerd_release_duplicate_enabled: true`, `containerd_release_duplicate_phase: qualify` or `apply`. Protected stdin is bounded and consumed before any child. Existing Ansible process environment input is also supported; credentials are never written into source, arguments, receipts or node files.

Every phase binds terminal result56f152a9adc044478db62e3cacc65288 SHA583d6a0eece75e23940ff4d6f1a4a805dfe6b58148fc8a3d0f44a1d5a9736072, three completed native receipts, exact original node UIDs, API/kubelet1.37.2, containerd2.4.2, kernel202, Ready uncordoned nodes,28 healthy/16 offline volumes and the original full58 checker. Qualification hashes every exact file, tar member, installed runtime/CNI/config/unit state, inode/mode/time and physical allocation. The immutable original Linux reference guard is extended by all-unit-property and process-environment scans; process cmdline/fd/maps/cwd/root/exe and mount namespaces remain covered. Any native qualification/apply attempt has a fixed exclusive intent; failed or uncertain attempts cannot be replayed. Each unlink waits for a controller journal fsync acknowledgement. Full58 is repeated after deletion.

Outputs remain exclusively in H/containerd-release-duplicate-cleanup under the established F-backed root. Peak allowance128MiB; only small ownership/intents/profiles/events/results are retained. File-only measured candidates: master127,991,808B, worker2127,979,520B, plus only proven-empty directory allocation. Final receipts report actual Linux allocations, never Windows recovery. Remaining guards may refuse all deletion; preparation is not acceptance.
