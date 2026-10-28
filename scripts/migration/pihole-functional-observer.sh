#!/bin/sh
# Explicit bounded Pi-hole functional observation; existing native CLI key only.
set -eu
set +x
expected_version=$1
shift
base=http://127.0.0.1:80/api
sid=
request() {
  printf 'header = "X-FTL-SID: %s"\n' "$sid" | curl --disable --config - --silent --show-error --fail --noproxy '*' --connect-timeout 3 --max-time 15 --max-filesize 4194304 "$base$1"
}
logout() {
  if [ -n "$sid" ]; then
    printf 'header = "X-FTL-SID: %s"\n' "$sid" | curl --disable --config - --silent --show-error --fail --noproxy '*' --connect-timeout 3 --max-time 10 --request DELETE "$base/auth" >/dev/null || true
  fi
}
trap logout EXIT
code=$(curl --disable --silent --show-error --noproxy '*' --connect-timeout 3 --max-time 10 --max-filesize 65536 --output /dev/null --write-out '%{http_code}' "$base/groups")
test "$code" = 401
# Password and SID remain in Pod RAM/pipes; no query-string, argv, disk or log.
sid=$(jq -cn --rawfile p /etc/pihole/cli_pw '{password:($p|gsub("[\r\n]+$";""))}' | curl --disable --silent --show-error --fail --noproxy '*' --connect-timeout 3 --max-time 15 --max-filesize 65536 --header 'Content-Type: application/json' --request POST --data-binary @- "$base/auth" | jq -er '.session|select(.valid==true)|.sid')
case "$sid" in ''|*[!A-Za-z0-9+/=]*) exit 1 ;; esac
version=$(request /info/version | jq -er '.version.ftl.local.version')
test "$version" = "$expected_version"
request /dns/blocking | jq -e 'has("blocking")' >/dev/null
request /stats/summary | jq -e '(.queries|type)=="object"' >/dev/null
request /groups | jq -e '(.groups|type)=="array"' >/dev/null
request /clients | jq -e '(.clients|type)=="array"' >/dev/null
local_record=$(request /config | jq -er 'select((.config|type)=="object") | (.config.dns.hosts // []) | map(select(test("^[0-9]+[.][0-9]+[.][0-9]+[.][0-9]+[[:space:]]+[A-Za-z0-9_.-]+"))) | (first // "")')
local_ip=
local_name=pi.hole
local_source=builtin-pi-hole
if [ -n "$local_record" ]; then
  local_ip=$(printf '%s\n' "$local_record" | awk '{print $1}')
  local_name=$(printf '%s\n' "$local_record" | awk '{print $2}')
  local_source=retained-configured-host
fi
check_dns() {
  protocol=$1
  target=$2
  name=$3
  expected=$4
  host=${target%:*}
  port=${target##*:}
  case "$host" in ''|*[!0-9.]*) exit 1 ;; esac
  case "$port" in ''|*[!0-9]*) exit 1 ;; esac
  test "$port" -ge 1 && test "$port" -le 65535
  if [ "$protocol" = TCP ]; then transport=+tcp; else transport=+notcp; fi
  response=$(dig "@$host" -p "$port" "$name" A +time=3 +tries=1 +ignore "$transport" +noall +comments +answer)
  printf '%s\n' "$response" | grep -q 'status: NOERROR'
  if printf '%s\n' "$response" | grep -Eq 'flags:[^;]*[[:space:]]tc[;[:space:]]'; then exit 1; fi
  answers=$(printf '%s\n' "$response" | awk '!/^;/ && $4 == "A" {print $5}')
  test -n "$answers"
  if [ -n "$expected" ]; then
    printf '%s\n' "$answers" | grep -Fxq "$expected"
  else
    printf '%s\n' "$answers" | grep -qv '^0[.]0[.]0[.]0$'
  fi
}
checks=0
for target in 10.96.11.155:53 "$@"; do
  for protocol in UDP TCP; do
    check_dns "$protocol" "$target" example.com ''
    check_dns "$protocol" "$target" "$local_name" "$local_ip"
    checks=$((checks+2))
  done
done
printf 'header = "X-FTL-SID: %s"\n' "$sid" | curl --disable --config - --silent --show-error --fail --noproxy '*' --connect-timeout 3 --max-time 10 --request DELETE "$base/auth" >/dev/null
sid=
trap - EXIT
printf '{"passed":true,"authenticated_reads":6,"unauthenticated_read_rejected":true,"credential":"existing-native-cli-key","credential_location":"writer-Pod-RAM-only","own_session_deleted":true,"user_password_login_or_reset":false,"configuration_or_lists_mutated":false,"dns_checks":%s,"local_record_source":"%s","udp_fallback_to_tcp_disabled":true,"truncated_replies_rejected":true}\n' "$checks" "$local_source"
