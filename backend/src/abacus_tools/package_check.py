"""Unpack an engagement export package into a blank folder and verify it (Q-04-T019; A-01's
format `accrued.binder-export` 1.0, `docs/contracts/engagement-export-v1.md`;
`docs/runbooks/firm-rollback.md`).

    python -m abacus_tools.package_check <export.zip> --into <new empty folder>

A firm rollback hands the firm its engagements as files. The rehearsal (and every real rollback)
proves the package is usable without Accrued: it is unpacked into a folder that did not exist,
exactly as a firm's own workpaper folder would receive it, and checked the way the package's
README tells the firm to (`shasum -a 256 -c manifest.sha256`, `shasum -a 256 -c checksums.sha256`),
here in Python so it runs the same on any machine:

- **Unpacked safely.** Every entry stays inside the folder: an absolute path, a `..` part, a
  symlink, a duplicate name or a total over `--max-bytes` (default 20 GiB) refuses the package
  before anything is written outside it. The folder must not exist yet.
- **Both checksum files pass.** Every line of `manifest.sha256` and `checksums.sha256`
  (`sha256sum` format) names a file that exists and hashes to the line's value.
- **Nothing unlisted.** Every unpacked file is named by `checksums.sha256`, except the two checksum
  files themselves (the builder lists every file but those).
- **The manifest agrees.** Each file `manifest.json` lists has the same SHA-256 there as in
  `checksums.sha256`.

The report is JSON of counts and file paths inside the package (never content). Exit 0 when the
package verifies, 1 when it does not, 2 when it was refused before unpacking.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final, cast

DEFAULT_MAX_BYTES: Final = 20 * 1024**3
CHECKSUM_FILES: Final = ("manifest.sha256", "checksums.sha256")
_LINE: Final = re.compile(r"^([0-9a-f]{64}) [ *](.+)$")


class PackageRefused(ValueError):
    """The package would not be unpacked: a path that escapes, a link, a duplicate, too large."""


@dataclass
class Result:
    files: int = 0
    bytes: int = 0
    checked: dict[str, int] = field(default_factory=dict[str, int])
    missing: list[str] = field(default_factory=list[str])
    mismatched: list[str] = field(default_factory=list[str])
    unlisted: list[str] = field(default_factory=list[str])
    manifest_disagrees: list[str] = field(default_factory=list[str])
    malformed: list[str] = field(default_factory=list[str])

    @property
    def ok(self) -> bool:
        return not (
            self.missing
            or self.mismatched
            or self.unlisted
            or self.manifest_disagrees
            or self.malformed
            or any(self.checked.get(name, 0) == 0 for name in CHECKSUM_FILES)
        )

    def as_json(self) -> dict[str, object]:
        return {"ok": self.ok, **self.__dict__}


def _safe_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or name.startswith("/") or "\\" in name or path.is_absolute():
        raise PackageRefused(f"an absolute or odd path: {name!r}")
    if any(part in ("..", "") for part in path.parts) or re.match(r"^[A-Za-z]:", name):
        raise PackageRefused(f"a path that leaves the folder: {name!r}")
    return path


def _is_link(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def unpack(package: Path, into: Path, max_bytes: int = DEFAULT_MAX_BYTES) -> int:
    """Unpack into a new folder after checking every entry; the bytes written."""
    if into.exists():
        raise PackageRefused(f"{into} already exists: unpack into a new, blank folder")
    with zipfile.ZipFile(package) as archive:
        infos = archive.infolist()
        seen: set[str] = set()
        total = 0
        for info in infos:
            name = str(_safe_name(info.filename))
            if _is_link(info):
                raise PackageRefused(f"a symbolic link: {name!r}")
            if name in seen:
                raise PackageRefused(f"a duplicate entry: {name!r}")
            seen.add(name)
            total += info.file_size
            if total > max_bytes:
                raise PackageRefused(f"more than {max_bytes} bytes unpacked")
        into.mkdir(parents=True)
        written = 0
        for info in infos:
            target = into / _safe_name(info.filename)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as sink:
                while chunk := source.read(1024 * 1024):
                    written += len(chunk)
                    if written > max_bytes:  # a header that understated its size
                        raise PackageRefused(f"more than {max_bytes} bytes unpacked")
                    sink.write(chunk)
        return written


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _listed(text: str) -> Iterable[tuple[int, str, str] | int]:
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        match = _LINE.match(line)
        yield (number, match.group(1), match.group(2)) if match else number


def verify(folder: Path) -> Result:
    result = Result()
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    result.files = len(files)
    result.bytes = sum(p.stat().st_size for p in files)
    listed_hashes: dict[str, str] = {}
    for checksum_file in CHECKSUM_FILES:
        source = folder / checksum_file
        result.checked[checksum_file] = 0
        if not source.is_file():
            result.missing.append(checksum_file)
            continue
        for entry in _listed(source.read_text(encoding="utf-8")):
            if isinstance(entry, int):
                result.malformed.append(f"{checksum_file}:{entry}")
                continue
            _number, expected, name = entry
            try:
                target = folder / _safe_name(name)
            except PackageRefused:
                result.malformed.append(f"{checksum_file}:{name}")
                continue
            result.checked[checksum_file] += 1
            if checksum_file == "checksums.sha256":
                listed_hashes[name] = expected
            if not target.is_file():
                result.missing.append(name)
            elif _sha256(target) != expected:
                result.mismatched.append(name)
    for path in files:
        rel = path.relative_to(folder).as_posix()
        if rel not in CHECKSUM_FILES and rel not in listed_hashes:
            result.unlisted.append(rel)
    result.manifest_disagrees = manifest_disagreements(folder / "manifest.json", listed_hashes)
    return result


def manifest_disagreements(manifest: Path, listed: dict[str, str]) -> list[str]:
    """Files whose SHA-256 in `manifest.json` is not the one `checksums.sha256` gives."""
    if not manifest.is_file():
        return ["manifest.json"]
    try:
        body: object = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return ["manifest.json"]
    entries: object = (
        cast(dict[str, object], body).get("files", []) if isinstance(body, dict) else []
    )
    out: list[str] = []
    for entry in cast(list[object], entries) if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        fields = cast(dict[str, object], entry)
        path, digest = fields.get("path"), fields.get("sha256")
        if isinstance(path, str) and isinstance(digest, str) and listed.get(path) != digest:
            out.append(path)
    return sorted(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.package_check", description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--into", type=Path, required=True, help="a folder that does not exist")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args(argv)
    try:
        unpack(args.package, args.into, args.max_bytes)
    except (PackageRefused, zipfile.BadZipFile) as exc:
        print(json.dumps({"ok": False, "refused": str(exc)}), file=sys.stderr)
        return 2
    result = verify(args.into)
    print(json.dumps(result.as_json(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
