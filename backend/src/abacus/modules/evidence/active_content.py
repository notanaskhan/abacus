"""PDFs with active content (Q-03 §D1; ED-021; DEC-296, DEC-299). Pure code, no I/O.

A PDF can carry things a viewer runs, opens or submits: JavaScript (`/JavaScript`, `/JS`), launch,
embedded-go-to, submit and import actions (`/Launch`, `/GoToE`, `/SubmitForm`, `/ImportData`),
embedded files (`/EmbeddedFile(s)`, a file specification's `/EF`, `/FileAttachment` annotations),
XFA forms (`/XFA`) and rich media (`/RichMedia`); `/OpenAction` and `/AA` run them. Such a file is
stored, never extracted, OCR'd, previewed or served by the viewer, and is flagged for the team.

`markers(content)` reads the bytes as tokens, never as a document, and **fails closed**: whatever
it cannot read completely is `unscannable`, which is active content.

- Names are decoded (`#xx` escapes) and compared case-folded.
- Objects are walked in order; a dictionary is read with its strings, hex strings and comments
  skipped, so `(obj)` or `>>` inside a string can't move a boundary.
- Every object stream (`/Type /ObjStm`) is decoded and read too. It must have a direct
  `/Length` that ends at `endstream`, and either no filter or exactly `/FlateDecode` with no
  `/DecodeParms`; anything else (ASCIIHex, ASCII85, LZW, a chain, a predictor, an indirect or
  wrong length, a decompression error, a stream that doesn't end, an encrypted object stream) is
  `unscannable`.
- Hard caps, each failing closed: `MAX_SCAN_BYTES` read in all (raw and inflated), `MAX_OBJECTS`
  object headers and `MAX_OBJECT_STREAMS` object streams.

It runs before storage in an isolated child with a timeout (`uploads.screened`), and again inside
the isolated extraction, rendering and word-layer children, so a file stored before this rule
existed is never derived from either.
"""

from __future__ import annotations

import re
import zlib
from typing import Final, cast

PDF_MAGIC: Final = b"%PDF-"
MAX_SCAN_BYTES: Final = 96 * 1024 * 1024  # 50 MB raw, then what object streams inflate to
MAX_INFLATED: Final = 32 * 1024 * 1024
MAX_OBJECTS: Final = 250_000
MAX_OBJECT_STREAMS: Final = 2_000
MAX_DICT: Final = 256 * 1024  # one object's dictionary

# Markers, in the order a reason names them (the first found is the flag's reason).
JAVASCRIPT: Final = "javascript"
LAUNCH: Final = "launch_action"
EMBEDDED: Final = "embedded_file"
XFA: Final = "xfa_form"
RICH_MEDIA: Final = "rich_media"
GOTO_EMBEDDED: Final = "goto_embedded"
SUBMIT: Final = "submit_form"
IMPORT: Final = "import_data"
UNSCANNABLE: Final = "unscannable"
OPEN_ACTION: Final = "open_action"

_RULES: Final[tuple[tuple[str, frozenset[bytes]], ...]] = (
    (JAVASCRIPT, frozenset({b"javascript", b"js"})),
    (LAUNCH, frozenset({b"launch"})),
    (EMBEDDED, frozenset({b"embeddedfile", b"embeddedfiles", b"ef", b"fileattachment"})),
    (XFA, frozenset({b"xfa"})),
    (RICH_MEDIA, frozenset({b"richmedia"})),
    (GOTO_EMBEDDED, frozenset({b"gotoe"})),
    (SUBMIT, frozenset({b"submitform"})),
    (IMPORT, frozenset({b"importdata"})),
)
_RUNNERS: Final = frozenset({b"openaction", b"aa"})

_NAME: Final = re.compile(rb"/((?:[A-Za-z0-9_.\-+*!$&'\"~^`|]|#[0-9A-Fa-f]{2})+)")
_HEX: Final = re.compile(rb"#([0-9A-Fa-f]{2})")
_OBJECT: Final = re.compile(
    rb"(?<![0-9])[0-9]{1,10}[ \t\r\n\f\x00]+[0-9]{1,5}[ \t\r\n\f\x00]+obj\b"
)
_LENGTH: Final = re.compile(
    rb"/Length[ \t\r\n\f\x00]*([0-9]{1,12})(?![0-9])(?![ \t\r\n\f\x00]+[0-9]+[ \t\r\n\f\x00]+R)"
)
_FILTER: Final = re.compile(
    rb"/Filter[ \t\r\n\f\x00]*(\[[^\]]{0,512}\]|/[^ \t\r\n\f\x00/<>\[\]()]+)"
)
_WS: Final = b" \t\r\n\f\x00"


class _Unscannable(Exception):
    """Something the scan can't read completely: flagged (fail closed)."""


def _decoded(raw: bytes) -> bytes:
    return _HEX.sub(lambda m: bytes([int(m.group(1), 16)]), raw).lower()


def _names(data: bytes | memoryview) -> set[bytes]:
    return {_decoded(m.group(1)) for m in _NAME.finditer(data)}


def _skip_string(data: bytes, i: int) -> int:
    """`data[i]` is `(`: the index after its matching `)` (escapes and nesting), or -1."""
    depth, n = 0, len(data)
    while i < n:
        c = data[i]
        if c == 0x5C:  # backslash: skip the escaped byte
            i += 2
            continue
        if c == 0x28:
            depth += 1
        elif c == 0x29:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _dict_end(data: bytes, i: int) -> int:
    """`data[i:i+2]` is `<<`: the index after its matching `>>`, or -1 when it doesn't close
    within `MAX_DICT` bytes."""
    depth, n = 0, min(len(data), i + MAX_DICT)
    while i < n:
        c = data[i]
        if c == 0x28:  # (string)
            i = _skip_string(data, i)
            if i < 0:
                return -1
            continue
        if c == 0x25:  # % comment, to the end of the line
            while i < n and data[i] not in (0x0A, 0x0D):
                i += 1
            continue
        if c == 0x3C:  # < : a dictionary, or a hex string
            if i + 1 < n and data[i + 1] == 0x3C:
                depth += 1
                i += 2
                continue
            close = data.find(b">", i, n)
            if close < 0:
                return -1
            i = close + 1
            continue
        if c == 0x3E and i + 1 < n and data[i + 1] == 0x3E:
            depth -= 1
            i += 2
            if depth == 0:
                return i
            continue
        i += 1
    return -1


def _skip_ws(data: bytes, i: int) -> int:
    n = len(data)
    while i < n and data[i] in _WS:
        i += 1
    return i


def _data_end(header: bytes, data: bytes, start: int) -> int | None:
    """Where a stream's data ends by its direct `/Length`, when that ends at `endstream`."""
    length = _LENGTH.search(header)
    if length is None:
        return None
    end = start + int(length.group(1))
    if end > len(data) or data[_skip_ws(data, end) :][:9] != b"endstream":
        return None
    return end


def _object_stream(
    header: bytes, names: set[bytes], view: memoryview, start: int, end: int | None, budget: int
) -> bytes:
    """An object stream's decoded body; `_Unscannable` unless it is plainly Flate (or
    unfiltered) with a direct length that ends at `endstream`."""
    if end is None:
        raise _Unscannable("an indirect, missing or wrong length")
    if names & {b"decodeparms", b"dp"}:
        raise _Unscannable("decode parameters")
    found = _FILTER.search(header)
    if found is None:
        return bytes(view[start:end])
    if _names(found.group(1)) != {b"flatedecode"} or found.group(1).count(b"/") != 1:
        raise _Unscannable("a filter the scan doesn't decode")
    inflater = zlib.decompressobj()
    try:
        out = inflater.decompress(view[start:end], budget)
    except zlib.error:
        raise _Unscannable("decompression failed") from None
    if inflater.unconsumed_tail or not inflater.eof:
        raise _Unscannable("the stream didn't inflate completely within the budget")
    return out


def _scan(content: bytes) -> set[bytes]:
    if len(content) > MAX_SCAN_BYTES:
        raise _Unscannable("too large to scan")
    view = memoryview(content)
    names = _names(content)
    budget = min(MAX_INFLATED, MAX_SCAN_BYTES - len(content))
    objects = streams = 0
    pos = 0
    while True:
        found = _OBJECT.search(content, pos)
        if found is None:
            break
        objects += 1
        if objects > MAX_OBJECTS:
            raise _Unscannable("too many objects")
        i = _skip_ws(content, found.end())
        if content[i : i + 2] != b"<<":
            pos = found.end()
            continue
        end = _dict_end(content, i)
        if end < 0:
            raise _Unscannable("a dictionary that doesn't close")
        header = content[i:end]
        j = _skip_ws(content, end)
        if content[j : j + 6] != b"stream":
            pos = end
            continue
        start = j + 6
        if content[start : start + 2] == b"\r\n":
            start += 2
        elif content[start : start + 1] in (b"\n", b"\r"):
            start += 1
        header_names = _names(header)
        data_end = _data_end(header, content, start)
        if b"objstm" not in header_names:
            # Not an object stream: its data holds no objects; skip it by its length, else to
            # the first `endstream` (a fake one inside the data only skips less).
            if data_end is None:
                data_end = content.find(b"endstream", start)
                if data_end < 0:
                    raise _Unscannable("a stream that doesn't end")
            pos = data_end
            continue
        streams += 1
        if streams > MAX_OBJECT_STREAMS:
            raise _Unscannable("too many object streams")
        body = _object_stream(header, header_names, view, start, data_end, budget)
        budget -= len(body)
        if budget <= 0:
            raise _Unscannable("the scan budget ran out")
        names |= _names(body)
        pos = cast(int, data_end)
    return names


def markers(content: bytes) -> tuple[str, ...]:
    """The active-content markers a PDF carries, in a fixed order; () for anything else."""
    if not content.startswith(PDF_MAGIC):
        return ()
    try:
        names = _scan(content)
    except _Unscannable:
        return (UNSCANNABLE,)
    found = [reason for reason, keys in _RULES if names & keys]
    # An open or page action is active only when it runs something named above; a plain
    # `/OpenAction [page /Fit]` (a view) is not active content.
    if found and names & _RUNNERS:
        found.append(OPEN_ACTION)
    return tuple(found)


def is_active(content: bytes) -> bool:
    return bool(markers(content))


def reason_of(content: bytes) -> str | None:
    """The flag's reason: the first marker, or None."""
    found = markers(content)
    return found[0] if found else None


# Audit references carry integers, never text (`kernel.uow.Ref`): each reason's code.
REASON_CODES: Final[dict[str, int]] = {
    JAVASCRIPT: 1,
    LAUNCH: 2,
    EMBEDDED: 3,
    OPEN_ACTION: 4,
    XFA: 5,
    RICH_MEDIA: 6,
    GOTO_EMBEDDED: 7,
    SUBMIT: 8,
    IMPORT: 9,
    UNSCANNABLE: 10,
}


__all__ = [
    "EMBEDDED",
    "JAVASCRIPT",
    "LAUNCH",
    "MAX_INFLATED",
    "MAX_OBJECT_STREAMS",
    "MAX_SCAN_BYTES",
    "OPEN_ACTION",
    "REASON_CODES",
    "UNSCANNABLE",
    "is_active",
    "markers",
    "reason_of",
]
