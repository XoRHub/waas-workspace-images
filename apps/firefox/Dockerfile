# syntax=docker/dockerfile:1.29@sha256:572cebbc2b15e6f84c077742952674889cb63cd5e9b80abdffcbe587b6f19183
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
