#!/bin/sh
# commit_catalog.sh — commit FILE to main through the GitHub Contents
# API rather than `git push`: main requires verified signatures, and a
# plain github-actions[bot] commit is never marked Verified (GH013),
# while commits the API creates are. No-op if FILE is byte-identical to
# main's copy. A commit made with GITHUB_TOKEN triggers no workflow, so
# the resulting commit carries no g<sha> images (release.yml targets
# the last green build instead).
set -eu

FILE="${1:?usage: commit_catalog.sh <file> [message]}"
MESSAGE="${2:-chore(catalog): publish ${FILE}}"
: "${GITHUB_REPOSITORY:?}"

LOCAL_SHA=$(git hash-object "${FILE}")
REMOTE_SHA=$(gh api "repos/${GITHUB_REPOSITORY}/contents/${FILE}?ref=main" --jq .sha 2>/dev/null || true)

# On a 404 — the first publish of a minor — `gh api` writes the raw error
# body to stdout instead of applying --jq, so REMOTE_SHA would hold
# `{"message":"Not Found",...}`: non-empty, and with a space in it, which
# word-splits SHA_FLAG below into a second positional argument ("accepts
# 1 arg(s), received 2"). Only a real blob sha counts.
case "${REMOTE_SHA}" in
    "" | *[!0-9a-f]*) REMOTE_SHA="" ;;
esac

if [ "${LOCAL_SHA}" = "${REMOTE_SHA}" ]; then
    echo "${FILE} unchanged, nothing to commit"
    exit 0
fi

SHA_FLAG=""
[ -n "${REMOTE_SHA}" ] && SHA_FLAG="-f sha=${REMOTE_SHA}"

# shellcheck disable=SC2086
gh api --method PUT "repos/${GITHUB_REPOSITORY}/contents/${FILE}" \
    -f message="${MESSAGE}" \
    -f content="$(base64 -w0 "${FILE}")" \
    -f branch=main \
    ${SHA_FLAG}
echo "committed ${FILE} to main via the Contents API"
