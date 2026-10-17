# syntax=docker/dockerfile:1.28@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b
# Hermes Agent (Nous Research) with its web dashboard as the kiosk
# session: Firefox on http://127.0.0.1:9119 (the Chat tab embeds the
# TUI). The dashboard is supervised by an entrypoint.d hook, loopback
# only; the VNC display stays the sole way in. WAAS_HERMES_DASHBOARD=0
# (or WAAS_APP="xterm -fa monospace -fs 12 -e hermes") falls back to the
# bare TUI, no rebuild.
#
# Upstream's installer in its root FHS mode: code in
# /usr/local/lib/hermes-agent, launcher /usr/local/bin/hermes, uv-managed
# Python under /usr/local/share. Per-user state self-bootstraps in
# ~/.hermes, on the home volume. Node is preinstalled system-wide: the
# installer otherwise drops its own copy into the build user's home,
# which the runtime home mount would shadow.
ARG BASE_IMAGE
# hadolint ignore=DL3006
FROM ${BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0

ARG TARGETARCH
# renovate: datasource=node-version depName=node
ARG NODE_VERSION=22.23.3
# Build-time only: npm drives the two workspace builds below and is then
# deleted along with node_modules. Its own vendored tree is where the
# node CVEs live (picomatch/sigstore, then brace-expansion/undici/tar),
# so the image ships node without it rather than chasing npm releases.
# renovate: datasource=npm depName=npm
ARG NPM_VERSION=12.2.0
# renovate: datasource=github-tags depName=NousResearch/hermes-agent
ARG HERMES_VERSION=v2026.9.24

# The installer is fetched from the same tag as the code it installs:
# the floating https://hermes-agent.nousresearch.com/install.sh moved to
# a `pm`-based flow that older tags cannot bootstrap.
# git/ripgrep/ffmpeg: upstream's runtime deps. Both front-ends are
# prebuilt: a lazy first-run build can never work on a root-owned,
# read-only tree. node_modules is build scaffolding only (the Python
# server serves web's dist; ui-tui's entry.js is self-contained), so
# every one of them goes — including apps/desktop's, which the installer
# populates for an Electron app this image never launches and which is
# the single biggest source of trivy findings here.
# /root/.hermes is install-time state for the wrong user.
# hadolint ignore=DL3008,DL3003,DL3016
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates curl git ripgrep ffmpeg xz-utils && \
    case "${TARGETARCH}" in \
        amd64) NODE_ARCH=x64 ;; \
        arm64) NODE_ARCH=arm64 ;; \
        *) echo "unsupported TARGETARCH ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz" \
        | tar -xJ -C /usr/local --strip-components=1 --no-same-owner && \
    node --version && \
    npm install -g "npm@${NPM_VERSION}" && \
    npm --version && \
    curl -fsSL "https://raw.githubusercontent.com/NousResearch/hermes-agent/${HERMES_VERSION}/scripts/install.sh" \
        | bash -s -- --branch "${HERMES_VERSION}" --skip-setup --non-interactive --skip-browser && \
    /usr/local/bin/hermes --version && \
    cd /usr/local/lib/hermes-agent && \
    npm install --workspace web --workspace ui-tui && \
    npm run build -w web && \
    npm run build -w ui-tui && \
    test -f hermes_cli/web_dist/index.html && \
    test -f ui-tui/dist/entry.js && \
    find /usr/local/lib/hermes-agent -type d -name node_modules \
        -prune -exec rm -rf {} + && \
    rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
        /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
        /root/.npm /root/.hermes && \
    node --version && test ! -e /usr/local/bin/npm && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* /home/waas_user/.gnupg /tmp/*

# Firefox for the dashboard kiosk; HttpsOnlyMode exempts 127.0.0.1.
RUN --mount=type=bind,from=firefox,source=install-apt.sh,target=/tmp/install-firefox.sh \
    sh /tmp/install-firefox.sh && \
    dpkg -s curl git ripgrep ffmpeg >/dev/null
# hadolint ignore=DL3022
COPY --from=firefox policies.json /etc/firefox/policies/policies.json

# mise on the hardened variant too: it writes only under $HOME and /tmp.
# hadolint ignore=DL3008
RUN --mount=type=bind,from=mise,source=install.sh,target=/tmp/install-mise.sh \
    apt-get update && \
    apt-get install -y --no-install-recommends gpg && \
    sh /tmp/install-mise.sh && \
    apt-get purge -y --auto-remove gpg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* /home/waas_user/.gnupg

# Same wiring as desktop/xfce: shims for non-interactive contexts (the
# agent's subprocesses), activate for interactive shells.
ENV PATH=/home/waas_user/.local/share/mise/shims:/home/waas_user/.local/bin:$PATH
ENV MISE_DATA_DIR=/home/waas_user/.local/share/mise \
    MISE_CACHE_DIR=/home/waas_user/.cache/mise
# hadolint ignore=SC2016
RUN printf '\n# mise (waas): user toolchains live on the home PVC.\neval "$(mise activate bash)"\n' \
        >> /etc/bash.bashrc

# Kiosk wrapper + dashboard entrypoint hook.
COPY rootfs/ /

# INSTALL_SUDO=1 only ever comes from the -dev variant (the toolkit
# refuses it elsewhere): reduced profile, HARDENING.md.
ARG INSTALL_SUDO=0
# hadolint ignore=DL3008
RUN if [ "${INSTALL_SUDO}" = "1" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends sudo && \
        printf '#1000 ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/waas-dev && \
        chmod 0440 /etc/sudoers.d/waas-dev && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/*; \
    fi

RUN if [ "${INSTALL_SUDO}" = "1" ]; then \
        find / -xdev -perm /6000 -type f ! -path /usr/bin/sudo -exec chmod a-s {} + 2>/dev/null || true; \
    else \
        find / -xdev -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true; \
    fi

ARG WAAS_PROFILE=standard
ENV WAAS_PROFILE=${WAAS_PROFILE}

ENV WAAS_APP="waas-hermes-kiosk"
ENV WAAS_HERMES_DASHBOARD=1

# Point hermes at the prebuilt bundles (what upstream's own image sets):
# without HERMES_TUI_DIR every launch re-runs `npm run build` in the
# read-only tree; without HERMES_WEB_DIST the dashboard rests on a
# staleness heuristic. Both silently fall back to npm if the paths are
# wrong — hence the two `test -f` guards above.
ENV HERMES_TUI_DIR=/usr/local/lib/hermes-agent/ui-tui
ENV HERMES_WEB_DIST=/usr/local/lib/hermes-agent/hermes_cli/web_dist

USER 1000:1000
