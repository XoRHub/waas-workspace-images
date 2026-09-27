"""Format-contract tests for ci/generate_catalog.py against fabricated
manifests. stdlib unittest only; the core toolkit is located through
WAAS_CORE_IMAGES_DIR (see generate_catalog.toolkit_dir)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import generate_catalog as gc  # noqa: E402

gp = gc.gp

CFG = {
    "os": {"ubuntu-noble": {}, "debian-13": {}},
    "defaults": {"os": "ubuntu-noble", "archs": ["linux/amd64"]},
}

MANIFESTS = [
    {
        "name": "ubuntu-xfce",
        "layer": "desktop",
        "context": "desktop/xfce",
        "dockerfile": None,
        "description": "XFCE desktop over VNC, derived from the apt core image.",
        "icon": "ubuntu-linux",
        "variants": [
            {"name": "ubuntu-xfce"},
            {"name": "debian-xfce", "os": "debian-13", "icon": "debian-linux"},
        ],
    },
    {
        "name": "ubuntu-firefox",
        "layer": "apps",
        "context": "apps/firefox",
        "dockerfile": None,
        "description": "",
        # no icon: key at all — field must be absent, not empty
        "variants": [{"name": "ubuntu-firefox"}],
    },
]

REGISTRY = "ghcr.io/xorhub/waas-workspace-images"


class CatalogFormat(unittest.TestCase):
    def setUp(self):
        variants = gp.flatten_variants(MANIFESTS, CFG)
        self.out = gc.catalog(variants, REGISTRY, "0.4.2")
        self.by_app = {e["app"]: e for e in self.out["images"]}

    def test_api_version(self):
        self.assertEqual(self.out["apiVersion"], "waas.xorhub.io/catalog/v1")

    def test_one_entry_per_variant(self):
        self.assertEqual(
            sorted(self.by_app), ["debian-xfce", "ubuntu-firefox", "ubuntu-xfce"])

    def test_full_entry(self):
        self.assertEqual(self.by_app["ubuntu-xfce"], {
            "image": f"{REGISTRY}/ubuntu-xfce:0.4.2",
            "os": "linux",
            "app": "ubuntu-xfce",
            "version": "0.4.2",
            "icon": "ubuntu-linux",
            "displayName": "Ubuntu Xfce",
            "description": "XFCE desktop over VNC, derived from the apt core image.",
            "architectures": ["amd64"],
            "profile": "hardened",
            "recommended": gc.RECOMMENDATION_STANDARD,
        })

    def test_version_is_the_release_for_every_entry(self):
        for entry in self.out["images"]:
            self.assertEqual(entry["version"], "0.4.2")
            self.assertTrue(entry["image"].endswith(":0.4.2"))

    def test_version_must_be_semver(self):
        variants = gp.flatten_variants(MANIFESTS, CFG)
        with self.assertRaises(SystemExit):
            gc.catalog(variants, REGISTRY, "0.4")

    def test_architectures_follow_variant_archs(self):
        manifests = [dict(
            MANIFESTS[1],
            variants=[{"name": "ubuntu-firefox",
                       "archs": ["linux/amd64", "linux/arm64"]}],
        )]
        out = gc.catalog(gp.flatten_variants(manifests, CFG), "reg", "1.0.0")
        self.assertEqual(out["images"][0]["architectures"], ["amd64", "arm64"])

    def test_variant_icon_override(self):
        self.assertEqual(self.by_app["debian-xfce"]["icon"], "debian-linux")

    def test_missing_icon_and_description_omitted(self):
        entry = self.by_app["ubuntu-firefox"]
        self.assertNotIn("icon", entry)
        self.assertNotIn("description", entry)
        # displayName is always emitted: humanized id as the fallback.
        self.assertEqual(entry["displayName"], "Ubuntu Firefox")

    def test_image_ref_has_no_digest(self):
        for entry in self.out["images"]:
            self.assertNotIn("@", entry["image"])

    def test_description_never_truncated(self):
        long = ("word " * 40).strip()
        manifests = [dict(MANIFESTS[0], description=long)]
        out = gc.catalog(gp.flatten_variants(manifests, CFG), "reg", "1.0.0")
        for entry in out["images"]:
            self.assertEqual(entry["description"], long)
            self.assertNotIn("…", entry["displayName"])

    def test_display_name_source_overrides_humanize(self):
        manifests = [dict(
            MANIFESTS[0],
            displayName="XFCE Desktop",
            variants=[
                {"name": "ubuntu-xfce"},
                {"name": "debian-xfce", "os": "debian-13",
                 "displayName": "XFCE Desktop (Debian)"},
            ],
        )]
        out = gc.catalog(gp.flatten_variants(manifests, CFG), "reg", "1.0.0")
        by_app = {e["app"]: e for e in out["images"]}
        self.assertEqual(by_app["ubuntu-xfce"]["displayName"], "XFCE Desktop")
        self.assertEqual(by_app["debian-xfce"]["displayName"], "XFCE Desktop (Debian)")

    def test_humanize(self):
        self.assertEqual(gc.humanize("firefox"), "Firefox")
        self.assertEqual(gc.humanize("ubuntu-desktop-noble"), "Ubuntu Desktop Noble")
        self.assertEqual(gc.humanize("fedora-desktop-43"), "Fedora Desktop 43")
        self.assertEqual(gc.humanize("snake_case_id"), "Snake Case Id")

    def test_output_path_is_per_minor(self):
        self.assertEqual(gc.output_path("0.4.2"), Path("catalogs/0.4/catalog.yaml"))
        self.assertEqual(gc.output_path("1.12.0"), Path("catalogs/1.12/catalog.yaml"))


RECOMMENDED_MANIFESTS = [
    {
        "name": "ubuntu-desktop",
        "layer": "desktop",
        "context": "desktop/xfce",
        "dockerfile": None,
        "description": "OS desktop over VNC.",
        "variants": [
            {"name": "ubuntu-desktop-noble", "smoke": {"vnc": True, "audio": True}},
            # CI probes nothing on this one: no protocol hint at all.
            {"name": "ubuntu-desktop-unprobed", "smoke": {}},
        ],
    },
    {
        "name": "chrome",
        "layer": "apps",
        "context": "apps/chrome",
        "dockerfile": None,
        "description": "Chrome desktop, VNC only.",
        "variants": [{"name": "chrome", "smoke": {"vnc": True}}],
    },
    {
        "name": "devtools",
        "layer": "apps",
        "context": "apps/devtools",
        "dockerfile": None,
        "description": "Dev desktop.",
        "variants": [
            {"name": "devtools", "smoke": {"vnc": True}},
            {"name": "devtools-dev", "profile": "dev", "smoke": {"vnc": True}},
        ],
    },
    {
        "name": "hermes-agent",
        "layer": "apps",
        "context": "apps/hermes-agent",
        "dockerfile": None,
        "description": "Hermes agent.",
        # An image-only hint plus one colliding with the vnc-derived
        # WAAS_AUDIO_ENABLED (manifest wins).
        "env": [
            {"name": "WAAS_HERMES_DASHBOARD", "default": "1"},
            {"name": "WAAS_AUDIO_ENABLED", "default": "0"},
        ],
        "variants": [{"name": "hermes-agent", "smoke": {"vnc": True}}],
    },
]


class CatalogRecommended(unittest.TestCase):
    def setUp(self):
        variants = gp.flatten_variants(RECOMMENDED_MANIFESTS, CFG)
        self.out = gc.catalog(variants, "reg", "1.0.0")
        self.by_app = {e["app"]: e for e in self.out["images"]}

    def test_standard_profile_maps_to_hardened(self):
        entry = self.by_app["chrome"]
        self.assertEqual(entry["profile"], "hardened")
        sec = entry["recommended"]["securityContext"]
        self.assertTrue(sec["readOnlyRootFilesystem"])
        self.assertFalse(sec["allowPrivilegeEscalation"])
        self.assertEqual(sec["capabilities"], {"drop": ["ALL"]})
        self.assertEqual(entry["recommended"]["volumes"],
                         [{"name": "tmp", "mountPath": "/tmp"}])

    def test_dev_profile_maps_to_normal_with_exceptions(self):
        entry = self.by_app["devtools-dev"]
        self.assertEqual(entry["profile"], "normal")
        sec = entry["recommended"]["securityContext"]
        self.assertFalse(sec["readOnlyRootFilesystem"])
        self.assertTrue(sec["allowPrivilegeEscalation"])
        # Runtime-default capabilities kept — never an explicit empty drop.
        self.assertNotIn("capabilities", sec)
        self.assertEqual(entry["recommended"]["podSecurityContext"],
                         self.by_app["devtools"]["recommended"]["podSecurityContext"])

    def test_env_hints_follow_smoke(self):
        for app in ("ubuntu-desktop-noble", "chrome"):
            self.assertEqual(
                [h["name"] for h in self.by_app[app]["recommended"]["env"]],
                ["WAAS_AUDIO_ENABLED"])
        self.assertNotIn("env", self.by_app["ubuntu-desktop-unprobed"]["recommended"])

    def test_no_hint_ever_names_a_dropped_protocol(self):
        for entry in self.out["images"]:
            for hint in entry["recommended"].get("env", []):
                self.assertNotIn("RDP", hint["name"])
                self.assertNotIn("SSH", hint["name"])
                self.assertEqual(hint.get("protocols", ["vnc"]), ["vnc"])

    def test_manifest_env_merges_and_overrides_protocol_hints(self):
        env = self.by_app["hermes-agent"]["recommended"]["env"]
        self.assertEqual([h["name"] for h in env],
                         ["WAAS_AUDIO_ENABLED", "WAAS_HERMES_DASHBOARD"])
        audio = next(h for h in env if h["name"] == "WAAS_AUDIO_ENABLED")
        self.assertEqual(audio["default"], "0")

    def test_no_smoke_protocols_omits_env_key(self):
        out = gc.catalog(gp.flatten_variants(MANIFESTS, CFG), "reg", "1.0.0")
        by_app = {e["app"]: e for e in out["images"]}
        self.assertNotIn("env", by_app["ubuntu-xfce"]["recommended"])


class ThisRepo(unittest.TestCase):
    def test_every_variant_is_catalogued(self):
        root = Path(__file__).resolve().parents[2]
        cfg = gp.load_config(root)
        variants = gp.flatten_variants(gp.load_manifests(root, cfg["layers"]), cfg)
        out = gc.catalog(variants, gc.DEFAULT_REGISTRY, "0.4.0")
        self.assertEqual([e["app"] for e in out["images"]], sorted(variants))
        for entry in out["images"]:
            self.assertTrue(entry["image"].startswith("ghcr.io/xorhub/waas-workspace-images/"))


if __name__ == "__main__":
    unittest.main()
