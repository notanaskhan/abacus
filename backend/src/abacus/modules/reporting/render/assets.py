"""The renderer's vendored assets (ADR-320 §3, §4): the TrueType faces fontconfig reads (the only
fonts a render can use), verified against their manifest before every render, and the in-memory
map the `asset:` fetcher serves (letterhead and signature images join it with P-11-T07).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"
MANIFEST = FONTS_DIR / "MANIFEST.sha256"
FONTCONFIG_FILE = FONTS_DIR / "fonts.conf"


class AssetError(RuntimeError):
    """A vendored file is missing or its bytes differ from the manifest."""


@dataclass(frozen=True)
class FontFace:
    family: str
    weight: int
    file: str

    @property
    def asset_id(self) -> str:
        return f"font/{self.file}"


# Arimo for form faces, Gelasio for letterheads and signature lines, Geist Mono for figures in
# trace exports (ADR-320). The paper's body text is a layout choice among these.
FACES: tuple[FontFace, ...] = (
    FontFace("Arimo", 400, "arimo-latin-400-normal.ttf"),
    FontFace("Arimo", 700, "arimo-latin-700-normal.ttf"),
    FontFace("Gelasio", 400, "gelasio-latin-400-normal.ttf"),
    FontFace("Gelasio", 500, "gelasio-latin-500-normal.ttf"),
    FontFace("Gelasio", 700, "gelasio-latin-700-normal.ttf"),
    FontFace("Geist Mono", 400, "geist-mono-latin-400-normal.ttf"),
    FontFace("Geist Mono", 500, "geist-mono-latin-500-normal.ttf"),
)


def _manifest() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        digest, _, name = line.partition("  ")
        if digest and name:
            entries[name] = digest
    return entries


@cache
def font_assets() -> dict[str, bytes]:
    """`asset:font/<file>` → bytes, each checked against MANIFEST.sha256 (a swapped or edited font
    file would change every render's bytes, so it is refused, not used)."""
    manifest = _manifest()
    out: dict[str, bytes] = {}
    for face in FACES:
        data = (FONTS_DIR / face.file).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest.get(face.file):
            raise AssetError(f"{face.file} does not match the fonts manifest")
        out[face.asset_id] = data
    return out


def fonts_manifest_sha256() -> str:
    """The manifest's own hash: part of `engine_version` (P-11 §4.2)."""
    return hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
