#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pyyaml==6.0.2",
# ]
# ///
"""Emit catalogs/<X.Y>/catalog.yaml — the WaaS picker catalog of the
images this repo publishes, for one release version X.Y.n.

Reuses the core toolkit's manifest discovery (generate_pipeline.py,
located through WAAS_CORE_IMAGES_DIR, default: the sibling checkout) so
the catalog can never drift from the build matrix. Runs after promotion
in release.yml: every entry is `<registry>/<variant>:<version>`, a tag
only — release tags are immutable by construction.

profile/recommended mirror the platform-side doctrine of the core's
HARDENING.md (RECOMMENDATION_STANDARD/RECOMMENDATION_DEV) and are
derived from the variant's `profile:`; recommended.env layers the
manifest's own `env:` hints on top of the smoke:-derived protocol ones.
"""
from __future__ import annotations

import argparse
import copy
import os
import re
import sys
from pathlib import Path

import yaml


def toolkit_dir() -> Path:
    root = Path(os.environ.get("WAAS_CORE_IMAGES_DIR")
                or Path(__file__).resolve().parents[2] / "waas-core-images")
    pipeline = root / ".github" / "actions" / "pipeline"
    if not (pipeline / "generate_pipeline.py").is_file():
        sys.exit(f"core toolkit not found at {pipeline} — clone "
                 "git@github.com:XoRHub/waas-core-images.git next to this repo "
                 "or set WAAS_CORE_IMAGES_DIR")
    return pipeline


sys.path.insert(0, str(toolkit_dir()))
import generate_pipeline as gp  # noqa: E402

API_VERSION = "waas.xorhub.io/catalog/v1"
DEFAULT_REGISTRY = "ghcr.io/" + os.environ.get(
    "GITHUB_REPOSITORY", "XoRHub/waas-workspace-images").lower()
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

# variant profile (standard/dev) -> wire Entry.profile.
PROFILE_WIRE_NAME = {"standard": "hardened", "dev": "normal"}

RECOMMENDATION_STANDARD = {
    "podSecurityContext": {
        "runAsNonRoot": True,
        "runAsUser": 1000,
        "fsGroup": 1000,
        "seccompProfile": {"type": "RuntimeDefault"},
    },
    "securityContext": {
        "allowPrivilegeEscalation": False,
        "capabilities": {"drop": ["ALL"]},
        "readOnlyRootFilesystem": True,
    },
    "volumes": [
        {"name": "tmp", "mountPath": "/tmp"},
    ],
}

# The -dev exceptions: rootfs writable, escalation allowed, and the
# runtime-default capability set kept (an ALL-dropped pod keeps sudo
# dead — a setuid binary regains capabilities only within the bounding set).
RECOMMENDATION_DEV = {
    "podSecurityContext": copy.deepcopy(RECOMMENDATION_STANDARD["podSecurityContext"]),
    "securityContext": {
        "allowPrivilegeEscalation": True,
        "readOnlyRootFilesystem": False,
    },
    "volumes": copy.deepcopy(RECOMMENDATION_STANDARD["volumes"]),
}

# smoke.<protocol> -> EnvHint(s) to surface for it.
_ENV_HINTS_BY_PROTOCOL = {
    "vnc": [
        {
            "name": "WAAS_AUDIO_ENABLED",
            "description": "Enable the unprivileged PulseAudio daemon "
                           "(native protocol on TCP 4713, consumed by "
                           "guacd's VNC client) — boolean '0'/'1'.",
            "protocols": ["vnc"],
            "default": "1",
        },
    ],
}


def env_hints(smoke: dict) -> list[dict]:
    hints: list[dict] = []
    for protocol, protocol_hints in _ENV_HINTS_BY_PROTOCOL.items():
        if smoke.get(protocol):
            hints.extend(copy.deepcopy(protocol_hints))
    return hints


def merge_hints(protocol_hints: list[dict], manifest_hints: list[dict]) -> list[dict]:
    """Manifest hints layered on the protocol ones: a same-name hint
    replaces in place (order kept), a new name is appended."""
    by_name = {h["name"]: h for h in protocol_hints}
    order = [h["name"] for h in protocol_hints]
    for h in manifest_hints:
        if h["name"] not in by_name:
            order.append(h["name"])
        by_name[h["name"]] = copy.deepcopy(h)
    return [by_name[n] for n in order]


def recommended_for(v: dict) -> dict:
    base = RECOMMENDATION_DEV if v["profile"] == "dev" else RECOMMENDATION_STANDARD
    recommended = copy.deepcopy(base)
    hints = merge_hints(env_hints(v["smoke"]), v.get("env", []))
    if hints:
        recommended["env"] = hints
    return recommended


def humanize(name: str) -> str:
    """Fallback displayName from a variant id ("ubuntu-desktop-noble" ->
    "Ubuntu Desktop Noble"). Branding an id renders badly gets an
    explicit displayName: in its manifest, never a dictionary here."""
    return " ".join(w.capitalize() for w in re.split(r"[-_]+", name) if w)


def output_path(version: str) -> Path:
    return Path("catalogs") / version.rsplit(".", 1)[0] / "catalog.yaml"


def catalog(variants: dict[str, dict], registry: str, version: str) -> dict:
    if not VERSION_RE.match(version):
        sys.exit(f"version must be X.Y.Z, got {version!r}")
    images = []
    for name, v in sorted(variants.items()):
        entry = {
            "image": f"{registry}/{name}:{version}",
            # Workspace OS family, not the build distro.
            "os": "linux",
            "app": name,
            "version": version,
        }
        if v["icon"]:
            entry["icon"] = v["icon"]
        entry["displayName"] = v["displayName"] or humanize(name)
        if v["description"]:
            entry["description"] = v["description"]
        # From the build matrix: the catalog cannot claim an arch the
        # pipeline does not build. Empty = unknown, field omitted.
        if v["archs"]:
            entry["architectures"] = [a.split("/", 1)[-1] for a in v["archs"]]
        entry["profile"] = PROFILE_WIRE_NAME[v["profile"]]
        entry["recommended"] = recommended_for(v)
        images.append(entry)
    return {"apiVersion": API_VERSION, "images": images}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="release version X.Y.Z")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=None,
                        help="default: catalogs/<X.Y>/catalog.yaml")
    args = parser.parse_args()

    root = args.root.resolve()
    cfg = gp.load_config(root)
    variants = gp.flatten_variants(gp.load_manifests(root, cfg["layers"]), cfg)
    out = catalog(variants, args.registry, args.version)

    out_path = args.output or root / output_path(args.version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(out, sort_keys=False, width=120, allow_unicode=True))
    print(f"generated {out_path} with {len(out['images'])} image(s)")


if __name__ == "__main__":
    main()
