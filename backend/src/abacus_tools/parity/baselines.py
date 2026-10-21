"""Fetch parity baselines for a handoff version (F-05-T16): `pnpm visual:baselines`.

Run: python -m abacus_tools.parity.baselines [--source DIR] [--dest DIR]

The full reference set lives outside git, keyed by handoff version (chapter 04 §9.3, D-DS-12):
`<source>/<handoff version>/<file>.png` with the `index.json` that crop_handoff writes. The source
is a local directory today (a crop_handoff output directory, or a mirror of the bucket); the
`abacus-shared-design-baselines` bucket (Q-01) is the same layout behind an `s3://` source and is
not wired. Every file is checked against the index's SHA-256 before it is copied, and files in the
destination that the version does not name are removed, so the destination is exactly that version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from abacus_tools.parity.crop_handoff import REPO, VERSION_FILE, ManifestError, read_version

DEST = REPO / "apps" / "web" / ".visual" / "parity.spec.ts"
SOURCE_ENV = "ACCRUED_BASELINES_SOURCE"


class BaselineError(RuntimeError):
    """The baselines cannot be fetched."""


def fetch(source: str, dest: Path, version: str) -> list[str]:
    """Copy `<source>/<version>/*.png` into `dest`; returns the keys fetched."""
    if "://" in source:
        raise BaselineError(
            f"{source}: bucket sources are not wired yet (Q-01); point {SOURCE_ENV} at a directory"
        )
    root = Path(source).expanduser() / version
    index_path = root / "index.json"
    if not index_path.is_file():
        raise BaselineError(f"{root}: no baselines for handoff version {version}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("handoff_version") != version:
        raise BaselineError(f"{index_path}: the index is for {index.get('handoff_version')}")
    dest.mkdir(parents=True, exist_ok=True)
    keep: set[str] = set()
    for key, item in sorted(index["entries"].items()):
        file = root / item["file"]
        if not file.is_file():
            raise BaselineError(f"{key}: {file} is missing")
        if hashlib.sha256(file.read_bytes()).hexdigest() != item["sha256"]:
            raise BaselineError(f"{key}: {file} does not match the index; fetch it again")
        shutil.copyfile(file, dest / item["file"])
        keep.add(item["file"])
    for stale in dest.glob("*.png"):
        if stale.name not in keep:
            stale.unlink()
    return sorted(index["entries"])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="baselines", description=__doc__)
    parser.add_argument("--source", default=os.environ.get(SOURCE_ENV, ""))
    parser.add_argument("--dest", type=Path, default=DEST)
    parser.add_argument("--version-file", type=Path, default=VERSION_FILE)
    args = parser.parse_args(argv)
    if not args.source:
        print(f"baselines: set {SOURCE_ENV} or pass --source", file=sys.stderr)
        return 1
    try:
        keys = fetch(args.source, args.dest, read_version(args.version_file))
    except (BaselineError, ManifestError, OSError, ValueError) as error:
        print(f"baselines: {error}", file=sys.stderr)
        return 1
    print(f"fetched {len(keys)} baselines into {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
