"""Malware scanning before any parsing (ADR-110; SPEC-028, TASK-052 D3).

Every uploaded file is scanned before anything parses or previews it. A file that isn't
scanned clean is never parsed. `scan(content)` asks the configured scanner. In staging and
production that is `ClamdScanner`, ClamAV's `clamd` as an internal service (ADR-153), selected by
`scanner_endpoint`. Locally and in tests, `LocalScanner` stands in: it refuses the standard EICAR
test signature and archive bombs (a zip container, such as XLSX, whose expanded size or
compression ratio passes a limit), and passes everything else. Outside synthetic environments,
with no scanner configured, scanning fails closed.
"""

from __future__ import annotations

import hashlib
import io
import re
import socket
import struct
import time
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


# F-04-T18 (F-04.25): a scenario artefact may carry an injected verdict, so journeys and tests see
# every outcome a real scanner gives. Keyed by the content's SHA-256. Synthetic environments only.
InjectedVerdict = Literal["infected", "error", "timeout", "pending"]
_VERDICTS: Final[frozenset[str]] = frozenset({"infected", "error", "timeout", "pending"})
_PENDING: Final = re.compile(r"pending\((\d+(?:\.\d+)?)s\)")
MAX_INJECTED_DELAY_SECONDS: Final = 10.0


@dataclass(frozen=True)
class _Injected:
    verdict: InjectedVerdict
    delay_seconds: float


_injected: dict[str, _Injected] = {}


class InjectionRefused(RuntimeError):
    """Verdict injection outside a synthetic environment: the real scanner decides there."""


def inject_verdict(
    content_sha256: str, verdict: InjectedVerdict, *, delay_seconds: float = 0.0
) -> None:
    """Make `LocalScanner` answer `verdict` for this content. `pending` and `timeout` wait
    `delay_seconds` first (the scanning state; scans run off the event loop). Refused outside
    the synthetic environments, so never in staging or production."""
    if settings().environment not in SYNTHETIC_ENVIRONMENTS:
        raise InjectionRefused("scanner verdict injection is for synthetic environments only")
    if verdict not in _VERDICTS:
        raise ValueError(f"unknown scanner verdict {verdict!r}")
    if not (0.0 <= delay_seconds <= MAX_INJECTED_DELAY_SECONDS):
        raise ValueError("an injected delay is between 0 and 10 seconds")
    _injected[content_sha256] = _Injected(verdict, delay_seconds)


def inject_marked(content_sha256: str, mark: str) -> None:
    """A scenario artefact's `scan:` mark: `infected`, `error`, `timeout` or `pending(2s)`."""
    pending = _PENDING.fullmatch(mark)
    if pending is not None:
        inject_verdict(content_sha256, "pending", delay_seconds=float(pending.group(1)))
    elif mark in ("infected", "error", "timeout"):
        inject_verdict(content_sha256, mark)
    else:
        raise ValueError(f"unknown scan mark {mark!r}")


def forget_injected() -> None:
    _injected.clear()


class LocalScanner:
    """Local and test only: the EICAR signature and archive bombs are refused, as before; then
    an injected verdict, if the content has one (F-04-T18). EICAR and bombs are checked first,
    so no injection can clear them."""

    def scan(self, content: bytes) -> ScanResult:
        if EICAR in content:
            return ScanResult(False, "malware")
        if content[:4] == b"PK\x03\x04":
            local = _zip_check(content)
            if not local.clean:
                return local
        injected = _injected.get(hashlib.sha256(content).hexdigest()) if _injected else None
        if injected is None:
            return ScanResult(True)
        if injected.delay_seconds:
            time.sleep(injected.delay_seconds)
        if injected.verdict == "infected":
            return ScanResult(False, "malware")
        if injected.verdict in ("error", "timeout"):
            return ScanResult(False, "unscannable")  # as ClamdScanner answers both
        return ScanResult(True)  # pending: the scanning state, then clean


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


STREAM_MAX_BYTES: Final = 60 * 1024 * 1024  # clamd's StreamMaxLength (ADR-153)
_CHUNK: Final = 64 * 1024
_MAX_REPLY: Final = 4096


class ClamdScanner:
    """ClamAV `clamd` over its `INSTREAM` command, on plaintext in the API before sealing
    (ADR-153, SPEC-050 AC-16). The archive-bomb checks of `LocalScanner` run first, so a bomb is
    never streamed. EICAR and any signature clamd finds are `malware`. Anything else that is not
    a clean verdict is `unscannable`, which fails closed: a socket error, a timeout, a reply that
    isn't `OK` or `FOUND`, or a stream over 60 MB.

    Blocking (a socket), so callers run it off the event loop, as `uploads.screened` does. One
    connection per scan; `timeout_seconds` bounds the whole exchange, not each read."""

    def __init__(
        self,
        endpoint: str,
        *,
        timeout_seconds: float = 30.0,
        max_bytes: int = STREAM_MAX_BYTES,
    ) -> None:
        host, _, port = endpoint.rpartition(":")
        if not host or not port.isdigit():
            raise ValueError("scanner endpoint is host:port")
        self._address = (host, int(port))
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes

    def scan(self, content: bytes) -> ScanResult:
        if content[:4] == b"PK\x03\x04":
            local = _zip_check(content)
            if not local.clean:
                return local
        if len(content) > self._max_bytes:
            return ScanResult(False, "unscannable")
        try:
            reply = self._instream(content)
        except (OSError, ValueError):  # refused, reset, timed out (socket.timeout is an OSError)
            return ScanResult(False, "unscannable")
        # Only clamd's exact clean verdict is clean (AC-16, ADR-153): `stream: NOT OK` and other
        # replies that merely end in OK are unscannable. `_reply` has already dropped `stream: `.
        if reply == b"OK":
            return ScanResult(True)
        if reply.endswith(b" FOUND"):
            return ScanResult(False, "malware")
        return ScanResult(False, "unscannable")

    def ping(self) -> None:
        """Readiness (`/readyz`): clamd answers PING with PONG. Raises if it doesn't."""
        deadline = time.monotonic() + min(self._timeout, 5.0)
        with self._connect(deadline) as sock:
            sock.sendall(b"zPING\0")
            if self._reply(sock, deadline) != b"PONG":
                raise ConnectionError("the scanner did not answer PING")

    def _connect(self, deadline: float) -> socket.socket:
        return socket.create_connection(self._address, timeout=_remaining(deadline))

    def _instream(self, content: bytes) -> bytes:
        deadline = time.monotonic() + self._timeout
        with self._connect(deadline) as sock:
            sock.sendall(b"zINSTREAM\0")
            for start in range(0, len(content), _CHUNK):
                chunk = content[start : start + _CHUNK]
                sock.settimeout(_remaining(deadline))
                sock.sendall(struct.pack(">I", len(chunk)) + chunk)
            sock.settimeout(_remaining(deadline))
            sock.sendall(struct.pack(">I", 0))
            return self._reply(sock, deadline)

    def _reply(self, sock: socket.socket, deadline: float) -> bytes:
        """The reply up to its terminating NUL (or newline), without the `stream:` prefix."""
        reply = bytearray()
        while len(reply) < _MAX_REPLY:
            sock.settimeout(_remaining(deadline))
            chunk = sock.recv(1024)
            if not chunk:
                break
            reply += chunk
            if b"\0" in chunk or b"\n" in chunk:
                break
        return bytes(reply).strip(b"\0\n ").rpartition(b": ")[2]


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError("the scanner did not answer in time")
    return left


_scanner: Scanner | None = None


def configure_scanner(scanner: Scanner | None) -> None:
    """Deployments (and tests) install the real scanner; None restores the default."""
    global _scanner
    _scanner = scanner


def scanner() -> Scanner:
    """The scanner in use: one installed by `configure_scanner`; else `ClamdScanner` when
    `scanner_endpoint` is set (staging and production require it); else the local scanner in
    synthetic environments. Otherwise there is none, and scanning fails closed."""
    if _scanner is not None:
        return _scanner
    s = settings()
    if s.scanner_endpoint is not None:
        return ClamdScanner(s.scanner_endpoint, timeout_seconds=s.scanner_timeout_seconds)
    if s.environment in SYNTHETIC_ENVIRONMENTS:
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
    "STREAM_MAX_BYTES",
    "ClamdScanner",
    "InjectedVerdict",
    "InjectionRefused",
    "LocalScanner",
    "Pingable",
    "ScanResult",
    "Scanner",
    "check_scanner",
    "configure_scanner",
    "forget_injected",
    "inject_marked",
    "inject_verdict",
    "scan",
    "scanner",
]
