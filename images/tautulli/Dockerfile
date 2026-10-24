FROM docker.io/library/python:3.13.17-slim-trixie@sha256:fe14fd57a4c0361110eaa0c284112b189750bcb43fb04bb5d1ee7b7744027ccf AS cpython-source
COPY copy-cpython.py cpython-core-manifest.json /usr/share/branconet-security/tautulli/
RUN PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python /usr/share/branconet-security/tautulli/copy-cpython.py export

FROM ghcr.io/tautulli/tautulli@sha256:a4323bc09b27e265e269d79421ed3eb795083ef988bb84788eba89e5738c8005 AS runtime

# Keep the vendor's unset/root USER and inherited startup/configuration. The
# entrypoint needs root to apply PUID/PGID and then drops to the tautulli user.
COPY maintain.py wheel-inputs.json copy-cpython.py cpython-core-manifest.json /usr/share/branconet-security/tautulli/
RUN set -eu; \
    export PYTHONDONTWRITEBYTECODE=1; \
    /usr/local/bin/python /usr/share/branconet-security/tautulli/maintain.py before-os; \
    apt-get -o APT::Get::AllowUnauthenticated=false -o Acquire::Check-Valid-Until=true -o Acquire::AllowInsecureRepositories=false -o Acquire::AllowDowngradeToInsecureRepositories=false update; \
    DEBIAN_FRONTEND=noninteractive apt-get -o APT::Get::AllowUnauthenticated=false -y --no-remove --with-new-pkgs upgrade; \
    /usr/local/bin/python /usr/share/branconet-security/tautulli/maintain.py after-os; \
    rm -rf /var/lib/apt/lists/*

# Stage only the inspected core, never donor site-packages/pip/bootstrap. Capture
# the original state before replacing files; old noninstaller packages survive.
RUN PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python /usr/share/branconet-security/tautulli/copy-cpython.py before
COPY --from=cpython-source /cpython-runtime/ /usr/share/branconet-security/tautulli/cpython-input/
COPY --from=cpython-source /usr/share/branconet-security/tautulli/cpython-export.json /usr/share/branconet-security/tautulli/cpython-export.json
RUN PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python /usr/share/branconet-security/tautulli/copy-cpython.py install
ENV PYTHON_VERSION=3.13.17 \
    PYTHON_SHA256=6020bd10aff3bf4821be16f088ebb1591beb7b811dcd8fab1da8f7c22a7b27e7
RUN PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python /usr/share/branconet-security/tautulli/copy-cpython.py after

RUN set -eu; \
    export PYTHONDONTWRITEBYTECODE=1; \
    /usr/local/bin/python /usr/share/branconet-security/tautulli/maintain.py python; \
    /usr/local/bin/python /usr/share/branconet-security/tautulli/maintain.py runtime-root; \
    gosu tautulli /usr/local/bin/python /usr/share/branconet-security/tautulli/maintain.py runtime-user
