#!/bin/sh
# install.sh — install mise (user-level toolchain manager) into
# /usr/local/bin from the signed GitHub release. Run as root from a
# Dockerfile (bind-mounted from the `mise` build context) with curl, gpg,
# gpgv and tar available; the caller installs and purges those.
#
# The signing-key fingerprint is pinned rather than a per-arch tarball
# digest: a literal SHA256 would need one value per arch that Renovate
# cannot recompute on a version bump.
set -eu

# renovate: datasource=github-releases depName=jdx/mise
MISE_VERSION=v2026.10.18
FINGERPRINT=24853EC9F655CE80B48E6C3A8B81C9D17413A06D

case "${TARGETARCH:?}" in
    amd64) MISE_ARCH=x64 ;;
    arm64) MISE_ARCH=arm64 ;;
    *) echo "unsupported TARGETARCH ${TARGETARCH}" >&2; exit 1 ;;
esac
TARBALL="mise-${MISE_VERSION}-linux-${MISE_ARCH}.tar.gz"
RELEASE="https://github.com/jdx/mise/releases/download/${MISE_VERSION}"
# Absolute: gpgv resolves a relative --keyring against ~/.gnupg, not cwd.
KEYRING=/tmp/mise-release-key.gpg

cd /tmp
# Kept under its release filename: SHASUMS256.asc lists "./<tarball>"
# and `sha256sum -c` resolves that relative to cwd.
curl -fsSL -4 --max-time 60 "${RELEASE}/${TARBALL}" -o "${TARBALL}"
curl -fsSL -4 --max-time 20 "${RELEASE}/SHASUMS256.asc" -o SHASUMS256.asc
curl -fsSL -4 --max-time 20 https://mise.jdx.dev/gpg-key.pub | gpg --dearmor -o "${KEYRING}"
gpg --show-keys --with-colons "${KEYRING}" | grep -q "^fpr:.*${FINGERPRINT}"
gpgv --keyring "${KEYRING}" SHASUMS256.asc
grep "  ./${TARBALL}\$" SHASUMS256.asc | sed 's|\./||' | sha256sum -c -
tar -xzf "${TARBALL}" -C /usr/local/bin --strip-components=2 mise/bin/mise
rm -f "${TARBALL}" SHASUMS256.asc "${KEYRING}"
test "$(mise --version | cut -d' ' -f1)" = "${MISE_VERSION#v}"
# `mise --version` ran as root with HOME=/home/waas_user and seeded
# root-owned state there; a docker named volume would copy it in.
rm -rf /home/waas_user/.cache /home/waas_user/.local
