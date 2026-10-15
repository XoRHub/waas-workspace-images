# waas-workspace-images

The desktops and apps of WaaS Linux workspaces — everything the WaaS
catalog offers. Each image builds `FROM` a `core-*` image of
[waas-core-images](https://github.com/XoRHub/waas-core-images) (TigerVNC
Xvnc as the display server and the only remote-access listener, `tini`
+ `supervisord`, unprivileged, read-only-rootfs friendly), pinned by
digest in `images.yaml`, and is built by that repo's CI toolkit.

```
desktop/xfce         ubuntu-desktop-noble, debian-desktop-13 (XFCE + desktop baseline + mise)
desktop/xfce-fedora  fedora-desktop-43 (dnf sibling)
apps/firefox         firefox — policy-hardened Firefox kiosk
apps/chrome          chrome — Google Chrome kiosk (recipe:)
apps/libreoffice     libreoffice — LibreOffice kiosk (recipe:)
apps/devtools        devtools, devtools-dev — XFCE + VS Code + toolchain, FROM ubuntu-desktop-noble
apps/hermes-agent    hermes-agent, hermes-agent-dev — Hermes Agent dashboard kiosk
shared/              files bind-mounted into several images (Firefox apt install + policies, mise)
images.yaml          layers, release minor, pinned cores, default archs, trivy gate
catalogs/<X.Y>/      catalog.yaml per waas minor — generated and committed by release.yml
ci/                  catalog generator/validator, vendored waas schema, release helpers, tests
examples/            WorkspaceTemplate and NetworkPolicy consuming an image
HARDENING.md         app-specific gaps on top of the core's hardening contract
```

## Images

`ghcr.io/xorhub/waas-workspace-images/<variant>`, `linux/amd64` +
`linux/arm64` manifest lists (`chrome`: amd64 only, Google ships no
arm64 deb). A variant's `from:` is either a key of `images.yaml`'s
`cores:` (external parent, `tag@digest`) or another variant of this
repo (`devtools` ← `ubuntu-desktop-noble`, built one depth later).

| Session | Images |
|---|---|
| Full desktop (`WAAS_STARTUP=startxfce4`) | `ubuntu-desktop-noble`, `debian-desktop-13`, `fedora-desktop-43`, `devtools`, `devtools-dev` |
| Single-app kiosk (`WAAS_APP`) | `firefox`, `chrome`, `libreoffice`, `hermes-agent`, `hermes-agent-dev` |

The runtime contract (user, writable paths, `WAAS_*` variables, ports,
session modes, hooks) is the core's
[CONTRACT.md](https://github.com/XoRHub/waas-core-images/blob/main/CONTRACT.md):
port 5901, `WAAS_DESKTOP_PASSWORD` required, everything else optional.
`-dev` variants ship `sudo` under the reduced profile described in
`HARDENING.md`.

Run one standalone under the constraints WaaS enforces:

```shell
docker run --rm -it \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp --tmpfs /home/waas_user:mode=1777 \
  -p 5901:5901 -e WAAS_DESKTOP_PASSWORD=changeme \
  ghcr.io/xorhub/waas-workspace-images/firefox:latest
```

## Versions and tags

`images.yaml` `release: "X.Y"` is the waas minor these images target
and the only version source; releases are `X.Y.n` with `n` computed
from the existing `vX.Y.*` git tags (`X.Y.0` first). A new waas minor
is a PR changing `release:`; while waas is `0.x` only the current minor
is supported (a `release/X.Y` branch would keep patching an older one).

| Tag | Meaning |
|---|---|
| `X.Y.n` | release, immutable — what the catalog references |
| `X.Y` | latest patch of that minor |
| `latest` | latest release of the highest minor |
| `edge` | latest green `main` |
| `g<sha>` | the image set of one `main` commit (8-char short SHA) |

Releases are cosign-signed (keyless) with a CycloneDX SBOM attested to
the digest; verify as documented in the core's README with identity
`github.com/XoRHub/waas-workspace-images`.

## Catalog

`catalogs/<X.Y>/catalog.yaml` is the WaaS picker catalog for waas
`X.Y`, referencing `ghcr.io/xorhub/waas-workspace-images/<image>:X.Y.n`
by tag only. `ci/generate_catalog.py` derives it from the manifests
through the toolkit's discovery (`displayName`, `icon`, `description`,
`architectures`, `profile`, `recommended` — the platform-side doctrine
of the core's HARDENING.md, plus `env` hints from `smoke:` and the
manifest's `env:`) and `ci/validate_catalog.py` checks it against the
vendored waas schema (`ci/schema/`, `catalog-schema-sync.yml` keeps it
in sync by PR). `release.yml` commits it to `main` for every release
through the Contents API (signed commits); `main` hosts the catalogs of
every supported minor.

## Pipeline

`build.yml` runs on every PR and `main` push, on the core toolkit's
composite actions (`XoRHub/waas-core-images/.github/actions/<name>@actions/v1`,
bumped by Renovate). The mechanics — selective builds against the last
green `main` build, carry-forward of untouched variants, native
per-arch build → smoke → push, trivy scan, manifest list + sign +
attest — are the core README's § Pipeline. Specific to this repo:

- **Depths**: `layer-0` builds every variant whose parent is a core,
  `layer-1` builds `devtools` `FROM` this commit's `ubuntu-desktop-noble`
  (`layer-1` waits for `carry` and `merge-0`, either of which may be
  skipped). A deeper tree adds a `layer-N` set and raises `max-depth`.
- **What rebuilds**: a variant whose directory or `buildContexts:`
  (`shared/*`) changed, whose parent is rebuilt, or whose `cores:`
  entry changed; any other change to `images.yaml` or `.github/`
  rebuilds everything. No weekly rebuild here: the core's weekly patch
  release arrives as a Renovate PR (group `cores`) that rebuilds every
  dependent, refreshing their apt packages too.
- **Renovate**: patch/digest updates automerge once the checks pass and
  carry the `auto-release` label, so the merge triggers a patch
  release. Minor/major core bumps (a runtime-contract change) and
  toolkit majors (`actions/v2`) are reviewed by hand.

`release.yml` promotes (never rebuilds): computes `X.Y.<n+1>`, retags
the `g<sha>` images of the target `main` commit to `X.Y.n` + `X.Y` (+
`latest` from the highest minor), signs them, generates + validates +
commits the catalog, then creates the git tag and GitHub Release. Manual
dispatch targets the last green push build of `main` (a catalog commit
made with `GITHUB_TOKEN` triggers no build, so `HEAD` may carry no
images).

## Local loop

```
make build IMAGE=firefox              # any variant; args/contexts resolved from the manifests
make run   IMAGE=firefox              # VNC on localhost:15901, password devpassword
make smoke IMAGE=firefox              # the CI smoke test against the local build
make lint                             # hadolint + shellcheck + actionlint (docker)
make test                             # catalog unit tests (uv)
make catalog VERSION=0.4.0            # catalogs/0.4/catalog.yaml, schema-validated
```

The toolkit is read from a sibling checkout of `waas-core-images`
(`WAAS_CORE_IMAGES_DIR`, default `../waas-core-images`). A variant built
on a core pulls the pinned `cores:` ref; to build on a core built
locally (`make build IMAGE=core-ubuntu-noble` in that checkout):

```
CORE_REF=waas-local/core-ubuntu-noble:dev make build IMAGE=firefox
```

`devtools` always builds on the local `ubuntu-desktop-noble:dev` —
build that first. `BUILD_FLAGS` passes extra `docker build` flags
(`--network host`, `--no-cache`).

Requirements: Docker with buildx, [uv](https://docs.astral.sh/uv/)
(every Python script pins its dependencies inline, PEP 723), `jq`.
