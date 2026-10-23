#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml==6.0.2"]
# ///
"""Emit the kasmweb picker catalog (catalogs/<X.Y>/catalog-kasmweb.yaml):
the upstream docker.io/kasmweb/* images in the wire format waas owns
(its shared/catalog, vendored here as ci/schema/v1.schema.json — see
waas' docs/image-catalog.md § Wire format and schema).

These are the only images in this repo's catalogs that it does not
build. They live here anyway because this is the repo that produces
catalogs: X.Y is the waas minor from images.yaml `release:`, the same
key catalog.yaml uses, and the publishing plumbing (validation against
the vendored schema, the Contents-API commit) is already here.

ci/kasm-catalog-mapping.yaml stays hand-curated for which image/app
name/icon/displayName/description to publish (description optional and
never regenerated away — see catalog()); this script resolves the
newest published X.Y.Z release tag per image from the public Docker
Hub API (no auth needed) and derives `architectures` (Hub's per-tag
manifest-list data — hand-curating it drifted stale, see
hub_architectures()), `profile`/`recommended` (probe_hardening(), only
with --probe-hardening: it actually pulls+runs the resolved image under
the hardened Docker flags of waas-core-images' smoke test, since
kasmweb images carry no HARDENING.md doctrine to derive a profile from
statically) and `kasmvnc` (extract_kasmvnc(), same --probe-hardening
opt-in, reusing that pull: the KasmVNC version and the verbatim
/usr/share/kasmvnc/kasmvnc_defaults.yaml, a display/prefill hint for
waas' schema-driven KasmVNC admin form — waas never reads it at
reconcile). Best effort by design throughout: any Hub/Docker failure
falls back to omitting the field (or, for version resolution, the
mapping's knownVersion) rather than failing — this catalog must never
block anything. An unchanged image:version carries its previous
profile/recommended/kasmvnc forward instead of being re-run.

Two CLI modes, both usable from CI or by hand:

  - No positional arg (`make kasm-catalog`, the scheduled workflow):
    regenerate the WHOLE catalog from every image in the mapping.
  - `generate_kasm_catalog.py <name>` (e.g. `vs-code` — never a full
    ref, the registry is always docker.io/kasmweb/): resolve/probe just
    THAT image and upsert it into the existing --output in place. If
    `<name>` isn't in the mapping yet, a minimal entry
    (name/app/knownVersion) is appended to it as plain text — never a
    yaml round-trip of the whole file, which would strip its header
    comments; icon/displayName are left for a human to fill in.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

import yaml

HERE = Path(__file__).resolve().parent
MAPPING_PATH = HERE / "kasm-catalog-mapping.yaml"
PROBE_SCRIPT = HERE / "probe_kasm_hardening.sh"
API_VERSION = "waas.xorhub.io/catalog/v1"
# Plain X.Y.Z releases only: kasmweb also pushes develop*/-rolling/
# arch-prefixed tags, and Hub's last-updated ordering surfaces those
# first — "most recently pushed" is NOT "newest release".
RELEASE_TAG = re.compile(r"^\d+\.\d+\.\d+$")
PAGE_URL = ("https://hub.docker.com/v2/repositories/kasmweb/{name}/tags"
            "?page_size=100&page={page}")
TAG_URL = "https://hub.docker.com/v2/repositories/kasmweb/{name}/tags/{version}"
MAX_PAGES = 5  # ~500 tags, comfortable headroom over kasm's tag volume
TIMEOUT = 15
PROBE_TIMEOUT = 180  # probe_kasm_hardening.sh pulls full desktop images
ARCH_ENUM = ("amd64", "arm64")  # shared/catalog/schema/v1.schema.json Entry.architectures
KASMVNC_DEFAULTS_PATH = "/usr/share/kasmvnc/kasmvnc_defaults.yaml"
KASMVNC_MARKER = "---KASMVNC-DEFAULTS---"  # splits the version banner from the file in one docker run's stdout
KASMVNC_VERSION_RE = re.compile(r"KasmVNC (\d+\.\d+\.\d+)")  # "1.5.1" out of "1.5.1.<git-sha> - built ..."
KASMVNC_TIMEOUT = 30  # the image is already pulled by probe_hardening(); just a quick `docker run`

# Mirrors waas-core-images HARDENING.md § "To apply on the platform
# side" — the pod securityContext a probe-confirmed hardened image
# tolerates (docs/image-catalog.md § Deployment recommendations).
RECOMMENDATION_HARDENED = {
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

# podSecurityContext-only block for an image whose UID-1000 baseline was
# confirmed live but whose readOnlyRootFilesystem/cap-drop ALL tolerance
# was NOT (profile: "normal") — "hardening wasn't verified", not a
# claim about any exception.
KASM_RECOMMENDATION_NORMAL = {
    "podSecurityContext": copy.deepcopy(RECOMMENDATION_HARDENED["podSecurityContext"]),
}


def latest_release_tag(name: str) -> str | None:
    releases: list[tuple[int, ...]] = []
    for page in range(1, MAX_PAGES + 1):
        url = PAGE_URL.format(name=name, page=page)
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            data = json.load(resp)
        releases += [
            tuple(int(x) for x in t["name"].split("."))
            for t in data.get("results", [])
            if RELEASE_TAG.match(t["name"])
        ]
        if not data.get("next"):
            break
    if not releases:
        return None
    return ".".join(str(x) for x in max(releases))


def hub_architectures(name: str, version: str) -> list[str] | None:
    """Docker Hub's single-tag endpoint images[].architecture list for
    name:version. A hand-curated `architectures:` in the mapping used to
    claim amd64-only while kasmweb's plain X.Y.Z tags are multi-arch
    manifest lists (verified live on 1.19.0) — hence derived, never
    curated. None on any failure or when nothing in the schema's enum
    is present, same best-effort contract as latest_release_tag()."""
    url = TAG_URL.format(name=name, version=version)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None
    archs = sorted({
        img["architecture"] for img in data.get("images", [])
        if img.get("architecture") in ARCH_ENUM
    })
    return archs or None


def probe_hardening(ref: str) -> str | None:
    """Best-effort shell-out to probe_kasm_hardening.sh, which pulls+runs
    `ref` under increasingly strict Docker flags. Returns "hardened"/
    "normal"/None (inconclusive, timed out, errored) — never raises."""
    try:
        result = subprocess.run(
            ["sh", str(PROBE_SCRIPT), ref],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT)
    except Exception as exc:  # noqa: BLE001 — best effort, never fatal
        print(f"{ref}: hardening probe failed: {exc}", file=sys.stderr)
        return None
    outcome = result.stdout.strip()
    return outcome if outcome in ("hardened", "normal") else None


def extract_kasmvnc(ref: str) -> dict | None:
    """Best-effort shell-out: one `docker run --rm --entrypoint sh <ref> -c`
    gets both the `Xvnc -version` banner and the verbatim
    kasmvnc_defaults.yaml — the image is already pulled by
    probe_hardening() by the time this runs, so this never pulls again.
    Returns {"version", "defaults"} for the waas admin UI's schema-driven
    KasmVNC form (display/prefill hint only, waas never reads it at
    reconcile) or None on any failure (bad ref, missing binary/file,
    timeout) — never raises."""
    cmd = (f"Xvnc -version 2>&1; echo '{KASMVNC_MARKER}'; "
           f"cat {KASMVNC_DEFAULTS_PATH}")
    try:
        result = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "sh", ref, "-c", cmd],
            capture_output=True, text=True, timeout=KASMVNC_TIMEOUT)
    except Exception as exc:  # noqa: BLE001 — best effort, never fatal
        print(f"{ref}: kasmvnc defaults extraction failed: {exc}", file=sys.stderr)
        return None
    if KASMVNC_MARKER not in result.stdout:
        print(f"{ref}: kasmvnc defaults extraction failed: "
              f"docker run produced no usable output", file=sys.stderr)
        return None
    banner, _, defaults = result.stdout.partition(KASMVNC_MARKER)
    defaults = defaults.lstrip("\n")
    match = KASMVNC_VERSION_RE.search(banner)
    if not match or not defaults.strip():
        print(f"{ref}: kasmvnc defaults extraction failed: "
              f"unparsable version or empty defaults file", file=sys.stderr)
        return None
    return {"version": match.group(1), "defaults": defaults}


def recommended_for(profile: str) -> dict:
    if profile == "hardened":
        return copy.deepcopy(RECOMMENDATION_HARDENED)
    return copy.deepcopy(KASM_RECOMMENDATION_NORMAL)


def load_previous(path: Path) -> dict[str, dict]:
    """Best-effort read of the catalog last written at `path`, keyed by
    app name — the source of preserved descriptions and of hardening
    verdicts reused for an unchanged image:version. Anything wrong with
    the file just means no fallback, never a hard error."""
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return {}
    return {img["app"]: img for img in data.get("images", []) if "app" in img}


def catalog(
    mapping: dict,
    *,
    probe: Callable[[str], str | None] = lambda ref: None,
    extract_kasmvnc: Callable[[str], dict | None] = lambda ref: None,
    previous: dict[str, dict] | None = None,
) -> dict:
    previous = previous or {}
    images = []
    for img in mapping["images"]:
        name = img["name"]
        try:
            version = latest_release_tag(name)
            if version is None:
                print(f"kasmweb/{name}: no X.Y.Z release tag on Docker Hub",
                      file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — best effort, never fatal
            print(f"kasmweb/{name}: Docker Hub lookup failed: {exc}",
                  file=sys.stderr)
            version = None
        if version is None:
            version = str(img["knownVersion"])
            print(f"kasmweb/{name}: falling back to knownVersion {version}",
                  file=sys.stderr)
        ref = f"docker.io/kasmweb/{name}:{version}"
        entry = {
            "image": ref,
            "os": "linux",
            "app": img["app"],
            "version": version,
        }
        if img.get("icon"):
            entry["icon"] = img["icon"]
        if img.get("displayName"):
            entry["displayName"] = img["displayName"]
        # A description the previous catalog carried survives a mapping
        # that omits it — a value that once existed is never silently
        # erased. Absent from both -> field omitted.
        fallback = previous.get(img["app"])
        description = img.get("description") or (fallback or {}).get("description")
        if description:
            entry["description"] = description
        try:
            archs = hub_architectures(name, version)
        except Exception as exc:  # noqa: BLE001 — best effort, never fatal
            print(f"kasmweb/{name}: architecture lookup failed: {exc}",
                  file=sys.stderr)
            archs = None
        if archs:
            entry["architectures"] = archs
        # The probe pulls+runs a full desktop image: an unchanged
        # image:version keeps its published verdict (and kasmvnc
        # extraction) instead of being re-run every time.
        if fallback and fallback.get("image") == ref and fallback.get("profile"):
            entry["profile"] = fallback["profile"]
            if fallback.get("recommended"):
                entry["recommended"] = copy.deepcopy(fallback["recommended"])
            if fallback.get("kasmvnc"):
                entry["kasmvnc"] = copy.deepcopy(fallback["kasmvnc"])
        else:
            outcome = probe(ref)
            if outcome:
                entry["profile"] = outcome
                entry["recommended"] = recommended_for(outcome)
            kasmvnc = extract_kasmvnc(ref)
            if kasmvnc:
                entry["kasmvnc"] = kasmvnc
        images.append(entry)
    return {"apiVersion": API_VERSION, "images": images}


class _KasmCatalogDumper(yaml.SafeDumper):
    """safe_dump, plus block-literal (`|`) style for any multiline string
    (currently just kasmvnc.defaults) so the committed catalog keeps it
    human-readable instead of one giant quoted/escaped line."""


def _represent_str(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_KasmCatalogDumper.add_representer(str, _represent_str)


def dump_catalog(data: dict) -> str:
    return yaml.dump(data, Dumper=_KasmCatalogDumper, sort_keys=False, width=120,
                      allow_unicode=True)


def append_mapping_entry(mapping_path: Path, name: str, version: str) -> None:
    """Plain-text append, never a yaml round-trip of the whole file
    (that would strip its header comments). knownVersion is the version
    resolved live right now, so the entry has an offline fallback from
    the moment it's added."""
    block = (
        f"\n  - name: {name}            # docker.io/kasmweb/{name}\n"
        f"    app: {name}\n"
        f"    knownVersion: \"{version}\"\n"
    )
    with mapping_path.open("a") as f:
        f.write(block)


def resolve_mapping_entry(mapping: dict, mapping_path: Path, name: str) -> dict:
    """Find `name`'s mapping entry, or resolve it live and append a
    minimal one. Unlike catalog()'s per-run best effort, a manual add
    with no resolvable release has nothing sensible to write and fails
    loudly."""
    for img in mapping["images"]:
        if img["name"] == name:
            return img
    version = latest_release_tag(name)
    if version is None:
        sys.exit(f"kasmweb/{name}: no X.Y.Z release tag found on Docker Hub — "
                 "not a known kasmweb image name, or Hub is unreachable")
    append_mapping_entry(mapping_path, name, version)
    print(f"kasmweb/{name}: new image, appended to {mapping_path} with "
          f"knownVersion {version} (edit icon/displayName there by hand "
          "if wanted)", file=sys.stderr)
    return {"name": name, "app": name, "knownVersion": version}


def upsert_entry(out_path: Path, entry: dict) -> dict:
    """Merge `entry` into the catalog at out_path: same app -> replaced
    in place, new app -> appended, every other entry untouched."""
    if out_path.exists():
        try:
            data = yaml.safe_load(out_path.read_text()) or {}
        except yaml.YAMLError:
            data = {}
    else:
        data = {}
    data.setdefault("apiVersion", API_VERSION)
    images = data.setdefault("images", [])
    for i, existing in enumerate(images):
        if existing.get("app") == entry["app"]:
            images[i] = entry
            break
    else:
        images.append(entry)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "image", nargs="?",
        help="short kasmweb image name (e.g. 'vs-code') to resolve/probe "
             "and upsert in isolation instead of regenerating the whole "
             "catalog; added to --mapping automatically if it isn't there yet")
    parser.add_argument("--mapping", default=str(MAPPING_PATH))
    parser.add_argument(
        "--output", required=True,
        help="catalog file to (re)write — catalogs/<X.Y>/catalog-kasmweb.yaml, "
             "X.Y being the waas minor from images.yaml `release:` (the "
             "Makefile derives it)")
    parser.add_argument(
        "--probe-hardening", action="store_true",
        help="pull+run each resolved image via probe_kasm_hardening.sh to "
             "derive profile/recommended — slow, needs Docker; off by "
             "default so the local loop stays fast and offline-friendly")
    args = parser.parse_args()

    mapping_path = Path(args.mapping)
    mapping = yaml.safe_load(mapping_path.read_text())
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    probe = probe_hardening if args.probe_hardening else (lambda ref: None)
    # Same opt-in as the hardening probe: by the time this runs the
    # image is already pulled (probe() above), so it's free to also run.
    kasmvnc_extractor = extract_kasmvnc if args.probe_hardening else (lambda ref: None)
    previous = load_previous(out_path)

    if args.image:
        img = resolve_mapping_entry(mapping, mapping_path, args.image)
        entry = catalog({"images": [img]}, probe=probe, extract_kasmvnc=kasmvnc_extractor,
                         previous=previous)["images"][0]
        out_data = upsert_entry(out_path, entry)
        out_path.write_text(dump_catalog(out_data))
        profile_note = f" (profile: {entry['profile']})" if entry.get("profile") else ""
        print(f"updated {out_path}: {entry['app']} -> {entry['image']}{profile_note}")
        return

    out = catalog(mapping, probe=probe, extract_kasmvnc=kasmvnc_extractor, previous=previous)
    out_path.write_text(dump_catalog(out))
    print(f"generated {out_path} with {len(out['images'])} image(s)")


if __name__ == "__main__":
    main()
