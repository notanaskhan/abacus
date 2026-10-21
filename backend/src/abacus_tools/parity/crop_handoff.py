"""Crop the design handoff's reference PNGs into per-specimen parity baselines (F-05-T16).

Run: python -m abacus_tools.parity.crop_handoff <handoff-dir> <out-dir> [options]

Reads the checked-in manifest (docs/design/parity-manifest.json): each entry names a gallery
specimen (and optionally a part of it), the handoff PNG it is drawn from, that PNG's SHA-256 and
the crop box in the PNG's own pixels (the handoff is captured at 2x). Writes
`<out-dir>/<handoff version>/<key, with . as ->.png` and an `index.json` that records the source
and output hashes, so a baseline can be traced to the handoff and a changed handoff is noticed.

The handoff and its crops are never committed: the repository is public (D-DS-12). Standard
library and Pillow only (Pillow is on the dependency allowlist).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PIL import Image

REPO = Path(__file__).resolve().parents[4]
MANIFEST = REPO / "docs" / "design" / "parity-manifest.json"
VERSION_FILE = REPO / "docs" / "design" / "HANDOFF_VERSION"

# The product window of a 1440 x 900 screen artboard at 2x: x 40..2840, y 40..1760 (§9.3).
WINDOW_CROP = (40, 40, 2840, 1760)
TIERS = ("A", "B", "C", "D")
_KEY = re.compile(r"^[a-z0-9][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


Json = dict[str, Any]  # a JSON object read from disk: the manifest and the baseline index


class ManifestError(ValueError):
    """The manifest is malformed."""


class SourceError(RuntimeError):
    """A handoff source is missing, changed or too small for its crop."""


@dataclass(frozen=True)
class Entry:
    key: str
    specimen: str
    selector: str | None
    source: str
    sha256: str
    crop: tuple[int, int, int, int]
    tier: str
    locked: bool
    deviation: str | None


def baseline_file(key: str) -> str:
    """A baseline's file name. Playwright turns `.` in a snapshot name into `-`; so does this."""
    return f"{key.replace('.', '-')}.png"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_version(path: Path = VERSION_FILE) -> str:
    version = path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", version):
        raise ManifestError(f"{path}: a handoff version is one token of letters, digits, . _ -")
    return version


def _crop(key: str, raw: object) -> tuple[int, int, int, int]:
    if raw == "window":
        return WINDOW_CROP
    box = cast("list[object]", raw) if isinstance(raw, list) else []
    if len(box) != 4 or not all(isinstance(v, int) and not isinstance(v, bool) for v in box):
        raise ManifestError(f'{key}: "crop" is [x0, y0, x1, y1] in integers, or "window"')
    x0, y0, x1, y1 = (cast("int", v) for v in box)
    if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
        raise ManifestError(f"{key}: the crop box {box} is empty or negative")
    return (x0, y0, x1, y1)


def parse_entry(key: str, raw: Json) -> Entry:
    if not _KEY.fullmatch(key):
        raise ManifestError(f"{key}: a key is <specimen-id> or <specimen-id>.<part>, lower-case")
    source = raw.get("source")
    if not isinstance(source, str) or not source.endswith(".png"):
        raise ManifestError(f'{key}: "source" is a .png path relative to the handoff root')
    if Path(source).is_absolute() or ".." in Path(source).parts:
        raise ManifestError(f'{key}: "source" stays inside the handoff root')
    sha = raw.get("sha256")
    if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
        raise ManifestError(f'{key}: "sha256" is the source PNG\'s 64-digit hash')
    tier = raw.get("tier")
    if tier not in TIERS:
        raise ManifestError(f'{key}: "tier" is one of {", ".join(TIERS)}')
    selector = raw.get("selector")
    if selector is not None and not isinstance(selector, str):
        raise ManifestError(f'{key}: "selector" is a CSS selector inside the specimen')
    deviation = raw.get("deviation")
    if deviation is not None and not (isinstance(deviation, str) and deviation.strip()):
        raise ManifestError(f'{key}: "deviation" says in words why the pixels differ')
    return Entry(
        key=key,
        specimen=key.split(".")[0],
        selector=selector,
        source=source,
        sha256=sha,
        crop=_crop(key, raw.get("crop")),
        tier=tier,
        locked=raw.get("locked") is True,
        deviation=deviation,
    )


def load_manifest(path: Path = MANIFEST) -> list[Entry]:
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    raw = cast("Json", loaded) if isinstance(loaded, dict) else {}
    if raw.get("schema") != 1:
        raise ManifestError(f'{path}: expected an object with "schema": 1')
    entries = raw.get("entries")
    if not isinstance(entries, dict) or not entries:
        raise ManifestError(f'{path}: "entries" is a non-empty object keyed by specimen')
    return [parse_entry(str(key), value) for key, value in cast("Json", entries).items()]


def crop_entry(handoff: Path, entry: Entry, *, verify: bool = True) -> Image.Image:
    """The cropped region as an opaque RGB image (the handoff's PNGs are fully opaque RGBA)."""
    source = handoff / entry.source
    if not source.is_file():
        raise SourceError(f"{entry.key}: {entry.source} is not in the handoff at {handoff}")
    if verify and sha256_of(source) != entry.sha256:
        raise SourceError(
            f"{entry.key}: {entry.source} has changed since the manifest was pinned; look at it, "
            "re-check the crop box, then run with --pin"
        )
    with Image.open(source) as image:
        if entry.crop[2] > image.width or entry.crop[3] > image.height:
            raise SourceError(
                f"{entry.key}: crop {entry.crop} is outside {entry.source} "
                f"({image.width} x {image.height})"
            )
        region = image.crop(entry.crop)
        if region.mode == "RGBA":
            backdrop = Image.new("RGBA", region.size, (255, 255, 255, 255))
            region = Image.alpha_composite(backdrop, region)
        return region.convert("RGB")


def crop_all(
    handoff: Path,
    out: Path,
    entries: list[Entry],
    version: str,
    *,
    verify: bool = True,
    skip_missing: bool = False,
) -> Json:
    """Write every entry's crop under `<out>/<version>/`; returns the index it also writes."""
    target = out / version
    target.mkdir(parents=True, exist_ok=True)
    written: Json = {}
    for entry in entries:
        if skip_missing and not (handoff / entry.source).is_file():
            continue
        region = crop_entry(handoff, entry, verify=verify)
        path = target / baseline_file(entry.key)
        region.save(path, format="PNG", optimize=True)
        written[entry.key] = {
            "file": path.name,
            "sha256": sha256_of(path),
            "size": list(region.size),
            "source": entry.source,
            "source_sha256": entry.sha256,
            "tier": entry.tier,
        }
    index: Json = {"handoff_version": version, "entries": written}
    (target / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    return index


def pin(handoff: Path, manifest: Path) -> list[str]:
    """Rewrite each entry's `sha256` from the handoff on disk; returns the keys that changed."""
    raw: Json = json.loads(manifest.read_text(encoding="utf-8"))
    changed: list[str] = []
    for key, entry in raw["entries"].items():
        source = handoff / entry["source"]
        if not source.is_file():
            raise SourceError(f"{key}: {entry['source']} is not in the handoff at {handoff}")
        digest = sha256_of(source)
        if entry.get("sha256") != digest:
            entry["sha256"] = digest
            changed.append(key)
    manifest.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    return changed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="crop_handoff", description=__doc__)
    parser.add_argument("handoff", type=Path, help="the handoff root ($ACCRUED_HANDOFF_DIR)")
    parser.add_argument("out", type=Path, help="where the baselines are written")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--version-file", type=Path, default=VERSION_FILE)
    parser.add_argument("--only", action="append", default=[], help="a manifest key; repeatable")
    parser.add_argument("--pin", action="store_true", help="re-pin each source's SHA-256 first")
    parser.add_argument("--skip-missing", action="store_true", help="skip sources not on disk")
    args = parser.parse_args(argv)
    try:
        if args.pin:
            for key in pin(args.handoff, args.manifest):
                print(f"pinned {key}")
        entries = load_manifest(args.manifest)
        if args.only:
            unknown = sorted(set(args.only) - {e.key for e in entries})
            if unknown:
                raise ManifestError(f"not in the manifest: {', '.join(unknown)}")
            entries = [e for e in entries if e.key in args.only]
        version = read_version(args.version_file)
        index = crop_all(args.handoff, args.out, entries, version, skip_missing=args.skip_missing)
    except (ManifestError, SourceError, OSError, json.JSONDecodeError) as error:
        print(f"crop_handoff: {error}", file=sys.stderr)
        return 1
    print(f"wrote {len(index['entries'])} baselines to {args.out / version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
