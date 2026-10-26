# Static-site vendor image transition

Owner: maintenance chat `01a12045-bf7e-73b3-8557-752d17c72ffd`. All new generated
controls, sources, observations, scanner state and encrypted backups stay in
the existing F:-backed ext4 root recorded in
[the output inventory](TASK-OUTPUT-INVENTORY.md). Stage children are
`operator-control`, `control-source/upstream-static-sites-20261026`,
`upstream-static-sites-20261026` and `security-review-20261026`. They are children
of the same existing root, not additional output roots or drives.

Scope: aplb, lucinda-art-gallery, minecraft-website and santos-web. Their chart
values currently select one custom Nginx image and separate Longhorn content
claims mounted at `/usr/share/nginx/html`. Preserve every site's content,
configuration, Secrets, original resource identities and routes. The Minecraft
website is a static site; no game server is installed or restored by this work.

Compare maintained official vendor variants and current security findings before
selection. Use the existing trusted scanner binary and public vulnerability
database, with all new caches/HOME/TMPDIR under the declared root. No scanner
container, image build, dependency install, GitHub Actions or image publication
is introduced. Check C: and destination capacity before downloads, and retain
the source/tool/database provenance, exact finding rows and limitations.

Before image adoption, bind each live workload/claim/Secret identity, hash all
served content and configurations, validate Nginx configuration and actual
published/ingress routes, then take complete encrypted content backups through
quiescent read-only readers. Authenticate source archives and NAS read-back.
Only then publish reviewed chart changes through local validation → validated →
Flux. Repeat state/routes on adopted and distinct restart Pods. Preserve all
rollback artifacts and failures. Final IAB remains after implementation.

Regeneration uses the maintained qualification/cold-backup/scanner scripts with
their recorded exact phases, image/tool digests and private output paths. Keep
unique receipts, source manifests, keys and required encrypted recovery data;
remove proven reproducible inactive caches/scratch with exact path/byte receipts.
No recursive broad prune or Windows disk-recovery claim is authorized.

Preparation only; no site deployment or security acceptance is claimed here.
