"""Malware scanning before any parsing (ADR-110; SPEC-028, TASK-052 D3).

Every uploaded file is scanned before anything parses or previews it. A file that isn't
scanned clean is never parsed. `scan(content)` asks the configured scanner; the real one is
chosen with staging (TASK-014). Locally and in tests, `LocalScanner` stands in: it refuses the
standard EICAR test signature and archive bombs (a zip container, such as XLSX, whose expanded
size or compression ratio passes a limit), and passes everything else. Outside synthetic
environments, with no scanner configured, scanning fails closed.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from typing import Final, Literal, Protocol, runtime_checkable

from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings

# The standard anti-malware test file (EICAR): every scanner detects it; harmless by design.
EICAR: Final = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
MAX_EXPANDED_BYTES: Final = 200 * 1024 * 1024
MAX_RATIO: Final = 100
MAX_ENTRIES: Final = 10_000

Reason = Literal["malware", "archive_bomb", "unscannable"]


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    reason: Reason | None = None


class Scanner(Protocol):
    def scan(self, content: bytes) -> ScanResult: ...


@runtime_checkable
class Pingable(Protocol):
    """A scanner that can say whether its service is reachable (clamd answers PING)."""

    def ping(self) -> None: ...


class LocalScanner:
    """Local and test only: the EICAR signature and archive bombs are refused."""

    def scan(self, content: bytes) -> ScanResult:
        if EICAR in content:
            return ScanResult(False, "malware")
        if content[:4] == b"PK\x03\x04":
            return _zip_check(content)
        return ScanResult(True)


def _zip_check(content: bytes) -> ScanResult:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ENTRIES:
                return ScanResult(False, "archive_bomb")
            expanded = sum(e.file_size for e in entries)
            compressed = max(1, sum(e.compress_size for e in entries))
            # Sizes first: nothing is expanded until the archive is known not to be a bomb.
            if expanded > MAX_EXPANDED_BYTES or expanded / compressed > MAX_RATIO:
                return ScanResult(False, "archive_bomb")
            small = [e for e in entries if e.file_size < 1024 * 1024]
            if any(EICAR in archive.read(e) for e in small):
                return ScanResult(False, "malware")
    except (zipfile.BadZipFile, OSError, ValueError):
        return ScanResult(False, "unscannable")
    return ScanResult(True)


_scanner: Scanner | None = None


def configure_scanner(scanner: Scanner | None) -> None:
    """Deployments (and tests) install the real scanner; None restores the default."""
    global _scanner
    _scanner = scanner


def scanner() -> Scanner:
    if _scanner is not None:
        return _scanner
    if settings().environment in SYNTHETIC_ENVIRONMENTS:
        return LocalScanner()
    raise RuntimeError("no malware scanner configured for this environment (ADR-110)")


def scan(content: bytes) -> ScanResult:
    return scanner().scan(content)


def check_scanner() -> None:
    """Readiness (`/readyz`): a scanner is configured and, if it is a service, reachable.
    Raises if not."""
    configured = scanner()
    if isinstance(configured, Pingable):
        configured.ping()


__all__ = [
    "EICAR",
    "LocalScanner",
    "Pingable",
    "ScanResult",
    "Scanner",
    "check_scanner",
    "configure_scanner",
    "scan",
    "scanner",
]
