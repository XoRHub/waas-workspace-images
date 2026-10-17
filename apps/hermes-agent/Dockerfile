# syntax=docker/dockerfile:1.25@sha256:0adf442eae370b6087e08edc7c50b552d80ddf261576f4ebd6421006b2461f12
# Hermes Agent (Nous Research) with its native desktop app (upstream
# apps/desktop, Electron, packaged at build time) as the session; it
# spawns its own `hermes serve` backend. WAAS_HERMES_DASHBOARD=1 instead
# supervises the web dashboard (entrypoint.d hook, loopback only) and
# runs a Firefox kiosk on http://127.0.0.1:9119; the VNC display stays
# the sole way in. WAAS_APP="xterm -fa monospace -fs 12 -e hermes" is the
# bare TUI, no rebuild. One variant only, -dev: see manifest.yaml.
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
ARG NODE_VERSION=22.23.1
# Build-time only: npm drives the two workspace builds below and is then
# deleted along with node_modules. Its own vendored tree is where the
# node CVEs live (picomatch/sigstore, then brace-expansion/undici/tar),
# so the image ships node without it rather than chasing npm releases.
# renovate: datasource=npm depName=npm
ARG NPM_VERSION=12.0.1
# renovate: datasource=github-tags depName=NousResearch/hermes-agent
ARG HERMES_VERSION=v2026.9.24

# The installer is fetched from the same tag as the code it installs:
# the floating https://hermes-agent.nousresearch.com/install.sh moved to
# a `pm`-based flow that older tags cannot bootstrap.
# git/ripgrep/ffmpeg: upstream's runtime deps. All three front-ends are
# prebuilt: a lazy first-run build can never work on a root-owned,
# read-only tree. The desktop app is `npm run pack` (electron-builder
# --dir, unpacked under apps/desktop/release/linux-*unpacked — the arch
# is in the directory name, hence the symlink). node-pty has no Linux
# prebuild and npm 12 blocks unreviewed install scripts (the installer's
# own npm install leaves it unbuilt), so it is rebuilt explicitly under
# a one-off project .npmrc — make/g++ come and go in this layer; without
# the .node the app silently ships with no terminal. node_modules is
# build scaffolding only (the Python server serves web's dist; ui-tui's
# entry.js is self-contained; the packaged app vendors what it needs
# under release/), so every one of them goes — the single biggest source
# of trivy findings here — except the ones inside release/.
# The build runs as root but with the core's HOME=/home/waas_user, so
# that is where the installer's ~/.hermes and the npm/uv/electron/
# node-gyp caches land: install-time state for the wrong user, shadowed
# by the home volume at runtime, half a GB of image otherwise.
# hadolint ignore=DL3008,DL3003,DL3016
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates curl git ripgrep ffmpeg xz-utils make g++ && \
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
    npm install --workspace web --workspace ui-tui --workspace apps/desktop && \
    printf 'allow-scripts=node-pty\n' > .npmrc && \
    npm rebuild node-pty && \
    rm .npmrc && \
    test -f node_modules/node-pty/build/Release/pty.node && \
    npm run build -w web && \
    npm run build -w ui-tui && \
    npm run pack -w apps/desktop && \
    test -f hermes_cli/web_dist/index.html && \
    test -f ui-tui/dist/entry.js && \
    ln -s /usr/local/lib/hermes-agent/apps/desktop/release/linux-*unpacked/Hermes \
        /usr/local/bin/hermes-desktop && \
    test -x /usr/local/bin/hermes-desktop && \
    find /usr/local/lib/hermes-agent -path /usr/local/lib/hermes-agent/apps/desktop/release -prune \
        -o -type d -name node_modules -prune -exec rm -rf {} + && \
    rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
        /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
        "${HOME}"/.npm "${HOME}"/.hermes "${HOME}"/.cache && \
    node --version && test ! -e /usr/local/bin/npm && \
    apt-get purge -y --auto-remove make g++ && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* /home/waas_user/.gnupg /tmp/*

# Firefox: the opt-in dashboard kiosk, and the system browser for links
# the desktop app opens (OAuth, docs) — Electron hands those to xdg-open,
# which resolves firefox.desktop; HttpsOnlyMode exempts 127.0.0.1.
# Electron's one shared library the core lacks is NSS (Firefox bundles
# its own); ldd asserts the packaged app resolves — Electron would only
# fail at session start otherwise.
# hadolint ignore=DL3008
RUN --mount=type=bind,from=firefox,source=install-apt.sh,target=/tmp/install-firefox.sh \
    sh /tmp/install-firefox.sh && \
    apt-get update && \
    apt-get install -y --no-install-recommends libnss3 xdg-utils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* && \
    dpkg -s curl git ripgrep ffmpeg >/dev/null && \
    ! ldd /usr/local/bin/hermes-desktop | grep 'not found'
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

# Session launcher, kiosk wrapper + dashboard entrypoint hook.
COPY rootfs/ /

# INSTALL_SUDO=1 comes from the manifest's -dev variant, the only one
# (the toolkit refuses it under any other name): reduced profile,
# HARDENING.md. The ARG stays so that guard rail keeps meaning something.
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

ENV WAAS_APP="waas-hermes-session"
ENV WAAS_HERMES_DASHBOARD=0

# Point hermes at the prebuilt bundles (what upstream's own image sets):
# without HERMES_TUI_DIR every launch re-runs `npm run build` in the
# read-only tree; without HERMES_WEB_DIST the dashboard rests on a
# staleness heuristic. Both silently fall back to npm if the paths are
# wrong — hence the two `test -f` guards above.
ENV HERMES_TUI_DIR=/usr/local/lib/hermes-agent/ui-tui
ENV HERMES_WEB_DIST=/usr/local/lib/hermes-agent/hermes_cli/web_dist
# The desktop app resolves its backend from HERMES_DESKTOP_HERMES_ROOT
# first: the system install, so it never bootstraps a second runtime
# into ~/.hermes. DISABLE_GPU: upstream's own switch for remote displays
# (Chromium's GPU compositor flickers over VNC); its heuristic only sees
# a hostname in DISPLAY, not an Xvnc behind :1.
ENV HERMES_DESKTOP_HERMES_ROOT=/usr/local/lib/hermes-agent \
    HERMES_DESKTOP_DISABLE_GPU=1

USER 1000:1000
