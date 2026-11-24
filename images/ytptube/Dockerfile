# syntax=docker/dockerfile:1
# Local security derivative; the final digest must be built, scanned and qualified.
FROM ghcr.io/arabcoders/ytptube:v2.7.5@sha256:3ba09ac58f0b541aa7182feb9198b44d3c62158a7749ec00d26de1abad7ca8d7 AS runtime

USER root
ARG DEBIAN_FRONTEND=noninteractive
LABEL org.opencontainers.image.title="YTPTube with Branconet security dependency patches" \
      org.opencontainers.image.source="https://github.com/arabcoders/ytptube" \
      org.opencontainers.image.version="v2.7.5-branconet-security-20261023"

# Preserve Debian 13 and its configured authenticated package repositories.
RUN apt-get update \
    && apt-get -y --no-install-recommends --no-remove upgrade \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' curl)" ge '8.14.1-2+deb13u7' \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libexpat1)" ge '2.9.0-1~deb13u1' \
    && rm -rf /var/lib/apt/lists/*

# Upstream's final image does not copy uv or guarantee pip inside its uv venv.
# Use a separately checksum-pinned installer, targeting each exact interpreter.
ADD --checksum=sha256:f68d291c75783122dad58ab77def0e13f3233f358731db5d6d7e8715603b928f https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-unknown-linux-gnu.tar.gz /tmp/branconet-uv.tar.gz
RUN mkdir /tmp/branconet-uv \
    && tar xzf /tmp/branconet-uv.tar.gz --strip-components=1 -C /tmp/branconet-uv \
    && /tmp/branconet-uv/uv pip install --no-cache --python /usr/local/bin/python3 --system \
       'certifi==2026.10.19' 'msgpack==1.2.1' 'urllib3==2.8.0' \
    && /tmp/branconet-uv/uv pip install --no-cache --python /opt/python/bin/python \
       'yt-dlp[default]==2026.10.21' 'yt-dlp-ejs==0.8.0' 'certifi==2026.10.19' \
       'aiohttp==3.14.4' 'curl_cffi==0.15.0' 'urllib3==2.8.0' 'msgpack==1.2.1'

COPY patch-provider.py verify-python.py /usr/local/share/branconet-ytptube/
RUN /usr/local/bin/python3 /usr/local/share/branconet-ytptube/patch-provider.py \
    && /usr/local/bin/python3 /usr/local/share/branconet-ytptube/verify-python.py system \
    && /opt/python/bin/python /usr/local/share/branconet-ytptube/verify-python.py app \
    && /tmp/branconet-uv/uv pip uninstall --python /usr/local/bin/python3 --system pip setuptools \
    && /tmp/branconet-uv/uv pip uninstall --python /opt/python/bin/python pip setuptools \
    && /usr/local/bin/python3 /usr/local/share/branconet-ytptube/verify-python.py system strip-bootstrap \
    && /opt/python/bin/python /usr/local/share/branconet-ytptube/verify-python.py app strip-bootstrap \
    && /usr/local/bin/python3 /usr/local/share/branconet-ytptube/verify-python.py system runtime \
    && /opt/python/bin/python /usr/local/share/branconet-ytptube/verify-python.py app runtime \
    && rm -rf /tmp/branconet-uv /tmp/branconet-uv.tar.gz

# No writable /config extractor overlay is needed. Keep the original image's
# tini, entrypoint, provider supervision, healthcheck, WORKDIR and application CMD.
ENV YTP_YTDLP_AUTO_UPDATE=false \
    YTP_YTDLP_VERSION=2026.10.21 \
    YTP_PIP_IGNORE_UPDATES=true \
    YTP_PIP_PACKAGES=""
USER app
