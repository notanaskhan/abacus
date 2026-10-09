"""SPEC-020 AC-9 (TASK-035 D6): upload types judged by content, and file names kept as text."""

from __future__ import annotations

import io
import zipfile

import pytest

from abacus.modules.evidence.uploads import (
    CSV,
    DOCX,
    JPEG,
    OLE,
    PDF,
    PNG,
    XLSX,
    clean_name,
    clean_note,
    sniff,
)


def _zip(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        for name in names:
            package.writestr(name, "<x/>")
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"%PDF-1.7\n...", PDF),
        (b"\x89PNG\r\n\x1a\n....", PNG),
        (b"\xff\xd8\xff\xe0....", JPEG),
        (bytes.fromhex("d0cf11e0a1b11ae1") + b"....", OLE),
        (_zip("[Content_Types].xml", "xl/workbook.xml"), XLSX),
        (_zip("[Content_Types].xml", "word/document.xml"), DOCX),
        (b"account,amount\n1100,125000.00\n", CSV),
    ],
)
def test_ac9_allowed_types_are_recognised_by_their_bytes(content: bytes, expected: str) -> None:
    assert sniff(content) == expected


@pytest.mark.parametrize(
    "content",
    [
        b"MZ\x90\x00\x03\x00\x00\x00",  # a Windows executable
        b"PK\x03\x04not really a zip",
        _zip("evil.exe"),  # a zip, but not an Office document
        _zip("[Content_Types].xml", "ppt/presentation.xml"),  # Office, but not allowed
        b"text with a \x00 byte",
        b"\xff\xfe\x00\x00binary",
    ],
)
def test_ac9_anything_else_is_refused_whatever_its_name(content: bytes) -> None:
    assert sniff(content) is None


@pytest.mark.parametrize(
    ("raw", "kept"),
    [
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\a\\Bank statement.pdf", "Bank statement.pdf"),
        ("rec\u202eslx.exe", "recslx.exe"),  # a bidi override hiding the real extension
        ("tab\there", "tabhere"),
        ("   ", "Untitled file"),
        ("x" * 300, "x" * 200),
    ],
)
def test_ac9_file_names_are_plain_bounded_text(raw: str, kept: str) -> None:
    assert clean_name(raw) == kept


@pytest.mark.parametrize(
    ("raw", "kept"),
    [
        ("Emailed by the controller on 3 Oct", "Emailed by the controller on 3 Oct"),
        ("line\nbreak\tand\x00nul", "linebreakandnul"),
        ("   ", None),
        (None, None),
        ("x" * 600, "x" * 500),
    ],
)
def test_spec023_ac1_notes_are_plain_bounded_text(raw: str | None, kept: str | None) -> None:
    assert clean_note(raw) == kept
