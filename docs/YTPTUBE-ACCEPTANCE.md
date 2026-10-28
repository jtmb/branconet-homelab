# YTPTube operator acceptance preparation

## October25 22:00 UTC execution — backend accepted

Official v2.7.5 is live through Flux revision
`4db7673bcc1a8989a674c4f1dc26926420165b92`. Native login, the original account,
nine presets, original history and all seven legacy files passed preservation.
A distinct Blender video produced a 105,333-byte, 5.067-second H.264/AAC sample;
the media, history, active runtime and original data passed on a new Pod. Two
history rows remain. Original claims, Deployment and native Secret identities
are preserved. Normal LAN page/API access with native authentication passed.
Both full snapshots and companion metadata passed complete authenticated NAS
read-back, with source originals retained. All temporary backup, legacy and
repair Pods were UID-deleted. The failed first repeated-video check and its
restoration are documented below rather than discarded.

[Exact sanitized receipt, archive hashes, runtime and live identities](../evidence/ytptube-upstream-adoption-20261025.json).
Final IAB acceptance remains pending until implementation is finished. No fresh
zero-CVE claim or full-goal-completion claim is made.

## Official upstream transition profile — October25

The user superseded bespoke third-party derivative maintenance. The explicit
`--runtime-profile official-pinned-updater` accepts only official upstream
v2.7.5 index `3ba09ac58f0b541aa7182feb9198b44d3c62158a7749ec00d26de1abad7ca8d7`.
An isolated read-only inspection of this exact image found yt-dlp2026.8.19,
EJS0.8.0, Deno2.9.5 and bundled provider2.0.2; the inspection Pod had no claims,
Secrets or token and was UID-deleted. Registry `latest` resolves to the same
v2.7.5 image, not a newer rebuild. No custom image is built or published.

Use upstream's existing `YTP_YTDLP_AUTO_UPDATE=true` startup feature with
`YTP_YTDLP_VERSION=2026.10.21` managed in chart values. That exact stable yt-dlp
release was verified against its upstream release API. The pinned
[upgrader](https://github.com/arabcoders/ytptube/blob/c8a42e08ded27280573d7ebe6312dd109b2bb161/app/upgrader.py)
and [installer](https://github.com/arabcoders/ytptube/blob/c8a42e08ded27280573d7ebe6312dd109b2bb161/app/library/PackageInstaller.py)
install upstream yt-dlp/default dependencies into the app-owned package directory
under `/config`; they are not local image patches. Preserve that directory on
the original config claim, record active runtime versions and require the same
versions after restart. The vendor installer resolves transitive dependencies;
this is not represented as a fully hash-locked package environment.
`YTP_PIP_PACKAGES` stays empty, ignore-custom-update stays enabled, and active
pip.txt requests still refuse qualification. The earlier install-only-module
absence requirement applies to the historical derivative profile; the official
vendor profile truthfully records its supported installer instead of claiming
that the vendor image has been stripped. Existing legacy profile checks remain.

`check-adoption` may compare the accepted derivative's original sample to the
exact official-image profile, preserving its media/history bytes while recording
the explicit runtime change. A new real five-second sample and its new-Pod
restart check remain required. No automatic replay follows a download failure.

`qualify-ytptube-state.py` independently reads SQLite in query-only/readonly
mode. It compares complete users, password hashes, API keys, configuration and
task rows, and every prior history row, allowing additional history records.
Ephemeral login/logout sessions are explicitly excluded. Fingerprints use a
domain-separated HMAC derived in RAM from the existing native auth credential;
no key or raw account/config value is written or emitted. It pins the original
Deployment and all three claim UIDs, and preserves the native Secret UID.
A full fresh encrypted cold archive and a separate seven-file legacy check
still protect data beyond this SQL projection. This section records prepared
scope; adoption is not claimed until dated execution evidence is added.

The backup role now has an explicit `metube_state_snapshot_profile:
current-ytptube` option for a quiescent, already-migrated writer. It includes the
new configuration and package-cache directories, with no exclusions, while
preserving the original 4 GiB/4096-entry bounds and exact image/claim identities.
The default `original-metube` profile and original seven-file comparison remain
unchanged. The current-state profile cannot be used as a replacement legacy
baseline. Ansible syntax validation passed for the updated role and launcher.

The October25 first upstream sample reused the original video's URL. YTPTube's
unique `history_url` index replaced the earlier row; the full SQL comparison
correctly refused restart acceptance. Both media files remained. After a fresh
full encrypted snapshot of that state, a quiescent transaction restored the
original row exactly from the authenticated pre-transition archive, replacing
only the owned verification row and proving every other table unchanged.
The repair Pod was UID-deleted. Both complete snapshots passed NAS read-back
checksums and full age authentication; originals remain. The original failed
check and recovery evidence are retained. Downloader qualification now refuses
an existing video's history before queuing a sample, and supports a second,
explicitly selected public Blender sample rather than overwriting prior history.

Current checkpoints and unresolved gates are summarized in [MIGRATION_STATUS.md](../MIGRATION_STATUS.md). This document retains operational contracts and dated attempt history.

`scripts/migration/qualify-ytptube.py` created the absent native authentication
Secret through its separately verified bootstrap on October23. Application
login, provider and real download checks passed on October24, followed by
restart persistence on a new Pod. The sample is five seconds of H.264/AAC,
110,645 bytes, with identical file/history after restart. A separate full legacy
reobservation passed for all seven original files; browser validation remains
pending after implementation.
Run it explicitly on an operator host that can reach the existing ytdl ClusterIP
and already has the approved kubeconfig and `kubectl`. It neither provisions
credentials nor disables Kubernetes TLS verification. Its stdout and receipts
contain metadata and fixed error categories only. No username/password, cookie,
user-provided URL, raw API response or application log is printed or saved.

The helper uses YTPTube v2.7.5 source commit
`c8a42e08ded27280573d7ebe6312dd109b2bb161`, inspected before implementation.
The [login schema](https://github.com/arabcoders/ytptube/blob/c8a42e08ded27280573d7ebe6312dd109b2bb161/app/features/auth/router.py)
accepts JSON credentials and sets an HttpOnly session cookie. The
[history routes](https://github.com/arabcoders/ytptube/blob/c8a42e08ded27280573d7ebe6312dd109b2bb161/app/routes/api/history.py)
support synchronous metadata extraction with `auto_start:false`, followed by
starting an exact item ID. This avoids starting an unidentified background item
when metadata extraction times out. The documented CLI fields pass through the
[reviewed item schema](https://github.com/arabcoders/ytptube/blob/c8a42e08ded27280573d7ebe6312dd109b2bb161/app/features/downloads/items.py).

## Native authentication Secret

Use an absolute receipt path in an owner-only directory outside Git:

The standalone public script may be staged outside its checkout. Receipt checks
reject actual Git ancestor markers (including worktree `.git` files) and require
the output directory to belong to the current operator. A fixed source-parent
guess is not used. The first staged bootstrap attempt refused this path check
before any Secret mutation; its source and refusal remain retained.

```text
python3 scripts/migration/qualify-ytptube.py bootstrap-secret --receipt /protected/evidence/ytdl-auth-bootstrap.json
```

This mode checks only existing Secret UID metadata first. An existing
`plex/ytdl-ytptube-auth` is preserved byte-for-byte. If absent, it generates a
random operator username and 48-character random password in RAM, then creates
an Opaque Secret with keys `username` and `password` through `kubectl create -f -` JSON
stdin. A concurrent existing object is preserved. No apply/update, temporary
credential file, command-line value, last-applied annotation or value output is
used. BORTUS/native Kubernetes Secrets remain the credential authority, with no
BORTUS SQLite credential copy. The application consumes those exact native
references; its normal upstream first-user bootstrap creates its own password
hash. If the application already has a different local account, the helper fails
login rather than changing accounts or resetting the native Secret. Authorized
operators can retrieve the native credential through the established BORTUS UI;
the helper does not export it.

## Cold preservation metadata

Root captures a fresh cold baseline after stopping the old MeTube writer through
the existing Flux owner. This is separate from the acceptance helper. Use the
reviewed read-only full-state access to the original data-0/data-1 claims, never
walk the NAS media corpus. Keep the full encrypted/cold backup independently.
The prepared [MeTube state backup/reobservation playbook](METUBE-STATE-BACKUP.md)
provides this separate full-claim path and emits the compatible private SHA-256
baseline. It has not been run by source preparation and does not change the
acceptance helper's own `legacy_reobserved:false` boundary.
The candidate uses the verified existing UID/GID 1000 directly, without fsGroup,
so kubelet does not recursively alter legacy file ownership or permissions.
Minimal protected metadata JSON schema:

```json
{
  "claims": [
    {"namespace": "plex", "name": "ytdl-data-0", "uid": "<actual-uid>"},
    {"namespace": "plex", "name": "ytdl-data-1", "uid": "<actual-uid>"},
    {"namespace": "plex", "name": "ytdl-data-2", "uid": "<actual-uid>"}
  ],
  "algorithm": "hmac-sha256",
  "legacy_state_files": {
    "data-0/<relative-legacy-file>": "<64-lowercase-hex-hmac>",
    "data-1/<relative-legacy-file>": "<64-lowercase-hex-hmac>"
  }
}
```

Use an independently protected operator HMAC key outside the baseline, helper
and receipts. Plain `sha256` is also supported for full-file hashes in private
evidence. Do not store file contents, URLs, cookies, Secret values or the HMAC key
in this metadata. Record each original file, with exact exclusions for the new
`data-0/ytptube-config/` and the new data-1 Deno/app cache directories. The actual
old tree and exclusions must be recorded by the root cold-state observation;
the example placeholders are not evidence. The helper binds the entire baseline
hash, canonical fingerprint-map hash and exact three PVC UIDs into its receipt.

It always records **`legacy_reobserved:false`**. The application sees `/config`
through subPath `ytptube-config` and cannot inspect sibling legacy files. Root
must independently re-observe the same full-state read-only view after the test
and restart, compare the original hashes/exclusions and record that result.
Neither matching claim UIDs nor a supplied baseline proves file preservation.

## Actual bounded sample

The reviewed chart must first deliver exactly one Ready writer on the scanned,
immutable derivative. All three original PVCs must remain Bound with their
baseline UIDs. `/config` must be data-0 subPath `ytptube-config`, `/tmp_dir` must
be data-1, and `/downloads` must be the original NAS data-2. The helper does not
change chart storage, create a Pod, mount a claim or restart the application.
It validates Pod -> ReplicaSet -> existing Deployment ownership and exact
spec/runtime image digest, and refuses an overlapping or terminating old writer.

```text
python3 scripts/migration/qualify-ytptube.py download --expected-image <accepted-name@sha256:digest> --preservation-baseline /protected/evidence/ytdl-cold-metadata.json --receipt /protected/evidence/ytdl-download.json
```

Credentials are read from the one native Secret into RAM. Requests use an
in-memory cookie jar, direct metadata-resolved ClusterIP, no environment proxy,
same-origin headers and no redirects. The helper logs out its own session at the
end without affecting other sessions. It requires authentication enabled and
already bootstrapped, downloads path `/downloads`, console/browser control off,
an empty existing queue, zero configured notifications, no Apprise config, and
the exact reviewed upstream default preset. It does not change any settings.

It verifies pinned yt-dlp 2026.10.21, EJS 0.8.0 and certifi 2026.10.19, supported
Deno >=2.3, FFmpeg/FFprobe versions and the provider's localhost:4416 `/ping`
version/uptime schema. A provider heartbeat does not prove a token was requested
or that YouTube will accept it; the real download is a separate requirement.

The sole input URL is the fixed public Big Buck Bunny video `YE7VzlLtp-4`, sent
only in the JSON request body. The helper uses a unique owned folder
`.branconet-acceptance/ytptube-20261023-<12hex>` and fixed generated filenames.
It requests only seconds 0-5, video height <=240 plus low audio, no playlist,
20 MiB maximum filesize, rate 1 MiB/s, one fragment worker and zero retries.
It disables archive, external-exec, cookies and sidecar options and ignores all
conditions for this item. It never invokes a notification-test endpoint.

Metadata extraction has a 120-second HTTP limit. The identified item is then
started once and polled for at most 240 seconds at two-second intervals. The
helper checks actual bytes in only its own NAS output folder and matching
temporary filenames under `/downloads/.ytptube-temp`, with an aggregate 20 MiB
bound. Sampling can overshoot; yt-dlp's per-file cap is an additional guard,
and a full-format filesize estimate can reject a short section. No automatic
retry or broader format fallback follows a refusal.

Completion requires history status `finished`, matching output filename, actual
nonzero NAS bytes, SHA256 and FFprobe video+audio streams with 1-7 seconds duration
and height <=240. Receipts retain exact history ID, test folder, sample hash,
versions, owner/image identity and original claim UIDs. A completed file is not
normal UI/access-route acceptance. On failure/deadline the helper cancels only
its known owned item ID and preserves partial files/history. `.attempt.json`
and `.queued.json` sidecars permit review if it stops early. A metadata timeout
can leave an idle auto-start-disabled item; inspect that exact folder manually
instead of re-running blindly. No receipt or test folder is overwritten.

## Restart persistence and remaining acceptance

Root performs the normal approved Pod restart under the existing Flux ownership.
Then run a separate read-check mode with a new receipt path:

```text
python3 scripts/migration/qualify-ytptube.py check-after-restart --expected-image <same-accepted-name@sha256:digest> --preservation-baseline /protected/evidence/ytdl-cold-metadata.json --baseline /protected/evidence/ytdl-download.json --receipt /protected/evidence/ytdl-after-restart.json
```

This mode queues nothing. It requires a new Pod UID or increased restart count,
same Deployment/claim UIDs, same completed history item, media bytes/hash/streams
and runtime/provider versions. It still records legacy re-observation false.
Root separately verifies legacy fingerprints, normal UI login/playback/download,
all retained LAN routes and old NAS media preservation, and reviews residual
scan findings before full adoption acceptance. HTTP 403/429, cookie/account/IP
restrictions, JS failures or unavailable formats leave download acceptance open;
the helper records only fixed diagnostic categories, never raw signed media URLs.

The runtime observation also requires pip/setuptools/pkg_resources/ensurepip
absence, empty YTP_PIP_PACKAGES and no active pip.txt entries. Removal of complete
install-only code addresses the real vendored package findings; no analyzer or
SBOM suppression is used. Application dependency changes require an image build.
