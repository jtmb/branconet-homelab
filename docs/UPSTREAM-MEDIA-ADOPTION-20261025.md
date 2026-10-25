# Same-version media vendor adoption

This continues the upstream-only ownership correction. It replaces the reviewed
local derivatives with official vendor rebuilds of the same installed app
versions. It does not build or publish a new image, change application versions,
alter storage identities or declare vendor dependencies free of vulnerabilities.

| App | Version | Reviewed vendor index digest |
| --- | --- | --- |
| Radarr | 6.4.4.10685 | `084b3b2ab1d0ef930660727259546a241f2bdf67c9ed085d54bf1486a6887c9b` |
| Sonarr | 4.0.20.3014 | `48e36b608b461273b9dae857725cd0561a127f2c694b687318f6d0c5ce63e5c9` |
| Bazarr | 1.6.2 | `32204ef90d4dcb54ad5fb019810f4ef805ced9c54853ae552cf09a41c056b14b` |

Registry configuration binds these to vendor app versions and source revisions
in [the candidate inventory](../evidence/media-upstream-candidates-20261025.json).
Radarr/Bazarr were rebuilt October25; Sonarr was rebuilt October24. The cold
backup profile `upstream-media-20261025` pins the existing three local-image
sources and every original Deployment/release/config-PVC UID. It retains the
4096-entry/4 GiB/8 MiB metadata limits, full archive authentication, zero-writer
fences, read-only claim access and UID-guarded reader cleanup. It never scales
the writer or walks NAS media. The Ansible role exposes this exact opt-in scope.

The existing API observers now accept `--security-patch --upstream-adoption`.
The first flag selects the existing modern, same-app preservation rules; the
second selects the finite local-to-vendor image pair. It is not a security-fix
claim. Receipt scopes cannot be mixed with earlier overlay runs. Original
library/configuration, credential HMACs, Service and claim identities must match.
Bazarr permits no legacy normalization exception for this same-app transition.
Radarr/Sonarr also require every SQLite Users column, ID and credential value
to match the fresh authenticated cold snapshot after adoption and restart.

The upstream SQL path creates no plaintext database files or alternate temporary
filesystem. It streams the bounded authenticated database/WAL into process RAM,
validates WAL magic/version/page size/salts and all chained checksums, requires a
committed final frame, and applies those pages only to the RAM query view. It
then uses the same SQLite integrity and Users-HMAC code as the live read-only
snapshot. Unrecognized, incomplete or corrupt WAL data is refused. Only the RAM
view's journal-mode header bytes change for SQLite deserialization; archive and
source files remain immutable. The original tmpfs/default profile is unchanged.
The format follows [SQLite's WAL documentation](https://www.sqlite.org/fileformat2.html#walformat).

Before execution, this RAM path matched the independently accepted native
SQLite results from the two real earlier encrypted cold archives: one Users row
and six columns per app. Sonarr's 35 committed WAL frames matched the prior
observation exactly; a corrupted-WAL check was rejected. The bounded control
receipt is retained under the existing F: root at
`operator-control/media-memory-sql-controls.json`, source SHA256
`53590df58f98871962b2aaa99bd7c075649a4c0f7c9e86031ff6a604a54d4920`.
The frozen eight-file source manifest is
`598c681db939119eae8743aaebe02c3338befc0e1b0a59a51b1493b5dc870a09`.
Ansible syntax validation passed. No new compiler, dependency copy or build ran.

Fresh API baselines passed for 180 Radarr movies; 155 Sonarr series, 14,730
episodes and 5,319 episode files; and Bazarr's 155 shows, 237 movies and settings.
Flux pause commit `e5f339caec523cb6f47f8bf908d1bc40b20557f3` quiesced all three
writers. Their complete fresh encrypted archives and NAS read-back passed:

| App | Files | File bytes | Encrypted archive bytes |
| --- | ---: | ---: | ---: |
| Radarr | 1197 | 518108661 | 519612468 |
| Sonarr | 1648 | 469455484 | 471401028 |
| Bazarr | 110 | 65337821 | 65480500 |

All temporary backup readers were deleted. Full source originals remain in
`FBASE/upstream-media-20261025/<app>/cold`; NAS copies are in the existing
verified recovery folder. The copy verified every encrypted byte's source and
destination SHA256 plus complete age authentication. Windows rejected direct
unsigned UNC-script invocation; the same reviewed routine was run inline in the
existing PowerShell session without changing execution policy. Its exact source
hash and copy receipts remain in `operator-control/media-smb-execution.json` and
`operator-control/smb-media-upstream-copy-status.json`.

## Completed backend checks, October25 23:28 UTC

Private adoption commit `ea28be56fb91b4f9693318f8ec55c4a3cfbbdc52` resumed the
writers with the exact vendor images. Controlled restart commit
`c195c3b67d4fa5886947ca90f36c1c46090c7229` reconciled successfully through local
validation, validated and Flux. Every API/config/library comparison passed after
adoption and on a different Pod after restart. Counts remained 180 Radarr movies;
155 Sonarr series, 14,730 episodes and 5,319 episode files; Bazarr 155 shows and 237
movies. Radarr/Sonarr each preserved the one original Users row and all six
columns/credential fields, with SQLite integrity and no additional columns.
All four SQL readers were UID-deleted. Media-root accessibility checks passed.

Across all three nodes, Radarr/Sonarr returned their expected application login
redirects and Bazarr returned its page. These pre-authentication HTTP checks are
separate from final IAB acceptance. Sonarr health checks are clear. Radarr's
current warning source is IndexerLongTermStatusCheck; its baseline also recorded
one warning category. The provider issue remains visible for follow-up rather
than being disabled or described as fixed.

The three complete archives and a 119,478,964-byte encrypted recovery-metadata
archive passed full NAS read-back checksums and age authentication. The metadata
includes only this batch's distinct sources, baselines/observations and required
verification keys, encrypted together; it does not sweep prior ancestor records.
Metadata archive SHA256 is
`a3ed5ae39a57dce83e79acf73875d1906971c627f781f41e1db977661005e4fb`.
Originals, rollback images, recipes and failures remain preserved.

All raw execution receipts stay under the existing F: root. The concise current
receipt is `operator-control/media-upstream-adoption.json`; per-app API and SQL
receipts are in `upstream-media-20261025/<app>`. It binds every archive and
observation hash and both Pod identities. Native account/config values are not
written into repository evidence. Final IAB and current vendor CVE review remain
open; this is not a zero-CVE or whole-goal-completion claim.
