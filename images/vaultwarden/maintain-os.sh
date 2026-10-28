#!/bin/bash
# Fail closed within the immutable candidate's existing signed Debian 13 track.
set -euo pipefail
export LC_ALL=C
evidence=/usr/share/branconet-security/vaultwarden
sources=/etc/apt/sources.list.d/debian.sources
keyring=/usr/share/keyrings/debian-archive-keyring.pgp
app=(/vaultwarden /web-vault /start.sh /healthcheck.sh)

test "$(dpkg --print-architecture)" = amd64
grep -qx 'ID=debian' /etc/os-release
grep -qx 'VERSION_ID="13"' /etc/os-release
grep -qx 'VERSION_CODENAME=trixie' /etc/os-release
test ! -e /etc/apt/sources.list
test -f "$sources" && test ! -L "$sources"
test "$(find /etc/apt/sources.list.d -mindepth 1 -maxdepth 1 \( -name '*.list' -o -name '*.sources' \) -print)" = "$sources"
printf '%s  %s\n' f02a6fd0c0a28e5f47d4512c0e5d264138378272850fe41dcb370ec885a3fcba "$sources" | sha256sum --check --status
test -f "$keyring" && test ! -L "$keyring"
for file in /vaultwarden /start.sh /healthcheck.sh; do
    test -f "$file" && test ! -L "$file"
done
test -d /web-vault && test ! -L /web-vault
# Include vendor startup hooks if a future unexpectedly changed candidate adds
# them; their absence/presence is also part of the fixed base contract.
for hook in /etc/vaultwarden.sh /etc/bitwarden_rs.sh /etc/vaultwarden.d /etc/bitwarden_rs.d; do
    if test -e "$hook" || test -L "$hook"; then app+=("$hook"); fi
done
test ! -e "$evidence/packages-before.txt"
test ! -e "$evidence/preservation-passed.txt"

snapshot() {
    local phase=$1
    # The image has no mounted user data during build. Never traverse /data or
    # start the application, run a migration, or run its healthcheck here.
    find "${app[@]}" -printf '%y\t%m\t%U\t%G\t%p\t%l\0' | sort -z > "$evidence/application-$phase.metadata"
    find "${app[@]}" -type f -print0 | sort -z | xargs -0 --no-run-if-empty sha256sum > "$evidence/application-$phase.sha256"
    sha256sum "$sources" "$keyring" > "$evidence/repositories-$phase.sha256"
    dpkg-query -W -f='${binary:Package}\t${Version}\t${db:Status-Status}\n' | sort > "$evidence/packages-$phase.txt"
    awk -F '\t' '$3 == "installed" {print $1}' "$evidence/packages-$phase.txt" > "$evidence/installed-$phase.txt"
    cp /etc/os-release "$evidence/os-release-$phase.txt"
    for hook in /etc/vaultwarden.sh /etc/bitwarden_rs.sh /etc/vaultwarden.d /etc/bitwarden_rs.d; do
        if test -e "$hook" || test -L "$hook"; then
            printf 'present\t%s\n' "$hook"
        else
            printf 'absent\t%s\n' "$hook"
        fi
    done > "$evidence/startup-hooks-$phase.txt"
}

snapshot before
apt_get=(apt-get -o APT::Get::AllowUnauthenticated=false
    -o Acquire::Check-Valid-Until=true -o Acquire::AllowInsecureRepositories=false
    -o Acquire::AllowDowngradeToInsecureRepositories=false
    -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts=/etc/apt/sources.list.d)
"${apt_get[@]}" update
DEBIAN_FRONTEND=noninteractive "${apt_get[@]}" -y --no-remove --no-install-recommends --only-upgrade install curl libcurl4t64 libpcre2-8-0
DEBIAN_FRONTEND=noninteractive "${apt_get[@]}" -y --no-remove --with-new-pkgs upgrade
for package in curl libcurl4t64; do
    version=$(dpkg-query -W -f='${Version}' "$package")
    dpkg --compare-versions "$version" ge '8.14.1-2+deb13u7'
done
dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libpcre2-8-0)" ge '10.46-1~deb13u3'
snapshot after
cmp "$evidence/application-before.metadata" "$evidence/application-after.metadata"
cmp "$evidence/application-before.sha256" "$evidence/application-after.sha256"
cmp "$evidence/repositories-before.sha256" "$evidence/repositories-after.sha256"
cmp "$evidence/startup-hooks-before.txt" "$evidence/startup-hooks-after.txt"
comm -23 "$evidence/installed-before.txt" "$evidence/installed-after.txt" > "$evidence/removed-packages.txt"
test ! -s "$evidence/removed-packages.txt"
grep -qx 'VERSION_ID="13"' /etc/os-release
grep -qx 'VERSION_CODENAME=trixie' /etc/os-release
printf '%s\n' 'application-content-modes-ownership-symlinks=unchanged' \
    'apt-sources-keyring=unchanged' 'installed-packages-removed=0' \
    'curl-libcurl4t64>=8.14.1-2+deb13u7' 'libpcre2-8-0>=10.46-1~deb13u3' \
    'user-data-accessed=false' 'application-started=false' > "$evidence/preservation-passed.txt"
rm -rf /var/lib/apt/lists/*
