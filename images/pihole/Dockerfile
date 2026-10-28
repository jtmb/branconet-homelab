FROM docker.io/pihole/pihole@sha256:ee348529cea9601df86ad94d62a39cad26117e1eac9e82d8876aa0ec7fe1ba27 AS runtime

# Same-branch OS packages only; application artifacts must remain byte-identical.
RUN set -eu; set -o pipefail; \
    case "$(cat /etc/alpine-release)" in 3.23.*) ;; *) exit 1 ;; esac; \
    awk '/^[[:space:]]*($|#)/ { next } { active++; if ($0 !~ /\/v3[.]23\/(main|community)\/?$/) bad=1 } END { exit (bad || !active) }' /etc/apk/repositories; \
    mkdir -p /usr/share/branconet-security; \
    printf '%s\n' 'docker.io/pihole/pihole@sha256:ee348529cea9601df86ad94d62a39cad26117e1eac9e82d8876aa0ec7fe1ba27' > /usr/share/branconet-security/base-image.txt; \
    cp /etc/alpine-release /usr/share/branconet-security/alpine-before.txt; \
    apk info -v | LC_ALL=C sort > /usr/share/branconet-security/packages-before.txt; \
    find /usr/bin/pihole-FTL /usr/local/bin/pihole /opt/pihole /var/www/html/admin /etc/.pihole /usr/bin/start.sh /usr/bin/bash_functions.sh /pihole.docker.tag -type f -exec sha256sum {} \; | LC_ALL=C sort > /usr/share/branconet-security/application-before.sha256; \
    apk upgrade --no-cache; \
    apk info -v | LC_ALL=C sort > /usr/share/branconet-security/packages-after.txt; \
    cp /etc/alpine-release /usr/share/branconet-security/alpine-after.txt; \
    find /usr/bin/pihole-FTL /usr/local/bin/pihole /opt/pihole /var/www/html/admin /etc/.pihole /usr/bin/start.sh /usr/bin/bash_functions.sh /pihole.docker.tag -type f -exec sha256sum {} \; | LC_ALL=C sort > /usr/share/branconet-security/application-after.sha256; \
    cmp /usr/share/branconet-security/application-before.sha256 /usr/share/branconet-security/application-after.sha256
