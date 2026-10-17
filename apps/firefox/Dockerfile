# syntax=docker/dockerfile:1.28@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b
# Managed Firefox in a single-app kiosk session on the bare core.
ARG BASE_IMAGE
# hadolint ignore=DL3006
FROM ${BASE_IMAGE}

USER 0

RUN --mount=type=bind,from=firefox,source=install-apt.sh,target=/tmp/install-firefox.sh \
    sh /tmp/install-firefox.sh

RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true

# hadolint ignore=DL3022
COPY --from=firefox policies.json /etc/firefox/policies/policies.json

ENV WAAS_APP="firefox"

USER 1000:1000
