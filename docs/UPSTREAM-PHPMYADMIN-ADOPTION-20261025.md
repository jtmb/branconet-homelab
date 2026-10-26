# phpMyAdmin official image acceptance — October 26, 00:20 UTC

The original frontend runs official **5.2.3-apache**, PHP **8.3.36**, image
`docker.io/library/phpmyadmin:5.2.3-apache@sha256:62a50b1419fe55b9b4c3cd6f5aed03a18f8f5b4a236f24735d76400bea75a5ff`.
The current official release/latest tags select this same immutable payload.
[Vendor source](https://github.com/phpmyadmin/docker) and
[release/downloads](https://www.phpmyadmin.net/downloads/).
Only the image changed in adoption `e305ca962176de588aa3951476332431df108112`.
Controlled restart `4e792ea690e2cbda21168510051345f865c47421` reached private
main, validated and Flux through the existing local publisher. Actions stayed off.

Before, after and different-Pod restart observations passed:

- Native phpMyAdmin login with the existing SQL application account, followed
  by POST/CSRF logout and proof that the protected database page requires login.
  Only the observer's own transient session was used; credentials, cookies and
  response bodies stayed in memory. All three published port 8086 routes return
  the native login form. Final IAB remains separate and pending.
- Exact frontend Deployment/HelmRelease, both Services, native Secret identities,
  versions/content HMACs and deployment settings matched, apart from reviewed
  image/restart annotation. This frontend has no PVC or data mount.
- All 12 WordPress table schemas and stable rows matched through the read-only
  SQL connection from the new frontend, including application users and roles.
  The configured SQL account/grants matched. MySQL Deployment specification,
  Pod identity, native credentials and original bound data claim stayed exact.
  Neither WordPress nor MySQL was stopped, rolled out or modified.

There are 514 compared nonvolatile WordPress rows. Account table row counts:
`{"wp_usermeta": 21, "wp_users": 1}`. The already-established volatile WordPress
option exclusions remain explicit in the source; their counts are informational.
Administrative mysql.* privilege tables were not queried, and no all-root-account
or fresh database-backup claim is made. Earlier complete database backups and
rollback images remain retained. No application bootstrap or SQL write ran.

## Unresolved vendor security findings

Backend acceptance does **not** establish security acceptance. The exact vendor
digest's prior unsuppressed scan ended `2026-10-25T00:54:41.798104+00:00`, with vulnerability
database updated `2026-10-24T19:09:13.779511838Z`. It reported 8 Critical,
131 High, 725 Medium, 983 Low and 55 Unknown finding rows; these are historical counts,
not a fresh scan or unique-CVE count. Results SHA256:
`e9d032db6e187653466d230e4c32561fef6e132d995cb15cc8b328ba0e0b8df9`.

Eleven Critical/High rows name package fixes: libbrotli1 for CVE-2026-111497,
symfony/cache for CVE-2026-45073, and twig/twig for CVE-2026-24425,
CVE-2026-46633/46634/46638, CVE-2026-48805/48806/48807/48808 and CVE-2026-49981.
The current vendor digest still carries those versions. The prior custom image
had local dependency/OS patches; this official-image transition does not retain
those bespoke patches. Maintaining a third-party fork or installing patches into
the running image would contradict the current scope. Fresh whole-inventory
advisory review and compatible maintained vendor alternatives remain open;
these findings are visible exceptions, not fixed or waived requirements.
Full package/version/advisory rows and original scan bindings remain in the
private F: receipt `operator-control/phpmyadmin-existing-vendor-findings.json`.

## Recovery, health and cleanup

Before-change recovery metadata is 92,388 encrypted bytes,
SHA256 `9397e70dc79179cc978e4f9b10d6000518cbc4f6f35f723f4d01857b26bbbedd`. Final distinct observations/security
metadata are 604,516 encrypted bytes,
SHA256 `429760a6022ad270a9f13cb0572f324e05347ef7c28cf397c594b9aa01c5cebd`. Both archives passed full member/authentication
checks and NAS SHA256/read-back/decryption checks. The native HMAC key appears
only in the encrypted before archive; final metadata does not duplicate the
baseline, key or frozen sources. Original files and recovery-key safeguards remain.

The 00:17 health check found all 3 nodes Ready, 55 PVCs Bound, 34 HelmReleases and all
desired workloads available; 41 Longhorn volumes had no unhealthy attached volume.
Only the two intentionally retained Seerr diagnostic failures remain.

All generated work uses the existing F:-backed ext4 task root documented in
[the output inventory](TASK-OUTPUT-INVENTORY.md). Exact private summary:
`operator-control/phpmyadmin-upstream-adoption.json`; observations:
`upstream-phpmyadmin-20261025`. Frozen source SHA256:
`3425a25973aafbc893a36a9035e391bef94c73af77ce4388ab308d7d051748e4`.
The first version-reader and GET-logout verification failures remain retained
with their frozen sources. Corrected checks use public version-source parsing
and the actual POST logout contract; application behavior was not changed.

No build, dependency install, data deletion or image publication ran.
Verified cleanup removed the empty `operator-control/tmp` directory, 4096 allocated
Linux bytes. All sources, observations, native verification key, encrypted
recovery metadata, scan evidence and rollback archives remain required evidence.
No Windows recovery is claimed. The full goal stays active with 15 third-party
transitions, current vulnerability review and final IAB still open.
