#!/bin/sh
# sync_schema.sh — re-sync the vendored WaaS catalog schema
# (ci/schema/v1.schema.json) from its source of truth in XoRHub/waas.
# The waas ref follows the branch: `main` tracks waas main (the next
# minor), `release/X.Y` pins the tag vX.Y.0. Stages the change and
# records the waas commit in ci/schema/README.md; reports changed= and
# waas_sha= through $GITHUB_OUTPUT. Never commits: a schema change can
# be breaking, so catalog-schema-sync.yml opens a PR for review.
set -eu

SCHEMA_PATH="shared/catalog/schema/v1.schema.json"
LOCAL_SCHEMA="ci/schema/v1.schema.json"
LOCAL_README="ci/schema/README.md"

BRANCH="${GITHUB_REF_NAME:-$(git rev-parse --abbrev-ref HEAD)}"
case "${BRANCH}" in
    release/*) WAAS_REF="v${BRANCH#release/}.0" ;;
    *) WAAS_REF=main ;;
esac

# SHA first, then the file at that SHA: a push landing in between would
# make the recorded commit describe other bytes than the vendored ones.
WAAS_SHA=$(gh api "repos/XoRHub/waas/commits/${WAAS_REF}" --jq .sha)
TMP_SCHEMA=$(mktemp)
trap 'rm -f "${TMP_SCHEMA}"' EXIT
gh api -H "Accept: application/vnd.github.raw" \
    "repos/XoRHub/waas/contents/${SCHEMA_PATH}?ref=${WAAS_SHA}" > "${TMP_SCHEMA}"

if diff -q "${TMP_SCHEMA}" "${LOCAL_SCHEMA}" >/dev/null 2>&1; then
    echo "${LOCAL_SCHEMA} already matches waas ${WAAS_REF} @ ${WAAS_SHA}"
    [ -n "${GITHUB_OUTPUT:-}" ] && echo "changed=false" >> "${GITHUB_OUTPUT}"
    exit 0
fi

cp "${TMP_SCHEMA}" "${LOCAL_SCHEMA}"
sed -i.bak -E "s/(v1\.schema\.json\`, commit \`)[0-9a-f]{7,40}/\1$(echo "${WAAS_SHA}" | cut -c1-12)/" "${LOCAL_README}"
rm -f "${LOCAL_README}.bak"

echo "${LOCAL_SCHEMA} updated to waas ${WAAS_REF} @ ${WAAS_SHA}"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "changed=true" >> "${GITHUB_OUTPUT}"
    echo "waas_sha=${WAAS_SHA}" >> "${GITHUB_OUTPUT}"
fi
