FROM ghcr.io/flaresolverr/flaresolverr@sha256:c80ae007ce2ccdcd217a12426e4f039ef763ff90738c808d38810c3e59323767 AS runtime

# The immutable vendor USER is flaresolverr. Restore it after OS maintenance;
# inherited ENTRYPOINT/CMD/WORKDIR/ENV/VOLUME/ports remain unchanged.
USER root
COPY verify-os.py /usr/share/branconet-security/flaresolverr/verify-os.py
RUN set -eu; \
    export PYTHONDONTWRITEBYTECODE=1; \
    /usr/local/bin/python /usr/share/branconet-security/flaresolverr/verify-os.py before; \
    apt-get -o APT::Get::AllowUnauthenticated=false -o Acquire::Check-Valid-Until=true -o Acquire::AllowInsecureRepositories=false -o Acquire::AllowDowngradeToInsecureRepositories=false update; \
    DEBIAN_FRONTEND=noninteractive apt-get -o APT::Get::AllowUnauthenticated=false -y --no-remove --no-install-recommends --only-upgrade install chromium chromium-common chromium-driver; \
    DEBIAN_FRONTEND=noninteractive apt-get -o APT::Get::AllowUnauthenticated=false -y --no-remove --with-new-pkgs upgrade; \
    /usr/local/bin/python /usr/share/branconet-security/flaresolverr/verify-os.py after; \
    rm -rf /var/lib/apt/lists/*

# Keep the OS-only receipts above phase-accurate. A separate, hash-pinned
# Python phase changes only the three reviewed distributions and their vendors.
COPY requirements-security.txt verify-python.py /usr/share/branconet-security/flaresolverr/
RUN set -eu; \
    export PYTHONDONTWRITEBYTECODE=1; \
    /usr/local/bin/python /usr/share/branconet-security/flaresolverr/verify-python.py before; \
    /usr/local/bin/python -m pip install --disable-pip-version-check --no-cache-dir --no-index --no-deps --no-compile --only-binary=:all: --require-hashes -r /usr/share/branconet-security/flaresolverr/requirements-security.txt; \
    /usr/local/bin/python /usr/share/branconet-security/flaresolverr/verify-python.py after
USER flaresolverr
RUN PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python /usr/share/branconet-security/flaresolverr/verify-python.py runtime
