# Seerr security image preparation

Upstream 3.5.1's signed image still contains published fixable dependency
vulnerabilities as of 2026-10-23. This recipe retains its exact upstream source
commit and patches dependency versions. It is a separately built local derivative,
not an upstream-signed release. Build, scan and migration acceptance are pending.

First export target `lock`, retain/review its generated pnpm-lock.yaml alongside
this recipe, then build target `runtime` with that frozen lock. The source archive
and base image are pinned by SHA256. Alpine packages update during preparation;
record their actual versions and the resulting immutable image digest. BuildKit
is isolated from production credentials and data. Build output alone is not
permission to deploy an incompatible migration.

The October 23 production-host BuildKit attempt was stopped after disk pressure.
Its Ansible role now permits only status/stop, preserving the sealed attempt and
failure evidence. The approved private CI runner failed its disk reserve check
before building. Worker1's existing filesystem has since been expanded safely;
the fresh worker1-only role provides a separately sealed, resource-limited build
after all original cluster resources recover. The retired master attempt stays frozen.

Next is rebuilt with its patched version; replacing a library under an existing
Next build is insufficient. Runtime dependencies are pruned with lifecycle
scripts disabled: the first worker1 attempt failed because pruning removed
development Husky and then the upstream prepare script imported it. Native
install scripts already ran during the frozen dependency installation; the
production prune does not need to rerun them. The failed attempt remains intact.
Tini handles
PID1/orphan reaping. npm/corepack and their install-only dependency trees are
removed from the final runtime. The new application uses UID/GID1000 and `/app/config`.
The upstream direct node-gyp dependency moves to build-only dependencies, and
SQLite's redundant optional node-gyp is targeted for removal, but the exported
lock still contains an optional peer closure; inspect the final image rather
than claiming the dependency is absent. Native SQLite must build and
pass an actual load/read check before adopting the image. SQLite's tar dependency
is patched and the complete Next application is rebuilt; no compiled build is
carried across incompatible dependency versions.
The complete cold Overseerr backup is the compatible rollback source.

The subsequent r2 build passed pruning preparation but stopped at TypeScript:
`@types/email-templates` 10.0.4 still imports the legacy Nodemailer 8 declaration,
whereas Nodemailer 10.0.6 includes its own Mail class. The recipe now checks the
exact original declaration SHA-256 before adapting that build-only declaration
to Nodemailer's own `Mail`, `TransportConfig` and `SendMailOptions` exports. It
does not cast the application transport, disable TypeScript checks or alter mail
runtime behavior. That declaration adaptation itself does not require lock
regeneration. The separate ip-address 10.3.1 → 10.7.4 security change does require
a new frozen lock, retained separately from the original. A fresh attempt must
rebuild and pass both application compilation and local mail serialization.
The new 561,754-byte lock is SHA-256
`9665b245267e7c864210bdf85f1098c0891f30946c64b3781f44077fff0b7811`.
Metadata-only pnpm 10.24.0 resolution used official Node 22.23.4, a 512 MiB heap,
disabled lifecycle scripts and no pnpmfile. It updates ip-address across the
direct dependency, override, express-rate-limit and socks; pnpm also connects
the already pinned Handlebars 4.7.10 optional peer in consolidate/email-templates.
The original lock and failed attempts stay intact. The local isolated declaration
comparison reproduces the original MailMessage diagnostic and compiles after
the adaptation; it does not establish full Seerr build or runtime acceptance.

Private CI run `40047979424` passed the mail declaration adaptation, Next
TypeScript checking and optimized Next compilation, then refused the server
compile at `imageproxy.ts`: Axios 1.20 types common response headers as a union,
while the image cache requires strings. The source-phase override now verifies
the complete pinned image-proxy file SHA256 before adding explicit string
guards for content-type and cache-control. Valid strings retain the existing
MIME lookup, cache-age parsing, fallback age and ETag handling. Missing/null
headers retain the empty content-type and `0` cache-control defaults. Other
nonstring values throw into the existing caught cache-miss path; they are not
coerced into header strings. No type assertion, disabled type check, dependency
change, lock regeneration or image-cache protocol redesign is introduced.
One focused check with actual Axios 1.20.0 declarations and TypeScript 5.4.5
reproduced both original diagnostics and passed after the guarded adaptation.
It runs no Seerr imports, server, API or cluster operation. The failed artifact
remains retained; a fresh full server/image build and live image checks are
still required. Axios' [header declarations](https://github.com/axios/axios/blob/v1.20.0/index.d.ts)
and [HTTP adapter](https://github.com/axios/axios/blob/v1.20.0/lib/adapters/http.js)
document the widened type and actual Node response-header wrapping.

After importing the exact built image, run `verify-runtime.cjs` as UID 1000 in a
temporary Pod without production mounts or credentials. It checks the selected
dependency versions, native SQLite query, bcrypt, Sharp decoding/encoding, local
mail serialization, compiled Next/server output and Tini. Mail uses JSON transport
only and sends nothing. This check does not replace the production account/data,
integration, routing and restart checks after migration. The script is injected
through operator stdin; it is not an input to the already sealed build recipe.
The first isolated check stopped at Sharp's private `package.json` export before
native checks ran. The check now reads metadata directly from the installed
application dependency and verifies its name/version; it does not import a
private package subpath. The failed check remains evidence and does not imply
an application or native-module failure.

See [cluster maintenance](../../docs/CLUSTER-SECURITY.md) and the separate private
charts migration runbook. Record residual/unfixed scan findings honestly.

The corrected isolated check actually passed on October 24 against the exact
CI image above: native SQLite, bcrypt, Sharp and JSON-only mail serialization,
compiled Next/server output and Tini, UID 1000, without production mounts or
credentials.

Verification receipt fingerprint (SHA256)

`6f7ad4a814099f759c2190f27c372a42476f05d30c14e60fae07128f29227bf9`.
All three independent-runtime caches hold that image. Production account/data,
settings, integration and restart acceptance remain pending.

## Included frozen production lock

This isolated maintenance source includes the already reviewed public
`pnpm-lock.yaml` (561,754 bytes), SHA256
`9665b245267e7c864210bdf85f1098c0891f30946c64b3781f44077fff0b7811`.
It closes the runtime Dockerfile COPY dependency for a fresh clone; it is copied
byte-for-byte from the accepted CI recipe, not re-resolved. Historical external
locks/failed attempts remain preserved. No dependency install, build or image
adoption follows from publishing this file.


The public `pnpm-lock.yaml` retained here is the accepted 561,754-byte lock
(SHA256 `9665b245267e7c864210bdf85f1098c0891f30946c64b3781f44077fff0b7811`).
The root `.gitattributes` requires LF for this file so Windows checkout conversion
cannot change the qualified lock bytes. No dependency resolution is performed.
