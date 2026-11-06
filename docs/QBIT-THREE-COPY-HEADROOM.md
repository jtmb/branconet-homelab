# Finite native qBittorrent replica relocation

This source is prepared, not executed. It uses supported Longhorn surplus-copy
cleanup after creating a third healthy copy. It never issues replica deletion,
file deletion, node eviction, scheduling changes or forced placement. Current
estimates mean qBittorrent alone may unlock the native upgrade's peak budget;
it does not necessarily close the final 2 GiB headroom acceptance target.

Use `scripts/migration/qbit-three-copy-headroom.py PHASE --authority PATH
--authority-sha256 SHA256`, or the optional
`k8s-rewrite/ansible-playbook/playbooks/qbit-three-copy-headroom.yml` with
`qbit_headroom_phase`, `qbit_headroom_authority` and
`qbit_headroom_authority_sha256`. The playbook defaults to qualification and does
not execute in Ansible check mode. Source parsing is the only local validation
performed for this implementation.

Phases run separately, never as an automatic mutation loop:

1. `qualify` requires the exact original qBittorrent volume and both original
   running/RW replicas, current58 backups and identities, healthy original
   volumes, unchanged global settings, all nodes uncordoned/Ready and running
   instance managers. It measures source-directory allocated blocks through
   metadata-only SSH and freezes its inode/device. It writes ownership and
   qualification only; no mutation intent.
2. `add-third` repeats qualification and capacity/cleanup-precedence guards,
   then changes only `numberOfReplicas: 2→3` and
   `replicaAutoBalance: ignored→best-effort` using UID/resourceVersion/full-spec
   JSON-patch tests. Hard node anti-affinity leaves worker1 as the only unused
   node. No placement selector is written.
3. `observe-third` takes one read-only snapshot. Completion requires three
   running engine-RW replicas, original master/worker2 UIDs, the new worker1
   replica, healthy volume and no rebuild status. During the rebuild, only this
   volume may be transiently degraded while at least two copies including the
   original master remain running/RW. That observation-only normalization never
   authorizes reduction. All other 43 volumes remain exact.
4. `reduce` requires completed third-copy proof and a fresh three-RW check,
   repeats cleanup precedence and strict ordering, then changes desired count
   from three to two. It leaves best-effort enabled for Longhorn to select and
   retire the surplus copy.
5. `observe-two` completes only with exactly the original master plus the
   recorded new worker1 copy running/RW, worker2's old CR gone, and its exact
   original directory absent after native cleanup. It also supports observing
   successful restoration after a lost reply without resubmitting a patch.
6. `restore` restores `replicaAutoBalance: ignored` and verifies the **complete
   original volume spec**, two healthy copies and all unchanged checkpoint/data
   gates. It records the pre-operation allocated bytes of the now-absent
   directory and actual node filesystem values without claiming Windows recovery.

Before each mutation, destination budgeting reserves at least 2 GiB copy space
and retains 15 GiB usable plus the original 25% capacity + 512 MiB + 2 GiB margin.
Every node must retain its original 15 GiB usable/25% + 512 MiB floor. Native
Longhorn scheduled-space and 25% availability rules also apply. No global setting
or reserve is lowered. Raw free-byte ordering must remain worker2 < master <
worker1, with all values eleven digits, matching Longhorn's decimal-string sort.

Selection is conditional on controller state, not UID-pinned by an API option.
The helper checks eviction/linked-clone exclusions, disabled data locality,
same-zone candidates, node/instance-manager health, and Longhorn's unstable-node
heuristic before reduction. The heuristic compares the newest two node Ready
transition timestamps; when their separation exceeds thirty minutes, any copy
on the newest node must have become healthy after that readiness transition.
It does not assume waiting thirty minutes clears that condition. Unknown health,
ordering or precedence refuses mutation and preserves three copies.

Original 219 projected identities and the current58 backup/NAS checks are reused.
Only the approved proxy old/new image and this volume's two temporary spec fields
are normalized. All other specs, original UID sets, ephemeral regeneration
sources, settings and Longhorn node specs stay exact. Root filesystem UUIDs and
the original engine UID/image are pinned. A local native-upgrade process blocks
the operation, which must run between closed upgrade attempts.

All outputs use the single existing-F leaf `H/qbit-three-copy-headroom`. Each
mutation freezes before/intent/after immediately before its sole patch; earlier
read-only refusals create no mutation intent. Existing intents cannot be replayed.
Lost replies are handled only by observation, never deletion or another patch.
Unknown or partial outcomes retain all data and evidence. Old failed witnesses
are excluded. Any later fixed xteve profile must use target-prefixed records in
this same leaf; this version deliberately does not authorize or implement it.
