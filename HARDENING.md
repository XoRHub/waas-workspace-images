# Hardening — app-specific gaps

The hardening contract (non-root, no setuid, read-only rootfs, VNC as
the only listener, VncAuth, unprivileged audio, the pod
`securityContext` to apply, the threat model) is the core's
[HARDENING.md](https://github.com/XoRHub/waas-core-images/blob/main/HARDENING.md);
its smoke test gates every image built here on every build. This file
lists only what the desktops and apps add or lift on top of it.

## Browser inner sandboxes (Firefox, Chrome, VS Code)

Unprivileged user namespaces are blocked by the pod's seccomp/caps
profile, so the *internal* process sandbox of Chromium-based software
cannot start: Chrome and VS Code run with `--no-sandbox`
(`apps/chrome` recipe, `apps/devtools` desktop entry), Firefox degrades
its own (`CanCreateUserNamespace: EPERM`). Deliberate: the pod
(non-root, no caps, read-only, seccomp, NetworkPolicy) is the sandbox
boundary; granting `CAP_SYS_ADMIN` to restore the inner one would weaken
the outer one. Google's deb ships a setuid `chrome-sandbox` helper — the
recipe template's suid strip removes it.

Firefox ships with locked enterprise policies (`shared/firefox/policies.json`:
no telemetry, no extensions, HTTPS-only, tracking protection, no
password manager) on every image that carries it — the kiosk, the
desktops, hermes-agent.

## Reduced profile: `-dev` variants

`devtools-dev` and `hermes-agent-dev` ship exactly `/usr/bin/sudo`
setuid (NOPASSWD for UID 1000) so users can `sudo apt install`
in-session. This is a build-time variant with a distinct tag, never a
runtime flag: the core's HARDENING.md § "Reduced profile" lists the
items lifted (`readOnlyRootFilesystem: false`,
`allowPrivilegeEscalation: true`, runtime-default capabilities instead
of `drop: [ALL]`) and the guard rails (the toolkit refuses
`INSTALL_SUDO=1` without the `-dev` suffix and `profile: dev`, the smoke
test asserts the suid set and runs `sudo -n true`, the image bakes
`WAAS_PROFILE=dev`). In-session installs land in the container layer
and die with the pod; only `/home/waas_user` survives.

`ci/generate_catalog.py`'s `RECOMMENDATION_DEV` derives the catalog's
`recommended` block (`profile: normal`) from those exceptions — keep
both in sync when editing either. The platform gates `-dev` entries by
`allowedGroups`.

### Durable tooling without the reduced profile

The desktop layer (`desktop/xfce`, `desktop/xfce-fedora`, hence
`devtools`) and `hermes-agent` ship **mise** (`shared/mise`): toolchains
install under `~/.local/share/mise`, on the home PVC, so they survive
restarts, and mise writes nothing outside `$HOME` and `/tmp` — it works
on the hardened variants. A user needing a language runtime or a CLI
tool does not need `-dev`. What it cannot provide is system libraries
(`.so`, codecs, apt maintainer scripts): that is still `sudo apt
install` on a `-dev` image. Tools installed via mise live on the PVC,
outside the trivy gate and the SBOM by construction; mise's shims sit
first on `PATH`, so a user-installed `python3` shadows the image's.

## hermes-agent

- The web dashboard (`hermes dashboard`, supervised by
  `rootfs/etc/waas/entrypoint.d/60-hermes-dashboard.sh`) binds
  `127.0.0.1:9119` only: reachable solely through the password-gated
  VNC display. `WAAS_HERMES_DASHBOARD=0` starts no server.
- Keys, sessions and memories live in `~/.hermes` on the home PVC; the
  install tree under `/usr/local` is root-owned and read-only, both
  front-ends are prebuilt at image build time.
- `apps/hermes-agent/.trivyignore` accepts six real CVEs in Python
  dependencies resolved by the upstream installer (mcp, python-multipart,
  starlette): the image tracks upstream's tested dependency set, the fix
  arrives with a Hermes release. Re-evaluate on every `HERMES_VERSION`
  bump. Every other `.trivyignore` entry in this repo is an investigated
  false positive documented inline.

## Known, accepted gaps

- `apps/chrome` and `apps/libreoffice` (`recipe:`) install their
  packages unpinned from the archive at every rebuild; a pin needing
  Renovate tracking is the hand-written Dockerfile case.
- `FIREFOX_VERSION=*` on the apt images: newest in the Mozilla repo at
  build time, refreshed by every rebuild (core bump or `no_cache`).
