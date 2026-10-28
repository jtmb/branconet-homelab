FROM docker.io/vaultwarden/server@sha256:efb3cde962015fcc036b2ea625242248611943b27212ebf4392841fb30fad055 AS runtime

# The immutable vendor USER is unset/root; no runtime configuration overrides.
# Preserve inherited CMD, ENTRYPOINT, ENV, WORKDIR, VOLUME and HEALTHCHECK.
COPY maintain-os.sh /usr/share/branconet-security/vaultwarden/maintain-os.sh
RUN /bin/bash /usr/share/branconet-security/vaultwarden/maintain-os.sh
