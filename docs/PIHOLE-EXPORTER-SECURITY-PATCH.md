# Pi-hole exporter security patch

The existing exporter now uses its exact original source commit
`99911965575f4624e265bde0d5c8db5d31d17b41`, rebuilt with Go1.26.10 and patched
modules. It retains the Pi-hole6 API, embedded UI-free exporter behavior, scratch
runtime, `/root` working directory and original command.

The deployed image is
`b5f1f7deeafa7a2649f983ac6a719eceaf07508fef0adf1bd3c06573a0d78431`. Build source is`0e73c200`; exact public artifact/source receipts remain
outside Git. The fresh exact scan has **zero findings**, with Results checksum
`d4e785b1d0a2771717188c9893331bb3c7bb43cb153b7ad9f63b505db32b6a06`
and scan receipt`3a359f2501f63690d441bddaf44ae9d90ee1216eb7af29a1dc52295f75a432a4`.

All three node caches imported the reviewed digest through Ansible before the
private validated/Flux cutover. Three real Pi-hole scrapes, readiness and liveness
passed. Original Pi-hole metric names, positive gravity count and enabled status
are present. Original deployment/Service settings and native credential Secret
identity/version remain unchanged. Query labels, credentials and metric values
are not included in public evidence.

The successful after receipt is
`962556d9a03cf428309915fa904cb7e046b6d149e97c52765f8e17699f073a1a`.
The repeatable read-only helper is`scripts/migration/qualify-pihole-exporter.py`.
Final inventory/cluster/browser acceptance remains separate.
