# Vaultwarden 1.37.4 Debian OS security derivative

Prepared source only. The exact sixth `vaultwarden` identifier is wired into
the artifact-only workflow and protected operator allowlists; no workflow run,
build, scan, chart, Flux, application deployment or data change is included. Existing production backup,
migration and acceptance gates remain required before any adoption.

The immutable candidate is
`docker.io/vaultwarden/server@sha256:efb3cde962015fcc036b2ea625242248611943b27212ebf4392841fb30fad055`.
Public Docker Hub OCI index, linux/amd64 manifest/config and all five layer blobs
were SHA-verified. `base-metadata.json` records that evidence without ENV values.
The source revision is `7c188967e7a467b19b2757bc3326f9cf3ccae327` (1.37.4).
This preserves that candidate's application fixes; it does not apply them to the
older running application or prove database migration safety.

The actual vendor config has unset USER (root), unset ENTRYPOINT, CMD
`["/start.sh"]`, WORKDIR `/`, VOLUME `/data`, exposed port 80 and its existing
`/healthcheck.sh` healthcheck. The derivative overrides none of those or ENV.
It adds only its build helper/evidence and upgrades installed OS packages.

The verified base is Debian 13 trixie. Its exact `debian.sources` uses the existing
Debian main trixie/trixie-updates/trixie-security repositories and archive keyring.
The helper refuses another OS/architecture/source-file hash, additional active
source files or unsigned/insecure repository exceptions. It uses authenticated
APT within that track, with `--no-remove`, explicitly upgrading curl, libcurl4t64
and libpcre2-8-0 before the general same-track upgrade. The actual final versions
must be at least `8.14.1-2+deb13u7` for curl/libcurl4t64 and
`10.46-1~deb13u3` for libpcre2-8-0. These are the available fixed versions for the
seven reported OS finding rows, not a forecast of a clean rebuilt scan.

The complete Rust `/vaultwarden` binary, `/web-vault` tree, `/start.sh` and
`/healthcheck.sh` are captured before/after with SHA-256, types, modes, numeric
ownership and symlink targets, including directory metadata. Existing optional
startup hooks are included if present. Any difference fails the build. The
original APT source/keyring hashes, package inventories and OS release are
retained under `/usr/share/branconet-security/vaultwarden/`; the helper also
proves no previously installed package disappeared. It does not strip package
metadata, rebuild/relabel Rust or web assets, start Vaultwarden, invoke its
healthcheck, access `/data` or execute a database/config migration.

Future execution still requires reviewed artifact-only CI execution,
inherited-config comparison, exact unsuppressed scan, protected cold backup,
documented 1.35.4-to-1.37.4 data qualification, correct native Secret/config
handling, authenticated application/integration checks and restart persistence.
This recipe grants none of those actions and changes no resource/publication
limits or rollback sources.

Primary sources: [pinned vendor Dockerfile](https://github.com/dani-garcia/vaultwarden/blob/7c188967e7a467b19b2757bc3326f9cf3ccae327/docker/Dockerfile.debian),
[1.37.4 release](https://github.com/dani-garcia/vaultwarden/releases/tag/1.37.4),
[Debian curl](https://packages.debian.org/trixie/curl) and
[Debian PCRE2](https://packages.debian.org/trixie/libpcre2-8-0).
