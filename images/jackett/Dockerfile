FROM docker.io/linuxserver/jackett@sha256:cdea5d3209a6ab1fb8eb954ec0b8169b7d54274617f42bf5c74f22a92075755f AS runtime

# Same-branch OS packages only; application artifacts must remain byte-identical.
RUN set -eu; set -o pipefail; \
    case "$(cat /etc/alpine-release)" in 3.22.*) ;; *) exit 1 ;; esac; \
    awk '/^[[:space:]]*($|#)/ { next } { active++; if ($0 !~ /\/v3[.]22\/(main|community)\/?$/) bad=1 } END { exit (bad || !active) }' /etc/apk/repositories; \
    mkdir -p /usr/share/branconet-security; \
    printf '%s\n' 'docker.io/linuxserver/jackett@sha256:cdea5d3209a6ab1fb8eb954ec0b8169b7d54274617f42bf5c74f22a92075755f' > /usr/share/branconet-security/base-image.txt; \
    cp /etc/alpine-release /usr/share/branconet-security/alpine-before.txt; \
    apk info -v | LC_ALL=C sort > /usr/share/branconet-security/packages-before.txt; \
    find /app/Jackett -type f -exec sha256sum {} \; | LC_ALL=C sort > /usr/share/branconet-security/application-before.sha256; \
    apk upgrade --no-cache; \
    apk info -v | LC_ALL=C sort > /usr/share/branconet-security/packages-after.txt; \
    cp /etc/alpine-release /usr/share/branconet-security/alpine-after.txt; \
    find /app/Jackett -type f -exec sha256sum {} \; | LC_ALL=C sort > /usr/share/branconet-security/application-after.sha256; \
    cmp /usr/share/branconet-security/application-before.sha256 /usr/share/branconet-security/application-after.sha256
