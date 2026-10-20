# Contributing

This repo builds the desktops and apps of WaaS Linux workspaces on the
`core-*` images of `waas-core-images`, whose CI toolkit it consumes.
Read `README.md` (pipeline, catalog), `HARDENING.md` (app-specific
gaps) and the core's `CONTRACT.md` (what an image may rely on) first.

## Prerequisites

Docker with buildx, [uv](https://docs.astral.sh/uv/), `jq`, and a
sibling checkout of the toolkit:

```
git clone git@github.com:XoRHub/waas-core-images.git ../waas-core-images
```

(`WAAS_CORE_IMAGES_DIR` points elsewhere.) hadolint, shellcheck and
actionlint run through docker (`make lint`).

## Local loop

```
make -C ../waas-core-images build IMAGE=core-ubuntu-noble      # once
CORE_REF=waas-local/core-ubuntu-noble:dev make build IMAGE=firefox
CORE_REF=waas-local/core-ubuntu-noble:dev make smoke IMAGE=firefox
make lint
make test
```

`CORE_REF` is needed until the cores are published (placeholder digests
in `images.yaml`); afterwards `make build` pulls the pinned core.
`devtools` builds on the local `ubuntu-desktop-noble:dev`: build that
first. These wrap the same scripts CI runs, so "works locally" means
"works in CI".

## Adding an image

Add a directory under `apps/` (or `desktop/`) with a `manifest.yaml`:
`from:` a `cores:` key or another variant, `smoke:` (what CI probes),
`icon:` (verified dashboard-icons slug), `displayName:` when the
humanized id reads badly, and either a `Dockerfile` following the
core's `CONTRACT.md` § "Building on a core" or a `recipe:` block (one
apt package list, optional third-party repo, `app:` kiosk). Files
shared with other images go under `shared/` and in `buildContexts:`.
The pipeline discovers it; wire nothing else.

## Before opening a PR

- `make lint` and `make test` pass.
- `make build` + `make smoke` pass for every variant your change
  touches — a `shared/` change touches every image listing it, a
  `desktop/xfce` change also `devtools`.
- A new `.trivyignore` entry states the investigated reason inline.
- Anything lifting a `HARDENING.md` item is a `-dev` variant, never a
  runtime flag.

CI builds only what your PR impacts and pushes `g<sha>` tags for it;
nothing is promoted from a PR.

## Releases

`release.yml` — `Actions → release → Run workflow`. It promotes the
already-tested images of the last green `main` build to `X.Y.<n+1>`
(`X.Y` from `images.yaml` `release:`), signs them, commits
`catalogs/X.Y/catalog.yaml` to `main` and creates `vX.Y.n` + the
GitHub Release. Patch releases also happen automatically after an
automerged Renovate patch/digest PR touching image content (label
`auto-release`, which must exist in the repository). A new waas minor
is a PR bumping `release:`.

## Dependency updates

Renovate (`renovate.json`): the pinned cores (`cores:`, group
`cores`), the toolkit ref (`actions/vN`), GitHub Actions, the tool
images in the workflows/Makefile, and the annotated pins in the
Dockerfiles and `shared/` scripts (node, npm, hermes-agent, mise).
Patch and digest updates automerge once the required checks pass;
those touching `images.yaml`, `apps/`, `desktop/` or `shared/` also
trigger a patch release. Minor/major core bumps and toolkit majors
are reviewed by hand.

## Commit messages

Conventional commits, scoped: `feat(apps): …`, `fix(desktop): …`,
`ci: …`, `docs: …`, `chore(deps): …`.
