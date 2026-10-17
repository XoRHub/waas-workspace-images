# syntax=docker/dockerfile:1.28@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b
# XFCE desktop on an apt core (ubuntu-desktop-noble, debian-desktop-13),
# plus the baseline every desktop should have: Firefox, git, ssh client,
# curl, vim, less, mise. apps/devtools builds on this image.
ARG BASE_IMAGE
# hadolint ignore=DL3006
FROM ${BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0

# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        xfce4-session \
        xfce4-panel \
        xfce4-settings \
        xfdesktop4 \
        xfwm4 \
        xfce4-terminal \
        thunar \
        adwaita-icon-theme \
    && apt-get purge -y --auto-remove xterm && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/*

# openssh-client only, never openssh-server.
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        openssh-client \
        curl \
        vim \
        less \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/*

RUN --mount=type=bind,from=firefox,source=install-apt.sh,target=/tmp/install-firefox.sh \
    sh /tmp/install-firefox.sh
# hadolint ignore=DL3022
COPY --from=firefox policies.json /etc/firefox/policies/policies.json

# gpgv is a separate package from gpg; ubuntu's apt depends on it,
# Debian 13's does not (sqv), so it is installed — and purged — only
# where this layer added it.
ARG TARGETARCH
# hadolint ignore=DL3008,SC2086
RUN --mount=type=bind,from=mise,source=install.sh,target=/tmp/install-mise.sh \
    apt-get update && \
    if dpkg -s gpgv >/dev/null 2>&1; then GPGV_PKG=""; else GPGV_PKG="gpgv"; fi && \
    apt-get install -y --no-install-recommends gpg ${GPGV_PKG} && \
    sh /tmp/install-mise.sh && \
    apt-get purge -y --auto-remove gpg ${GPGV_PKG} && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* /home/waas_user/.gnupg

# Shims cover non-interactive contexts (XFCE menu, scripts); `mise
# activate` in /etc/bash.bashrc covers interactive shells on old and new
# home volumes alike (skel is only seeded on a fresh PVC). MISE_* pinned
# because the shims path above hardcodes them and a session may inject XDG_*.
ENV PATH=/home/waas_user/.local/share/mise/shims:/home/waas_user/.local/bin:$PATH
ENV MISE_DATA_DIR=/home/waas_user/.local/share/mise \
    MISE_CACHE_DIR=/home/waas_user/.cache/mise
# hadolint ignore=SC2016
RUN printf '\n# mise (waas): user toolchains live on the home PVC.\neval "$(mise activate bash)"\n' \
        >> /etc/bash.bashrc

RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true

ENV WAAS_STARTUP=startxfce4

USER 1000:1000
