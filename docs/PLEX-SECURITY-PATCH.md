# Plex security patch acceptance

Plex keeps the exact claimed production beta 1.43.5.11079-b3b13e506, with signed
Ubuntu 24.04 package updates. It is baked into the image and VERSION=docker
prevents startup from downloading a mutable server release. The original launch
Secret reference, resources, four PVCs and NAS mount paths remain.

Candidate image:
`docker.io/library/plex-security-20261023@sha256:1b3470b85eb38360c5b242f7cfbc7d45accc429704f725a8610137861db00397`.
Its exact fresh scan reports zero Critical/High, 37 Medium and seven Low rows,
with no available fix at any severity. Results SHA256:
`c977ebd36b98ce8880817617189c2f5f5dc8c50e8e1ffee3761f3139fdfef00c`.
The artifact is verified in all three node caches. No older public server version
was substituted for this production beta.

Flux stopped the original writer before the complete config backup. All 38,905
cold files (6,455,480,574 plaintext bytes) are in the authenticated encrypted
archive; no NAS media was walked or copied. The archive is 6,596,764,276 bytes,
SHA256 `7f818f137d97d3e9aa6981734cab8f63348cf110091b0777af9e8170b8f2457a`.
Receipt SHA256: `81f22d8e3a683f1ec43eb8360d92d805ea3ad19473c5ea1fac265108625c397b`.
The temporary read-only backup Pod was deleted by UID. Complete archive
authentication was performed; a full restore drill was not performed.

The Plex-specific Ansible backup profile supports 131,072 entries, 16 GiB of
data and 64 MiB of metadata, writing directly to native F storage. Other profiles
retain their bounds. The real observation compares 21 complete account/library/
watch-state tables, server and account identity, native Secret/PVC bindings,
authenticated library API and a 64 KiB existing NAS-media prefix read as UID1000.
No credentials are returned in reports.

The same-beta Flux cutover is Ready. All 20 other core account/media/watch-state
tables match the original live baseline. The first live-baseline section-table
mismatch is retained: the complete authenticated cold archive proves every one
of its 23 columns and all three rows equals the new live table exactly. No field
is excluded. The native library API, claimed server/account identity, original
Secret/PVC bindings and actual NAS prefix read passed. Functional receipt SHA256:
`8af69f6a59417c812021b2cc41c363e1c6b0d1ab0359c3d075f6940ee8129aa5`.
Cold-section proof: `1068c787acb6b6966a0fe2bee903e3ed5b79bdc8719b66501fcfdf3b169fe400`.
Routes are being restored through Flux. Final external routes and browser
acceptance still need recording.
