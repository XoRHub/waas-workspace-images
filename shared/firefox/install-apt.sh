#!/bin/sh
# install-apt.sh — Firefox from packages.mozilla.org (Ubuntu ships it
# only as a snap, which cannot run in an unprivileged container). The
# repo is pinned by its signing-key fingerprint and an apt preference so
# nothing can shadow it. Run as root from a Dockerfile (bind-mounted from
# the `firefox` build context); the caller applies policies.json.
set -eu

# renovate: datasource=custom.mozilla-apt depName=firefox
FIREFOX_VERSION="${FIREFOX_VERSION:-*}"   # * = newest in the repo at build time
FINGERPRINT=35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3
KEYRING=/etc/apt/keyrings/packages.mozilla.org.gpg

apt-get update
apt-get install -y --no-install-recommends wget gpg
install -d -m 0755 /etc/apt/keyrings
# -4: dual-stack vendor CDNs have unreliable IPv6 routes from some runner fleets.
wget -4 --timeout=20 --tries=3 -qO- https://packages.mozilla.org/apt/repo-signing-key.gpg \
    | gpg --dearmor -o "${KEYRING}"
gpg --show-keys --with-colons "${KEYRING}" | grep -q "^fpr:.*${FINGERPRINT}"
echo "deb [signed-by=${KEYRING}] https://packages.mozilla.org/apt mozilla main" \
    > /etc/apt/sources.list.d/mozilla.list
printf 'Package: firefox*\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n' \
    > /etc/apt/preferences.d/mozilla
apt-get update
if [ "${FIREFOX_VERSION}" = "*" ]; then
    apt-get install -y --no-install-recommends firefox
else
    apt-get install -y --no-install-recommends "firefox=${FIREFOX_VERSION}"
fi
# auto + autoremove, not a blind purge: a package depending on wget/gpg
# must survive, and dpkg -s turns any collateral removal into a failure.
apt-mark auto wget gpg >/dev/null
apt-get autoremove -y --purge
dpkg -s firefox >/dev/null
apt-get clean
# gpg/wget ran as root with HOME=/home/waas_user: sweep their dotfiles.
rm -rf /var/lib/apt/lists/* /var/cache/* /var/log/* /home/waas_user/.gnupg /home/waas_user/.wget-hsts
