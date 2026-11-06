# Single qBittorrent replica eviction review

The proposed one-shot mutation of `Replica.spec.evictionRequested` is not a
stable single-replica control in the installed Longhorn 1.13.0 controller model.
Do not apply a race-dependent request or repeatedly assert that field.

The upstream [Replica validator](https://github.com/longhorn/longhorn-manager/blob/v1.13.0/webhook/resources/replica/validator.go#L55-L84)
does not reject this field change. However, the
[node controller](https://github.com/longhorn/longhorn-manager/blob/v1.13.0/controller/node_controller.go#L1909-L1964)
reconciles each scheduled replica's eviction flag to `shouldEvictReplica`.
That [decision](https://github.com/longhorn/longhorn-manager/blob/v1.13.0/controller/node_controller.go#L2041-L2081)
returns false when the node/disk eviction flags are false and the Kubernetes
node is schedulable. It then cancels a directly patched replica flag.

The volume controller's create-before-retire behavior therefore does not prove
that an independently patched per-replica request will persist long enough to
complete. No helper or playbook which claims reliable finite execution was
introduced. Changing node/disk eviction, scheduling, replica count, placement,
or deleting a replica would exceed the specified sole-mutation boundary.

Read-only observation on 2026-10-29 confirmed:

- Volume `pvc-999128b4-0ae2-4396-a8e4-eebace5d26f0` has UID
  `6f21d4fc-3a0a-4e82-a468-98792639f2ed`, is attached/healthy, encrypted, and
  specifies two replicas.
- Worker2 replica suffix `r-e1f9805b`, UID
  `a7a8c98f-a469-4628-b307-e333028d957a`, is running and engine-RW.
- Master counterpart suffix `r-4d021a64`, UID
  `6cf45d01-9d4b-4ca0-ae5d-48431460904f`, is running and engine-RW.
- Worker2 is schedulable; both its Longhorn node and source disk have
  `evictionRequested: false`. These are the cancellation conditions above.
- Worker1's Longhorn destination disk is Ready and Schedulable.
- The supplied checkpoint SHA256
  `7de0db518a9d913ff4efd9b4fc36bc9667956daaeba7f07417e21ea870a99902`
  identifies `H/kubernetes1372-current58-manifest.json`.

This is a control-semantics finding, not full migration qualification. No patch,
intent, allocation measurement, native directory removal, workload restart or
cluster change was performed. No data-recovery or freed-space claim is made.
All current replicas and older failure witnesses remain protected.
