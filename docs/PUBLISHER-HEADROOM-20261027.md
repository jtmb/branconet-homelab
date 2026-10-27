# Publisher reserve recovery, October 27

Completed at 15:48 UTC. Removed only twelve inactive, reproducible ELF tool
exports and their four empty `.tools` directories from four successful local
chart-publication runs. Recovered **599,113,728 allocated Linux bytes** on the
existing F-backed migration filesystem. Its measured available bytes increased
from **16,370,782,208** to **16,969,895,936**; the unchanged publisher floor is
**16,374,562,816**, leaving **595,333,120 bytes** of headroom at that observation.
These measurements do not claim Windows physical disk recovery or node space.

The [exact reconciliation](../evidence/publisher-headroom-reconciliation-20261027.json)
records every removed path and allocated byte count. Source manifests matched
reachable primary Git commits and every exported source blob. All three tools
matched their retained original binaries. Existing stage locks, complete Linux
unit/process/FD/map/mount exclusions, native Windows exclusive read handles and
final inode/hash checks passed before individual removal. Original source
exports, every validation/publication receipt and primary binaries were hashed
and verified unchanged afterward. The complete failed attempt
`f2085e8a5d0f4098896b6be87e5e3797` remains intact. No publisher retry or deployment
was performed. Ingenium's approximately 1.21 GB image is a separate node-space
requirement; no image, application data, volume or model was deleted here.

Retain the ownership, frozen operators, qualification plan, native handle proof
and reconciliation under the existing `operator-control` root as unique review
evidence. No payload archive, dependency tree or build cache was created. Tool
exports can be regenerated from the retained publisher originals after matching
their pinned hashes in a future exclusive stage; never replay publication just
to recreate disposable tools.
