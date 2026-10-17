# syntax=docker/dockerfile:1.28@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b
# XFCE desktop on the Fedora core — dnf sibling of desktop/xfce/Dockerfile.
# Package deltas verified against Fedora 43: xfdesktop (not xfdesktop4),
# Thunar (capitalised), openssh-clients, vim-enhanced.
ARG BASE_IMAGE
# hadolint ignore=DL3006
FROM ${BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0

# hadolint ignore=DL3041
RUN dnf install -y --setopt=install_weak_deps=False \
        xfce4-session \
        xfce4-panel \
        xfce4-settings \
        xfdesktop \
        xfwm4 \
        xfce4-terminal \
        Thunar \
        adwaita-icon-theme \
    && dnf remove -y xterm && \
    dnf clean all && \
    rm -rf /var/cache/* /var/log/*

# Firefox from the Fedora repos: a real, current RPM, so the
# packages.mozilla.org dance of the apt sibling buys nothing here.
# .viminfo: root-owned dotfile left in the user's home by the transaction.
# hadolint ignore=DL3041
RUN dnf install -y --setopt=install_weak_deps=False \
        firefox \
        git \
        openssh-clients \
        curl \
        vim-enhanced \
        less \
    && rpm -q firefox git openssh-clients curl vim-enhanced less >/dev/null && \
    dnf clean all && \
    rm -rf /var/cache/* /var/log/* /home/waas_user/.viminfo

# /etc/firefox/policies works for the distro RPM too (it ships no
# distribution/policies.json that would take precedence).
# hadolint ignore=DL3022
COPY --from=firefox policies.json /etc/firefox/policies/policies.json

# gnupg2-verify ships gpgv; it is base-image content on Fedora, so only
# gnupg2 is removed afterwards.
ARG TARGETARCH
# hadolint ignore=DL3041
RUN --mount=type=bind,from=mise,source=install.sh,target=/tmp/install-mise.sh \
    dnf install -y --setopt=install_weak_deps=False gnupg2 gnupg2-verify && \
    sh /tmp/install-mise.sh && \
    dnf remove -y gnupg2 && \
    dnf clean all && \
    rm -rf /var/cache/* /var/log/* /home/waas_user/.gnupg

# Same wiring as desktop/xfce; /etc/bashrc is the Red Hat family's
# system-wide interactive bashrc (/etc/bash.bashrc is never read here).
ENV PATH=/home/waas_user/.local/share/mise/shims:/home/waas_user/.local/bin:$PATH
ENV MISE_DATA_DIR=/home/waas_user/.local/share/mise \
    MISE_CACHE_DIR=/home/waas_user/.cache/mise
# hadolint ignore=SC2016
RUN printf '\n# mise (waas): user toolchains live on the home PVC.\neval "$(mise activate bash)"\n' \
        >> /etc/bashrc

RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true

ENV WAAS_STARTUP=startxfce4

USER 1000:1000
