"""PDFs with active content (Q-03 §D1; ED-021; DEC-296). Pure code, no I/O.

A PDF can carry things a viewer runs or opens: JavaScript (`/JavaScript`, `/JS`), an open or
page action that runs it (`/OpenAction`, `/AA` with a JavaScript action), a `/Launch` action,
and embedded files (`/EmbeddedFile`, `/EmbeddedFiles`). Such a file is stored, never extracted,
OCR'd, previewed or served by the viewer, and the upload is flagged for the team.

`markers(content)` reads the bytes as tokens, never as a document: PDF name escapes
(`/J#61vaScript`) are decoded, and FlateDecode object streams (`/ObjStm`, where a names tree
can hide) are inflated up to `MAX_INFLATED` bytes in all, so a compression bomb costs at most
that. Nothing is parsed or
rendered. It runs before storage (the upload audit) and again inside the isolated extraction and
rendering children, so a file stored before this rule existed is never derived from either.
"""

from __future__ import annotations

import re
import zlib
from typing import Final

PDF_MAGIC: Final = b"%PDF-"
MAX_INFLATED: Final = 16 * 1024 * 1024
MAX_STREAMS: Final = 100_000

# Markers, in the order a reason names them (the first found is the flag's reason).
JAVASCRIPT: Final = "javascript"
LAUNCH: Final = "launch_action"
EMBEDDED: Final = "embedded_file"
OPEN_ACTION: Final = "open_action"

_NAME: Final = re.compile(rb"/((?:[A-Za-z0-9_.\-+]|#[0-9A-Fa-f]{2})+)")
_HEX: Final = re.compile(rb"#([0-9A-Fa-f]{2})")
_STREAM: Final = re.compile(rb"(?<!end)stream\r?\n")
_DICT_WINDOW: Final = 2048
_ENDSTREAM: Final = b"endstream"


def _decoded(raw: bytes) -> bytes:
    return _HEX.sub(lambda m: bytes([int(m.group(1), 16)]), raw)


def _names(data: bytes) -> list[bytes]:
    return [_decoded(m.group(1)) for m in _NAME.finditer(data)]


def _object_streams(content: bytes) -> list[bytes]:
    """The inflated bodies of FlateDecode object streams, `MAX_INFLATED` bytes in all."""
    found: list[bytes] = []
    budget = MAX_INFLATED
    for count, match in enumerate(_STREAM.finditer(content)):
        if count >= MAX_STREAMS or budget <= 0:
            break
        window = content[max(0, match.start() - _DICT_WINDOW) : match.start()]
        header = window[window.rfind(b"obj") + 3 :] if b"obj" in window else window
        names = set(_names(header))
        if b"ObjStm" not in names or b"FlateDecode" not in names:
            continue
        start = match.end()
        end = content.find(_ENDSTREAM, start)
        if end < 0:
            break
        inflater = zlib.decompressobj()
        try:
            body = inflater.decompress(content[start:end], budget)
        except zlib.error:
            continue
        budget -= len(body)
        found.append(body)
    return found


def markers(content: bytes) -> tuple[str, ...]:
    """The active-content markers a PDF carries, in a fixed order; () for anything else."""
    if not content.startswith(PDF_MAGIC):
        return ()
    names: set[bytes] = set(_names(content))
    for body in _object_streams(content):
        names.update(_names(body))
    found: list[str] = []
    if b"JavaScript" in names or b"JS" in names:
        found.append(JAVASCRIPT)
    if b"Launch" in names:
        found.append(LAUNCH)
    if b"EmbeddedFile" in names or b"EmbeddedFiles" in names:
        found.append(EMBEDDED)
    # An open or page action is active only when it runs something: JavaScript or a launch,
    # both already named above. A plain `/OpenAction [page /Fit]` (a view) is not active content.
    if found and (b"OpenAction" in names or b"AA" in names):
        found.append(OPEN_ACTION)
    return tuple(found)


# Audit references carry integers, never text (`kernel.uow.Ref`): each reason's code.
REASON_CODES: Final[dict[str, int]] = {JAVASCRIPT: 1, LAUNCH: 2, EMBEDDED: 3, OPEN_ACTION: 4}


def is_active(content: bytes) -> bool:
    return bool(markers(content))


def reason_of(content: bytes) -> str | None:
    """The flag's reason: the first marker, or None."""
    found = markers(content)
    return found[0] if found else None


__all__ = [
    "EMBEDDED",
    "JAVASCRIPT",
    "LAUNCH",
    "MAX_INFLATED",
    "OPEN_ACTION",
    "REASON_CODES",
    "is_active",
    "markers",
    "reason_of",
]
