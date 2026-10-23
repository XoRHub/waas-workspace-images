# Vendored WaaS catalog JSON Schema

`v1.schema.json` is vendored byte-for-byte from the `waas` repo
(`shared/catalog/schema/v1.schema.json`, commit `1e7d2aca3874`) —
**`waas` is the source of truth** for the wire format (generated there
from the Go structs `catalog.File`/`catalog.Entry`, see its
`docs/image-catalog.md`). `ci/validate_catalog.py` checks every
generated catalog against it.

Which waas ref is tracked follows the branch: `main` follows waas
`main` (the next minor); a `release/X.Y` branch pins the tag `vX.Y.0`.
`ci/sync_schema.sh` is the re-sync procedure (`make schema-sync`
locally; `catalog-schema-sync.yml` runs it weekly and opens a PR — never
merged automatically, a schema change can be breaking).

If `waas` ever publishes a `v2.schema.json`, vendor it alongside and
branch `ci/validate_catalog.py` on `apiVersion`.

`Entry.kasmvnc` (`version`/`defaults`, both strings) was hand-added
ahead of waas publishing it, to unblock `ci/generate_kasm_catalog.py`'s
extraction — the next `ci/sync_schema.sh` run, once waas' authoritative
shape lands, supersedes this hand-added copy.
