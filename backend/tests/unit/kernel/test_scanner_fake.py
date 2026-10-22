"""F-04-T18 (F-04.25): "Scenario artefacts yield infected, error, timeout or pending verdicts;
EICAR and zip-bomb checks unchanged", and injection is refused outside synthetic environments."""

from __future__ import annotations

import hashlib
import io
import time
import zipfile
from collections.abc import Iterator
from types import SimpleNamespace

import pytest

from abacus.kernel import scanning
from abacus.kernel.scanning import (
    EICAR,
    InjectionRefused,
    LocalScanner,
    ScanResult,
    forget_injected,
    inject_marked,
    inject_verdict,
)

DOC = b"%PDF-1.7 Northwind 401(k) Plan certified trust report"
SHA = hashlib.sha256(DOC).hexdigest()


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    forget_injected()
    yield
    forget_injected()


@pytest.mark.parametrize(
    ("mark", "expected"),
    [
        ("infected", ScanResult(False, "malware")),
        ("error", ScanResult(False, "unscannable")),
        ("timeout", ScanResult(False, "unscannable")),
        ("pending(0.2s)", ScanResult(True)),
    ],
)
def test_a_marked_artefact_gets_its_injected_verdict(mark: str, expected: ScanResult) -> None:
    inject_marked(SHA, mark)
    assert LocalScanner().scan(DOC) == expected
    assert LocalScanner().scan(DOC + b" other") == ScanResult(True)  # only that content


def test_pending_shows_the_scanning_state_before_it_clears() -> None:
    inject_marked(SHA, "pending(0.2s)")
    started = time.monotonic()
    assert LocalScanner().scan(DOC).clean
    assert time.monotonic() - started >= 0.2


def test_no_injection_can_clear_eicar_or_an_archive_bomb() -> None:
    malware = DOC + EICAR
    inject_verdict(hashlib.sha256(malware).hexdigest(), "pending")
    assert LocalScanner().scan(malware) == ScanResult(False, "malware")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("big.txt", b"0" * 50_000_000)
    bomb = buffer.getvalue()
    inject_verdict(hashlib.sha256(bomb).hexdigest(), "pending")
    assert LocalScanner().scan(bomb) == ScanResult(False, "archive_bomb")


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_injection_is_refused_outside_synthetic_environments(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setattr(scanning, "settings", lambda: SimpleNamespace(environment=environment))
    with pytest.raises(InjectionRefused):
        inject_verdict(SHA, "infected")
    with pytest.raises(InjectionRefused):
        inject_marked(SHA, "pending(2s)")


def test_unknown_marks_and_long_delays_are_refused() -> None:
    with pytest.raises(ValueError, match="unknown scan mark"):
        inject_marked(SHA, "quarantined")
    with pytest.raises(ValueError, match="between 0 and 10"):
        inject_marked(SHA, "pending(60s)")
