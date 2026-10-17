# syntax=docker/dockerfile:1.28@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b
# XFCE work desktop with VS Code and a build toolchain, on top of
# ubuntu-desktop-noble (which brings Firefox, git, ssh client, mise).
# Hand-written: third-party repo + composed toolchain + the INSTALL_SUDO
# dev variant exceed the recipe: case.
ARG BASE_IMAGE
# hadolint ignore=DL3006
FROM ${BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0

# packages.microsoft.com is unreachable from some runner fleets even over
# IPv4: fetch the signing key live, fall back to the vendored copy, and
# verify the fingerprint either way.
COPY microsoft-signing-key.asc /tmp/microsoft-signing-key.vendored.asc

# python3 stays although mise could supply one: VS Code's Python
# extension expects a system interpreter. The desktop baseline is
# asserted so a reparent cannot silently ship a dev image without it.
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends wget gpg && \
    install -d -m 0755 /etc/apt/keyrings && \
    ( wget -4 --timeout=20 --tries=3 -qO- https://packages.microsoft.com/keys/microsoft.asc \
        > /tmp/microsoft-signing-key.fetched.asc || true ) && \
    if [ -s /tmp/microsoft-signing-key.fetched.asc ]; then \
        cp /tmp/microsoft-signing-key.fetched.asc /tmp/microsoft-signing-key.asc; \
    else \
        echo "WARN: live fetch of the packages.microsoft.com key failed, using the vendored copy" >&2; \
        cp /tmp/microsoft-signing-key.vendored.asc /tmp/microsoft-signing-key.asc; \
    fi && \
    gpg --dearmor -o /etc/apt/keyrings/packages.microsoft.com.gpg /tmp/microsoft-signing-key.asc && \
    rm -f /tmp/microsoft-signing-key.*.asc /tmp/microsoft-signing-key.asc && \
    gpg --show-keys --with-colons /etc/apt/keyrings/packages.microsoft.com.gpg \
        | grep -q "^fpr:.*BC528686B50D79E339D3721CEB3E94ADBE1229CF" && \
    echo "deb [signed-by=/etc/apt/keyrings/packages.microsoft.com.gpg] https://packages.microsoft.com/repos/code stable main" \
        > /etc/apt/sources.list.d/vscode.list && \
    printf 'Package: code*\nPin: origin packages.microsoft.com\nPin-Priority: 1000\n' \
        > /etc/apt/preferences.d/vscode && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        code \
        build-essential \
        python3 \
        python3-venv \
        jq \
        tmux \
    && apt-mark auto wget gpg >/dev/null && \
    apt-get autoremove -y --purge && \
    dpkg -s code build-essential python3 python3-venv jq tmux >/dev/null && \
    dpkg -s git curl vim less openssh-client firefox >/dev/null && \
    command -v mise >/dev/null && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* \
        /home/waas_user/.gnupg /home/waas_user/.wget-hsts

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

# The pod seccomp profile blocks the user namespaces VS Code's Chromium
# sandbox wants (same as Firefox, HARDENING.md): launch with --no-sandbox.
RUN install -d -m 0755 /usr/share/applications && \
    printf '[Desktop Entry]\nType=Application\nName=Visual Studio Code\nComment=Code Editing. Redefined.\nExec=/usr/bin/code --no-sandbox %%F\nIcon=vscode\nCategories=Development;IDE;\nMimeType=text/plain;inode/directory;\n' \
        > /usr/share/applications/code.desktop

USER 1000:1000
