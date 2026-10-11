# Independent inert-holder reader launcher

`scripts/migration/bortus-restore-reader.py` exports `mutations`, its exact `data`
and `metadata` interfaces, and `credentials`. Construct Collector and MutationAPI
through these interfaces. Use `ReaderLauncher(mutation_api, kubeconfig_path, options)`
and its `launch_reader(holder, deadline)` as the callback for `data.execute`.
Options must be this module's actual `credentials.OperatorMTLSOptions`, bound to
the reviewed absolute source path. Import/construction makes no request or process.

The launcher checks the actual live Collector, bound eligible target, confirmed
owned holder create and absence of delete intent. A fresh fixed Pod GET must match
the supplied current name/namespace/UID/opaque RV, owned run label, qualified image,
alternate node and exact inert read-only spec. Only the health fence's exact benign
API defaults are tolerated. The holder must be ownerless, running/Ready with one
running/Ready un-restarted holder container. Recreated, deleting, drifted, writable
or credential-bearing holders refuse before exec. Full before/after source and
consumer health fences remain coordinator/data-step duties.

The exact approved tagless Pod spec image must also equal the literal current
container status.imageID, including repository and digest. Missing IDs, config
IDs, digest-only IDs, registry aliases and docker-pullable substitutions refuse.
status.image is bounded display metadata (up to 4096 visible ASCII characters);
it may show the imported release tag and supplies no image proof. It never
replaces a missing/mismatched imageID. Current state must contain only running.
Root separately binds actual runtime name, config/source and three-node preload
evidence in its trusted qualification receipt. The immutable native handoff
retains the original failing five-case public regression and 71 passing local
imageID/reader/consumer/admitted-resource cases; root integration testing and
guarded restored-holder acceptance remain separate.

The existing protected kubeconfig inode is opened no-follow/nonblocking through
pinned safe directory anchors. Owner/mode0600/single-link/bounded size and read
continuity are checked. Closed embedded mTLS YAML and actual certificate/key loading
validate the exact opened FD's bytes and approved origin. Fresh options are used
for the Pod GET. Mid-invocation path replacement refuses. No credential file is
exported or cached: kubectl inherits the existing source FD and uses `/proc/self/fd/N`.
Every parent-owned source/anchor/memfd descriptor closes independently before the
child is returned. The child owns its inherited copy; Python reference release
does not claim heap zeroization.

Only existing `~/.local/share/branconet-migration/bin/kubectl` is dispatched after
regular executable/owned non-writable anchor checks. Args are fixed
`--kubeconfig /proc/self/fd/N --request-timeout=<remaining>s -n bortus exec <owned-pod>
-c holder -i -- node -`, where the owned Pod is exactly `bortus-restore-12hex`.
The child owns a new session, stdin/stdout pipes and stderr DEVNULL. Unrelated
descriptors close; the minimal environment contains no inherited proxy/auth
variables. No Node program, data or credentials enter argv. This helper writes no
stdin: `data.execute` exclusively sends `archive.NODE_READER`, bounds delivery and
capture, then closes the returned owned child.

One absolute monotonic deadline at most 300 seconds away covers validation, GET
and launch. The actual watch/holder prerequisites and budget are checked again
after Popen; already exited children refuse. Every pre-return failure independently
attempts owned child termination, pipes and descriptor cleanup. Attempts never
retry or adopt another process/resource. Arbitrary blocked Python callbacks are
not interruptible by these checks; actual scoped TLS has its bounded deadline.

GET and name-based exec cannot be atomic with Pod UID/spec. Exec offers no UID/RV
precondition, so replacement in that interval cannot be ruled out here. The
existing post-read UID/spec, source/consumer and live-watch fences remain mandatory.
Popen success or echoed fixture bytes do not prove production execution, data
equality, image/admission or live acceptance.

Qualification uses disposable embedded mTLS YAML and loopback HTTPS, protected
POSIX files/memfds and controlled Python children substituted for kubectl. It
tests inherited FD/stdin-only program delivery, drift, deadlines, ownership and
pre-return cleanup. No operator files, kubectl, Node, Docker, SSH or private API
are used. The full executor and live acceptance remain coordinator-owned.


The [actual inert public-fixture runtime](../evidence/bortus-holder-preload-runtime-7e30-20261011.json)
now executes the bounded Node reader on all three nodes. It uses writable memory
fixtures, not a production PVC or this full ReaderLauncher composition. Actual CRI
status.image displays a verified release tag despite exact digest Pod spec and
status.imageID. The selected correction accepts bounded display metadata while
requiring exact spec and literal runtime imageID. Neither a display name nor a
config image ID substitutes for immutable runtime identity. The cold checkpoint
used an independently checked exact runtime fence; full guarded restored-holder
and complete-row data acceptance remain pending.

Root integrated the selected admission collector, exact runtime imageID checks
and cold holder-release ordering fix through immutable handoffs, preserving the
actual earlier checkpoint evidence. The [combined local receipt](../evidence/bortus-admission-cold-helper-integration-20261011.json)
records 474 passing current test_bortus*.py cases, zero failures/errors/skips,
144 frozen Python source files and reaped exact process owners. This discovery
scope excludes differently named test modules. Loopback/fake API and disposable
local data checks do not prove live guard enforcement or independent recovery.
The corrected helper has not recaptured live data; the completed checkpoint
remains bound to its original executed source and explicit recovery journal.
