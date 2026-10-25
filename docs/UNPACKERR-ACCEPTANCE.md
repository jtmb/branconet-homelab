# Unpackerr security patch acceptance

The same Flux-owned service now runs0.16.1 with Go1.27.3 and signed Alpine3.24
updates, image `docker.io/library/unpackerr-security-20261023@sha256:6342be9c7797b126633a56948b4dab131fde45fde3b8b173a3c84a8f4efc6213`.
Its unsuppressed scan has no Critical/High/Medium/Low findings; unfixed Unknown
GO-2026-5932 remains. Results SHA256:
`96c33c827f91a10909791b31eb5229b9cfe2929ccd6018c9cefc3c081548f757`.

The complete original17148-byte config was cold-archived and authenticated before
adoption. Original native Secret, config bytes, both Longhorn/SMB claim identities
and resource requests match. Radarr/Sonarr log mentions and no observed auth/fatal
errors passed on the new Ready Pod. Cold receipt SHA256:
`d09e1317d89564d1a1df7a9a83f5ba557137cf70dc2d5d40077fa38758c7e353`.
Functional receipt: `2fb5d104202e0841adafd3d8a552dd1893c00c2c8bd85f55dfe6fa7e48980a29`.
The UID0 capability-free reader could not traverse the UID1000 directory; that
failure was retained and its exact owned Pod retired. The successful UID1000
reader used the same read-only/no-capability controls and was deleted after
verification. No NAS corpus was archived or changed by the backup.

A real isolated application fixture extracted a stored ZIP, matched all content,
0644 permissions and mapped ownership, simulated Radarr import by removing its
mock queue item, then verified cleanup retained original/archive/preexisting and
mock-library files. It used fresh user/network namespaces with loopback only,
512MiB hard cgroup memory/no swap, one CPU,64 tasks and180-second outer deadline.
Go's memory target was256MiB. No production config or credentials were loaded.
The first fixture inherited0077umask and failed its0644 assertion; matching the
measured production0022umask passed without changing production permissions.
Evidence: native F `unpackerr-fixture-z6loq8s8/result.json`; script SHA256
`e37aa881ea956513bae0fcbad64a723ade83a92b4fb449c8d9dce314d7f75aae`.
This is ZIP/mock-import acceptance, not a real Radarr import or NAS ACL test.

Upstream0.16 security extraction/retry/remnant limits remain enabled. Same config
keys do not imply identical operational limits to0.15.2; the private recipe
README records these changes. No SQLite migration or real download/deletion test
was introduced. Complete rollback data and previous images remain retained.
