# AGENTS.md

Operating rules for AI coding agents in this repository. Read
`README.md` and `HARDENING.md` first, then the core's `CONTRACT.md`
and `HARDENING.md` (`../waas-core-images`, or on GitHub).

## What this repo is

The desktops and apps of WaaS Linux workspaces — every image the WaaS
catalog offers — built `FROM` the `core-*` images of
`XoRHub/waas-core-images` (pinned `tag@digest` in `images.yaml`
`cores:`) with that repo's CI toolkit (`.github/actions/*@actions/v1`).
Every image boots the core's Xvnc as its only remote-access listener,
runs unprivileged under `tini + supervisord`, and passes the core's
smoke test under `--read-only --cap-drop ALL --security-opt
no-new-privileges`.

## Source of truth vs. generated files

Source: `images.yaml` and one `manifest.yaml` per `desktop/*`, `apps/*`
directory (discovered automatically — adding an image is adding a
directory). Generated, gitignored, never hand-edited:
`github-matrices.json`, `*/Dockerfile.generated` (from `recipe:`
blocks, by the toolkit's compiler). Committed by CI only:
`catalogs/<X.Y>/catalog.yaml` (release.yml) and
`catalogs/<X.Y>/catalog-kasmweb.yaml` (catalog-kasmweb.yml), both
through the Contents API. The
per-image docs go to the CI job summary. There is no `version:` field
anywhere: `images.yaml` `release:` is the minor, the git tag the patch.
`release:` is maintained by `release-sync.yml`, which opens a bump PR
when waas' `appVersion` minor moves ahead of it — change it by hand only
to lead a waas release, never to follow one.

## Non-negotiable constraints

Enforced by CI (the core's smoke test, hadolint, shellcheck, trivy) and
by `HARDENING.md`. Do not weaken them without the user asking
explicitly, and flag it if a change would:

- Add a setuid/setgid binary, or run anything as root past build time.
  Final `USER` stays `1000:1000` (`waas_user`). The one exception is
  `/usr/bin/sudo` on a `-dev` variant (`profile: dev`,
  `INSTALL_SUDO=1`), which the toolkit refuses under any other name.
- Require write access outside `/home/waas_user` and `/tmp`.
- Add a second remote-desktop or shell daemon (xrdp, sshd, …) or a
  build arg that could. VNC is the only protocol the platform accepts
  for a Linux workspace (waas#117); the smoke test only ever probes VNC.
- Bake a secret into a layer — passwords arrive via runtime env.
- Install packages without `--no-install-recommends` (dnf:
  `install_weak_deps=False`), a cache purge and a suid-bit re-strip.
- Add a `recipe:` block to a directory that also has a `Dockerfile`
  (the compiler refuses it — one source of truth per image).
- Reference a core by a floating tag: `cores:` entries are `tag@digest`,
  bumped by Renovate.

## Toolkit rules

- The toolkit (build/merge/promote/scan/pipeline actions,
  `generate_pipeline.py`, `recipe_compiler.py`, the smoke test) lives
  only in `waas-core-images`. Never copy a script from it here; consume
  it as `XoRHub/waas-core-images/.github/actions/<name>@actions/v1`, or
  through `WAAS_CORE_IMAGES_DIR` locally (`Makefile`,
  `ci/generate_catalog.py`). If it lacks something this repo needs,
  change it there (a compatible change moves `actions/v1`).
- Catalog tooling (`ci/generate_catalog.py`,
  `ci/generate_kasm_catalog.py`, `ci/probe_kasm_hardening.sh`,
  `ci/validate_catalog.py`, `ci/schema/`, `ci/sync_schema.sh`,
  `ci/commit_catalog.sh`) is workspace-only and lives here. waas owns
  the schema and reads catalogs; it does not produce any — don't move a
  generator back there.
- `catalog-kasmweb.yaml` publishes upstream `docker.io/kasmweb/*`
  images, the only ones in these catalogs this repo does not build.
  Which ones is hand-curated in `ci/kasm-catalog-mapping.yaml`; its
  refresh is deliberately outside `release.yml` (it tracks upstream
  Kasm, not our releases).
- Files several images need (`shared/*`) are bind-mounted through
  buildx named contexts (`buildContexts:` in the manifest), never
  duplicated per directory.
- Icon slugs (`icon:`) must resolve at
  `https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/<slug>.svg`
  — an invalid slug fails silently at runtime.
- Comments explain a non-obvious *why*; identifiers say the what.

## Verification loop

```
make lint                                              # hadolint + shellcheck + actionlint, via docker
make test                                              # catalog unit tests
CORE_REF=waas-local/core-ubuntu-noble:dev make build IMAGE=<variant>
CORE_REF=waas-local/core-ubuntu-noble:dev make smoke IMAGE=<variant>
make catalog VERSION=<X.Y.n>                           # generate + schema-validate
make kasm-catalog                                      # kasm catalog, no Docker probe
```

`CORE_REF` builds a variant on a locally modified core instead of the
published one pinned in `images.yaml` `cores:`. Run `make test` before
declaring a change to `ci/*.py` done, `make lint` for any
Dockerfile/`.sh`/workflow change, and `make build` + `make smoke` for
every variant a change touches (a `shared/` change touches every image
listing it in `buildContexts:`, a `desktop/xfce` change also
`devtools`). Before committing a change to the pipeline (`.github/`,
`images.yaml`, `ci/`), run the `sync-docs` skill so README and script
headers stay accurate.

## Commit style

Conventional commits, scoped: `feat(apps): …`, `fix(desktop): …`,
`ci: …`, `docs: …`, `chore(deps): …`, `chore(catalog): …`.
