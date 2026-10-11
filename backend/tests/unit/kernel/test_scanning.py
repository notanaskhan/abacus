"""ADR-110 (SPEC-028; TASK-052 D3): the local scanner refuses the EICAR signature and archive
bombs before anything expands, and scanning fails closed outside synthetic environments."""

from __future__ import annotations

import io
import zipfile

import pytest

from abacus.kernel import scanning
from abacus.kernel.scanning import EICAR, LocalScanner, ScanResult, configure_scanner, scan


def _zip(entries: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return out.getvalue()


def test_adr110_plain_content_is_clean() -> None:
    assert LocalScanner().scan(b"Account,Debit,Credit\n") == ScanResult(True)


def test_adr110_the_eicar_signature_is_malware() -> None:
    assert LocalScanner().scan(b"prefix " + EICAR) == ScanResult(False, "malware")


def test_adr110_eicar_inside_a_zip_is_malware() -> None:
    assert LocalScanner().scan(_zip({"a.txt": EICAR})) == ScanResult(False, "malware")


def test_adr110_a_highly_compressed_zip_is_an_archive_bomb() -> None:
    bomb = _zip({"zeros.bin": b"\0" * (5 * 1024 * 1024)})
    assert LocalScanner().scan(bomb) == ScanResult(False, "archive_bomb")


def test_adr110_too_many_entries_is_an_archive_bomb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scanning, "MAX_ENTRIES", 3)
    many = _zip({f"{n}.txt": b"x" for n in range(5)})
    assert LocalScanner().scan(many) == ScanResult(False, "archive_bomb")


def test_adr110_a_broken_zip_is_unscannable() -> None:
    assert LocalScanner().scan(b"PK\x03\x04 not really") == ScanResult(False, "unscannable")


def test_adr110_a_normal_zip_is_clean() -> None:
    assert LocalScanner().scan(_zip({"sheet.xml": b"<x>1, 2, 3</x>" * 10})).clean


def test_adr110_a_configured_scanner_is_used() -> None:
    class Refuses:
        def scan(self, content: bytes) -> ScanResult:
            return ScanResult(False, "malware")

    configure_scanner(Refuses())
    try:
        assert scan(b"anything") == ScanResult(False, "malware")
    finally:
        configure_scanner(None)


def test_adr110_no_scanner_outside_synthetic_environments_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Production:
        environment = "production"

    monkeypatch.setattr(scanning, "settings", lambda: Production())
    with pytest.raises(RuntimeError):
        scan(b"anything")
