#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pyyaml==6.0.2",
#   "jsonschema==4.26.0",
# ]
# ///
"""Validate catalog file(s) against the vendored WaaS JSON Schema
(ci/schema/v1.schema.json). A syntactically valid YAML can still violate
the contract waas parses (exact apiVersion, os enum,
additionalProperties: false): every violation is printed, exit 1 on any.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "v1.schema.json"


def validate(data: dict, schema: dict) -> list[str]:
    validator = Draft202012Validator(schema)
    return [
        f"{'.'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", metavar="catalog.yaml")
    args = parser.parse_args()

    schema = json.loads(SCHEMA_PATH.read_text())
    failed = False
    for file in args.files:
        errors = validate(yaml.safe_load(Path(file).read_text()), schema)
        if errors:
            failed = True
            for msg in errors:
                print(f"{file}: {msg}", file=sys.stderr)
        else:
            print(f"{file}: valid ({SCHEMA_PATH.name})")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
