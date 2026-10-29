# Optional Kubernetes 1.37.1 filesystem-cache scope

The default 41-root node-headroom profile is unchanged. Opt in with
`--superseded-kubernetes1371 --kubernetes-success ABSOLUTE_RESULT_PATH --kubernetes-success-sha256 SHA256`.
The playbook uses `node_headroom_cache_superseded_kubernetes1371: true` plus
`node_headroom_cache_kubernetes_success` and `node_headroom_cache_kubernetes_success_sha256`.

Each inventory, qualification and retirement requires the hash-bound terminal successful native upgrade result, all three completed host receipts, matching native authority/node UIDs, current API and all three kubelets v1.37.2, containerd2.4.2, Ready uncordoned nodes and the existing28 healthy/16 offline Longhorn checks. Qualification receipts bind this explicit profile and authority; old qualifications cannot be reused.

Only the four official1.37.1 index roots and their four amd64 manifests are added. Public registry metadata authority is retained under the existing H root in `kubernetes1371-superseded-cache-root-authority.json`. Its SHA256 is 7b7b4b897aed967857b60b551f0983d0c6c6b2311fb8f13c8d39650b6596e565. No layers or image archives were downloaded.

The immutable native inventory/physical/retirement implementations and all historical attempted-key exclusions remain unchanged. Non-target image ancestry, live/desired roots, every container including stopped containers, leases, foreign namespaces and shared descendants remain protected. Stable bbolt physical mapping, original compressed blob and uncompressed diffID verification, process/mount checks, durable intents and no uncertain replay remain required. This retires only qualified reproducible filesystem caches; never images, content, labels, containers, leases, volumes or raw directories. Zero eligible bytes is a valid result. No operation was executed while preparing this profile.
