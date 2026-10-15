#!/bin/sh
# sync_release.sh — align images.yaml `release:` with the waas minor the
# platform actually ships, so catalogs/<X.Y>/ exists for the minor a
# chart derives its bootstrap catalog URLs from.
#
# Tracks waas' helm/waas/Chart.yaml `appVersion`, NOT its latest release
# tag: waas publishes two tag series (vX.Y.Z for the app, chart-X.Y.Z
# for the chart) and it is appVersion the chart interpolates into both
# catalog URLs — so appVersion is the number that must match, by
# definition rather than by convention. release-please bumps it on main
# in the same commit that cuts the release, so tracking it is tracking
# releases.
#
# Stages the bump and reports changed=/minor=/previous= through
# $GITHUB_OUTPUT. Never commits: bumping `release:` is a shared input
# that rebuilds every image, so release-sync.yml opens a PR.
set -eu

WAAS_MINOR=$(gh api -H "Accept: application/vnd.github.raw" \
    "repos/XoRHub/waas/contents/helm/waas/Chart.yaml?ref=main" \
    | sed -nE 's/^appVersion: *"?([0-9]+\.[0-9]+)\.[0-9]+.*$/\1/p')
[ -n "${WAAS_MINOR}" ] || {
    echo "could not read appVersion from waas main" >&2
    exit 1
}

OURS=$(sed -nE 's/^release: *"?([0-9]+\.[0-9]+)"?.*$/\1/p' images.yaml)
[ -n "${OURS}" ] || {
    echo "images.yaml: release: must be MAJOR.MINOR" >&2
    exit 1
}

report() {
    [ -n "${GITHUB_OUTPUT:-}" ] || return 0
    echo "changed=$1" >> "${GITHUB_OUTPUT}"
    [ "$1" = true ] || return 0
    echo "minor=${WAAS_MINOR}" >> "${GITHUB_OUTPUT}"
    echo "previous=${OURS}" >> "${GITHUB_OUTPUT}"
}

if [ "${OURS}" = "${WAAS_MINOR}" ]; then
    echo "images.yaml release: ${OURS} already matches waas appVersion"
    report false
    exit 0
fi

# Never walk `release:` backwards: a minor prepared here before waas
# ships it is legitimate, and the images of an older minor stay served
# for the charts still on it.
HIGHEST=$(printf '%s\n%s\n' "${OURS}" "${WAAS_MINOR}" | sort -V | tail -n1)
if [ "${HIGHEST}" = "${OURS}" ]; then
    echo "images.yaml release: ${OURS} is ahead of waas ${WAAS_MINOR} — nothing to do"
    report false
    exit 0
fi

sed -i.bak -E "s/^release: *\"?[0-9]+\.[0-9]+\"?/release: \"${WAAS_MINOR}\"/" images.yaml
rm -f images.yaml.bak

echo "images.yaml release: ${OURS} -> ${WAAS_MINOR}"
report true
