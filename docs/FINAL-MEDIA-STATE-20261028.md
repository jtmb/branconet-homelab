# Final media state observation — 2026-10-28

This is an actual read-only observation after the original media pods restarted
onto Longhorn 1.13. It is not final browser acceptance or a security scan result.

## YTPTube

The unchanged stored-state qualifier passes against the original baseline:
one account, nine presets, all original history rows, every stable database table,
all three original claim identities and the existing native Secret identity.
Ephemeral session records retain the qualifier's existing exclusion.

The previously downloaded Blender sample remains exactly 105,333 bytes with the
same SHA-256 and 5.066667-second audio/video duration. No new download was started.

`verify-final-ytptube-legacy.py` authenticates and streams the original encrypted
cold archive without extracting plaintext files, verifies its original embedded
manifest, then hashes only its seven exact original paths in the existing pod.
It fences deployment, image, pod and claim/mount identities before and after.
The actual source-bound result in `ytptube-seven-original-files.json` passes:
all seven files match their original sizes and SHA-256, totaling 618,241,982 bytes,
on pod UID `f9f434b3-f00d-4921-92d5-d73ab3457b6a`.

## Seerr

The original archive SHA-256 is
`b70eb9a319fda964a445fb4e8d11a9b38abacf7fd8e46a0ca28f95310e19cdce`.
The old HMAC key was unavailable. A fresh temporary comparison key was held only
in RAM and used with the authenticated same original archive and current data.
No authentication credentials were replaced, and no prior receipt was rewritten.

Confirmed preservation:

- All six users, including passwords, permissions, Plex tokens and identity
  fields, match the original HMAC projections.
- Original counts and ordered IDs match: 654 requests, 1,099 media, 1,405 seasons,
  634 season requests, three issues, four comments and three user settings.
- Every column matches in season requests, issues, comments, user settings and
  push subscriptions. In the three changed tables, every column outside the
  explicitly enumerated fields matches its original HMAC.
- Of 199 original setting leaves, 197 match literally. The only differences are
  the two previously reviewed Plex library `lastScan` clocks. Original array
  lengths, required absences and migration markers match.
- SQLite integrity/foreign keys, startup API, Plex and configured Radarr/Sonarr
  health checks pass.

**The exact full-history/settings comparison remains false.** The failed receipt
`seerr-current.json` remains intact. Detailed current deltas are in
`seerr-history-deltas-corrected.json`:

| Table | Rows with actual differences | Changed fields |
| --- | ---: | --- |
| media_request | 1 | status, updatedAt |
| media | 102 | status, updatedAt, lastSeasonChange, mediaAddedAt, ratingKey |
| season | 75 | status, updatedAt |

One request (1041) changed from approved to completed, linked to media 1151
changing from processing to available. An authenticated read of current Plex
confirms the identical rating key and added timestamp, `2026-10-27T00:27:17Z`.
The request transition occurred at `2026-10-27 00:30:00`.

Five other media changed from partially available to available around
`2026-10-28 05:00`; 25 seasons changed from deleted to available and one from
deleted to partially available around `2026-10-26 03:00`. Remaining differences
are the enumerated update/season-change timestamps. Exact pinned upstream scanner
and entity source supports these kinds of native lifecycle updates. A subsequent
bounded read established current availability coherence: all five other changed
media exist in Plex under their original stored rating keys, all five have their
recorded non-special seasons available, and all 26 changed seasons exist in Plex
with episode files. Twelve seasons' Plex episode counts exactly match Sonarr's
reference total episode counts.

Two series (media 65 and 604) have no original Sonarr linkage. Two preserved
links (media 257 and 1082) return HTTP 404 for the exact linked Sonarr series.
These link fields match the original archive; this observation does not establish
when the linked Sonarr items disappeared. All four series and their affected
seasons are present in Plex, but independent total-episode denominators were not
established for their 14 changed seasons, including the partially available one.
No missing Plex media or season was found. These are current-state observations,
not a claim that every historical scanner event was observed. Ordinary update
clocks are not treated as frozen records. The original literal comparison stays
false; account/record preservation and current availability evidence are recorded
separately, without a blanket mutable-column exclusion.

## Evidence and storage

Sanitized receipt references and hashes are indexed in
`evidence/final-media-state-20261028.json`. Private minimal receipts remain at
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/platform-upstream-review-20261027/final-media-state-20261028`
on F-backed ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`.

The first maintained cold-reader invocation transiently used a context-managed
`/dev/shm/seerr-compare-*` directory, contrary to the single-root storage rule.
Its context removed it; no matching directories remained. Its exact suffix and
removed byte count were not captured. This incident is not presented as compliant.
Subsequent archive/database inspection used only streaming memory or a validated
SQLite WAL committed-page overlay in RAM, with no plaintext filesystem output.

The obsolete delta receipt containing empty records was losslessly regenerated
and verified before deleting exactly 253,437 bytes. Its corrected observation,
original failed acceptance receipt and minimal provenance remain. No Windows
space recovery is claimed from this Linux deletion. See `final-inventory.json`
and the subsequent follow-up inventory for exact retained paths.
