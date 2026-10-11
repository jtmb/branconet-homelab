# Immutable BORTUS release image builder

`scripts/migration/build-bortus-release-image.py` consumes the archive and manifest
produced by `prepare-bortus-release-context.py`. Supply the exact lowercase
40-character commit and independently pinned SHA-256 hashes of both artifacts.
The helper verifies the closed manifest, complete regular tar inventory, paths,
modes, raw Git blob IDs and SHA-256 hashes, required Docker/package/schema files,
migration inventory and the producer's exclusions before any SSH request.
Limits are 2,000 included plus excluded entries, 16 MiB per source file, 128 MiB
source total, 144 MiB compressed/decompressed archive and 4 MiB manifest.
PAX path headers are supported within 8 KiB; links, global/other extensions,
unexpected metadata and nonzero payload after tar EOF refuse. Nothing is extracted.

Run under Linux/WSL as the approved operator. Source inputs must be bounded,
regular, operator-owned and not group/world writable. Each is copied fresh with
nofollow/nonblocking reads, stable inode/content timestamps before and after,
and a protected copy hash/identity check immediately before streaming. The
protected copy pins ctime/mtime and link count as well as inode, avoiding
acceptance of a replaced file whose inode was reused. A post-stream check
refuses completion if the copy changes during dispatch; it cannot undo remote
work already dispatched. The coordinator must exclude concurrent writes by
the operator to the owned run and supplied source inputs.
The
operator runtime parent may be owned mode 0755; all ancestors must be owned by
root or the operator and not group/world writable. The final parent is pinned
and operator-owned. A new, deterministic `bortus-release-<fullcommit>` directory
is created mode 0700 and its parent entry is fsynced. Run files are mode 0600.
Any existing run refuses; the helper never reopens, adopts, overwrites or retries
an earlier intent, including failed validation or an uncertain outcome.

```sh
python3 scripts/migration/build-bortus-release-image.py \
  --context /approved/runtime/release-input/context.tar.gz \
  --manifest /approved/runtime/release-input/context.json \
  --source-commit <exact-lowercase-40hex-commit> \
  --context-sha256 <independently-pinned-64hex> \
  --manifest-sha256 <independently-pinned-64hex> \
  --runtime-parent /home/brajam/.local/share/branconet-migration
```

The sole destination is `james@192.168.0.4`, SSH port 2002, BatchMode=yes,
StrictHostKeyChecking=yes and ForwardAgent=no. No sudo, password, forwarded
agent, operator kubeconfig or runtime Secret is supplied. The sole build arg is
the approved nonsecret `KUBECTL_VERSION=v1.37.1`. Docker receives the verified
archive on stdin and the exact tag `bortus:release-<fullcommit>`. Existing tags
refuse both during the initial query and immediately before the remote build.
Docker provides no atomic tag compare-and-set: the release coordinator must
hold exclusive builder/tag ownership throughout this operation. The helper
does not claim to exclude an unrelated concurrent Docker writer.

A file-and-directory-fsynced pending record exists before build dispatch.
Complete build stdout/stderr are retained separately in the protected run,
hashed by streaming reads rather than buffered as a whole. SSH query/inspection
timeouts are 30 seconds; build timeout is 2,400 seconds, with a 15-second SSH
connection timeout. The local SSH child is waited/reaped by subprocess.run.
Timeout/lost reply (SSH exit 255), failed metadata inspection and post-dispatch
durability failures leave an uncertain intent or the prior pending record.
The remote Docker build may still run after a lost reply; no automatic retry,
remote cleanup, cancellation or image adoption is attempted. A received normal
nonzero build exit is failed; the remote pre-build tag guard exit 73 is refused.
Flush failures never grant success. This is fault injection qualification, not
power-loss testing. Protected logs may contain complete build diagnostics and
must not be copied indiscriminately into Git or public reports.

After build exit zero, the helper inspects only image config ID, positive image
size and five exact labels: source commit, application tree, context hash,
manifest hash and unique build owner. It never inspects environment values or
full image configuration. The `sha256:` config image ID is **not** an OCI
manifest or runtime digest. Successful completion records no qualified runtime
digest and `deployed=false`, `runtime_accepted=false`. This helper has no run,
deploy, export or preload API. Image scanning, runtime/migration/data acceptance,
admission, distribution and release are separate coordinator gates.
The separate [export/preload helper](BORTUS-RELEASE-STAGING.md) consumes this
exact completed receipt and retains its own independent staging intents.

The prior `build-bortus-image.py` binds a historical fixed image/source checkpoint;
its evidence remains historical. This generic helper does not reinterpret that
record. The separately qualified operator mTLS adapter has a scoped live TLS 1.3
Volume LIST/HTTP 200 watch-handshake receipt; it supplies no build input and is
not full independent restore or restored-data acceptance. See
[restore watch prerequisites](BORTUS-RESTORE-WATCH.md).

The local tests use public disposable source archives, actual POSIX file/dir
flushes and injected filesystem/subprocess faults. They do not contact the
builder, read operator credentials, run Docker, build an image or deploy.

Root selected immutable `7e30b9b4` for an inert recovery holder after independently
verifying its raw/working sources, 687 compiled files, original Windows and Linux
functional artifacts. The actual immutable build completed at 09:14:59 UTC on
2026-10-11. Exact source/context/build/config bindings are in the
[holder receipt](../evidence/bortus-holder-source-image-7e30-20261011.json).
This build does not qualify application performance, image runtime or deployment.
