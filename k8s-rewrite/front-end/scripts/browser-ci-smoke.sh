#!/usr/bin/env bash
set -euo pipefail
umask 077
test "$(id -u)" -ne 0
test "$#" -eq 1
test "$1" = acquire -o "$1" = run
test -n "${RUNNER_TEMP:-}"
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ ]]
[[ "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]+$ ]]
compiler='node@sha256:c4d5523090a817b7aa86d2111241fdd4f66d1e27782b44160e6aa63b357ecb2d'
browser_image='mcr.microsoft.com/playwright@sha256:c091b21d9fae78c76e85cd4356431e9b018402f172a214fc7d7a5e9a7e29d8ac'
root="$(pwd -P)"
tools="$(realpath "$RUNNER_TEMP")/bortus-browser-tools-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
name="bortus-browser-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
app="$name-app"
browser="$name-chromium"
acquirer="$name-tools"
# Names are only admission/absence checks. They never grant removal authority.
for candidate in "$browser" "$app" "$acquirer"; do
  existing="$(timeout 5s docker ps -aq --no-trunc --filter "name=^/${candidate}$")"
  test -z "$existing"
done
[[ "${GITHUB_SHA:-}" =~ ^[a-f0-9]{40}$ ]]
marker="${GITHUB_RUN_ID}:${GITHUB_RUN_ATTEMPT}:${GITHUB_SHA}:$(sha256sum ci/browser-tools/package-lock.json | cut -d ' ' -f 1):$(sha256sum scripts/browser-ci-smoke.sh | cut -d ' ' -f 1)"
directory_owned=0
fixture_logs_emitted=0
cidfiles=()
capture_cid() {
  local file="$1" cid
  test -f "$file" && test ! -L "$file" || return 1
  test "$(wc -c < "$file")" -le 65 || return 1
  cid="$(cat "$file")" || return 1
  [[ "$cid" =~ ^[a-f0-9]{64}$ ]] || return 1
  printf '%s' "$cid"
}
cleanup() {
  local status=$? cleanup_failed=0 confirmed=0 name_queries=0 names_absent=true uncertain_create=false file owned left i
  trap - EXIT INT TERM
  # Only exclusive CID files armed before this invocation's create can grant authority.
  # An interrupted create without a valid CID file remains uncertain; never adopt its name.
  for ((i=${#cidfiles[@]}-1; i>=0; i--)); do
    file="${cidfiles[i]}"
    if [[ -e "$file" || -L "$file" ]]; then
      if owned="$(capture_cid "$file")"; then
        confirmed=$((confirmed+1))
        if left="$(timeout 5s docker ps -aq --no-trunc --filter "id=$owned")"; then
          if [[ -n "$left" ]]; then
            if [[ "$left" == "$owned" ]]; then
              # Browser is already removed; give the confirmed app a bounded orderly stop.
              if [[ "$file" == "$tools/app.cid" && "$fixture_logs_emitted" == 0 ]]; then
                timeout 7s docker stop --time 5 "$owned" >/dev/null 2>&1 || cleanup_failed=1
                if timeout 3s docker logs --tail 3 "$owned" 2>/dev/null; then fixture_logs_emitted=1; else cleanup_failed=1; fi
              fi
              timeout 10s docker rm -f "$owned" >/dev/null 2>&1 || cleanup_failed=1
            else cleanup_failed=1; fi
          fi
        else cleanup_failed=1; fi
      else uncertain_create=true; cleanup_failed=1; fi
    else uncertain_create=true; cleanup_failed=1; fi
  done
  for candidate in "$browser" "$app" "$acquirer"; do
    name_queries=$((name_queries+1))
    if left="$(timeout 5s docker ps -aq --no-trunc --filter "name=^/${candidate}$")"; then
      if [[ -n "$left" ]]; then names_absent=false; cleanup_failed=1; fi
    else names_absent=false; cleanup_failed=1; fi
  done
  if [[ "$directory_owned" == 1 && -d "$tools" && ! -L "$tools" && "$tools" == "$(realpath "$RUNNER_TEMP")/bortus-browser-tools-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" ]]; then
    if ! rm -rf -- "$tools"; then cleanup_failed=1; fi
  fi
  if [[ "$cleanup_failed" == 0 ]]; then cleanup_failed=false; else cleanup_failed=true; fi
  printf '{"browserCICleanupFailed":%s,"confirmedCIDCount":%s,"exactNameQueryCount":%s,"exactNamesAbsent":%s,"uncertainCreate":%s}\n' "$cleanup_failed" "$confirmed" "$name_queries" "$names_absent" "$uncertain_create"
  if [[ "$status" == 0 && "$cleanup_failed" == true ]]; then status=1; fi
  exit "$status"
}
if [[ "$1" == run ]]; then
  # Acquire-to-run ownership handoff: validate before installing any destructive cleanup.
  test -d "$tools" && test ! -L "$tools"
  test "$(stat -c '%u:%a' "$tools")" = "$(id -u):700"
  test -f "$tools/acquisition.marker" && test ! -L "$tools/acquisition.marker"
  test "$(stat -c '%u:%a' "$tools/acquisition.marker")" = "$(id -u):600"
  test "$(cat "$tools/acquisition.marker")" = "$marker"
  directory_owned=1
fi
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ "$1" == acquire ]]; then
  test ! -e "$tools"
  mkdir -m 700 "$tools"
  directory_owned=1
  cp ci/browser-tools/package.json ci/browser-tools/package-lock.json "$tools/"
  # Pinned official amd64 image: seven layers /949411114 compressed bytes in retained metadata.
  timeout --signal=TERM --kill-after=5s 180s docker pull --quiet --platform linux/amd64 "$browser_image"
  timeout 15s docker image inspect "$browser_image" --format '{{json .}}' > "$tools/image.json"
  test ! -e "$tools/acquirer.cid" && test ! -L "$tools/acquirer.cid"
  cidfiles+=("$tools/acquirer.cid")
  timeout 15s docker create --pull never --cidfile "$tools/acquirer.cid" --name "$acquirer" --platform linux/amd64 \
    --cpus 2 --memory 1g --memory-swap 1g --pids-limit 256 --cap-drop ALL --security-opt no-new-privileges \
    --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp:rw,nosuid,nodev,size=128m \
    --mount "type=bind,source=$tools,target=/tools" --workdir /tools \
    -e HOME=/tmp/bortus-browser-home -e NPM_CONFIG_USERCONFIG=/tmp/empty-user-npmrc -e NPM_CONFIG_GLOBALCONFIG=/tmp/empty-global-npmrc \
    -e NPM_CONFIG_CACHE=/tmp/npm-cache --entrypoint bash "$compiler" \
    -c 'mkdir -p "$HOME" && npm ci --ignore-scripts --omit=optional --no-audit --no-fund --loglevel=error --fetch-retries=0 --fetch-timeout=15000 --registry=https://registry.npmjs.org && node -e '\''const a=require("node:assert/strict"),p=require("./node_modules/playwright-core/package.json"),i=require("./image.json");a.equal(p.name,"playwright-core");a.equal(p.version,"1.62.1");a.deepEqual(p.dependencies||{},{});a.deepEqual(p.optionalDependencies||{},{});a.equal(i.Os,"linux");a.equal(i.Architecture,"amd64");a(i.RepoDigests.includes("mcr.microsoft.com/playwright@sha256:c091b21d9fae78c76e85cd4356431e9b018402f172a214fc7d7a5e9a7e29d8ac"));'\'''
  acquirer_cid="$(capture_cid "$tools/acquirer.cid")"
  timeout --signal=TERM --kill-after=5s 35s docker start --attach "$acquirer_cid"
  actual="$(timeout 5s docker inspect --format '{{.State.ExitCode}}' "$acquirer_cid")"
  test "$actual" = 0
  timeout 10s docker rm "$acquirer_cid" >/dev/null
  remaining="$(timeout 5s docker ps -aq --no-trunc --filter "name=^/${acquirer}$")"
  test -z "$remaining"
  (set -o noclobber; printf '%s\n' "$marker" > "$tools/acquisition.marker")
  # npm ci enforces the exact lock SHA512; no npm lifecycle script or browser installer runs.
  printf '%s\n' 'Browser CI tools acquired; execution still separate.'
  trap - EXIT
  exit 0
fi
test -d "$tools/node_modules/playwright-core"
cmp ci/browser-tools/package-lock.json "$tools/package-lock.json"
mkdir -m 700 "$tools/exchange"
test ! -e "$tools/app.cid" && test ! -L "$tools/app.cid"
cidfiles+=("$tools/app.cid")
timeout 15s docker create --pull never --cidfile "$tools/app.cid" --name "$app" --platform linux/amd64 --network none \
  --cpus 2 --memory 1g --memory-swap 1g --pids-limit 256 --cap-drop ALL --security-opt no-new-privileges \
  --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp:rw,nosuid,nodev,size=512m \
  --mount "type=bind,source=$root,target=/app,readonly" \
  --mount "type=bind,source=$tools/exchange,target=/exchange" --workdir /app \
  -e HOME=/tmp/bortus-ci-home --entrypoint node "$compiler" scripts/browser-ci-fixture.mjs >/dev/null
cid="$(capture_cid "$tools/app.cid")"
timeout 15s docker start "$cid" >/dev/null
end=$((SECONDS+60))
while [[ ! -f "$tools/exchange/ready.json" ]]; do
  test "$SECONDS" -lt "$end"
  running="$(timeout 5s docker inspect --format '{{.State.Running}}' "$cid")"
  test "$running" = true
  sleep 0.2
done
test ! -e "$tools/browser.cid" && test ! -L "$tools/browser.cid"
cidfiles+=("$tools/browser.cid")
timeout 15s docker create --pull never --cidfile "$tools/browser.cid" --name "$browser" --platform linux/amd64 \
  --network "container:$cid" --ipc private --shm-size 64m \
  --cpus 2 --memory 1g --memory-swap 1g --pids-limit 256 --cap-drop ALL --security-opt no-new-privileges \
  --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --mount "type=bind,source=$root,target=/app,readonly" --mount "type=bind,source=$tools,target=/tools,readonly" \
  --mount "type=bind,source=$tools/exchange,target=/exchange,readonly" --workdir /app \
  -e HOME=/tmp/bortus-browser-home -e PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
  --entrypoint node "$browser_image" scripts/browser-ci-smoke.mjs
browser_cid="$(capture_cid "$tools/browser.cid")"
timeout --signal=TERM --kill-after=5s 150s docker start --attach "$browser_cid"
actual="$(timeout 5s docker inspect --format '{{.State.ExitCode}}' "$browser_cid")"
test "$actual" = 0
timeout 25s docker stop --time 20 "$cid" >/dev/null
actual="$(timeout 5s docker inspect --format '{{.State.ExitCode}}' "$cid")"
test "$actual" = 0
timeout 5s docker logs "$cid"
fixture_logs_emitted=1
printf '%s\n' 'Finite compiled browser smoke and fixture shutdown passed.'
