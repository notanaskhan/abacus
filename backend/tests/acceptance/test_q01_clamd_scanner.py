"""Q-01-T12 / SPEC-050 AC-16 and ADR-153 (P-64): the clamd scanner, written from the spec text.

Spec: "`LocalScanner`'s archive-bomb checks run first and `ClamdScanner` streams `INSTREAM` to
`scanner.abacus.internal:3310` (`StreamMaxLength 60M`, 30 s timeout); EICAR returns `malware`; any
socket error, timeout or unexpected reply returns `unscannable`, which fails closed". ADR-153:
"Any scanner error raises unscannable"; "No file is parsed, previewed or stored as evidence until
the scanner returns clean"; the EICAR, timeout and blocked-body cases fail closed.

Public names and signatures only are taken from the code: `ClamdScanner(endpoint, *,
timeout_seconds)`, `scan(content) -> ScanResult(clean, reason)`, `LocalScanner`, `ping()`.
The protocol side is an in-process loopback clamd (`support.FakeClamd`). The tests at the end run
against a real clamd and are skipped unless `ABACUS_SCANNER_ENDPOINT` is set.
"""

from __future__ import annotations

import io
import os
import time
import zipfile

import pytest

from abacus.kernel.config import settings
from abacus.kernel.scanning import ClamdScanner, LocalScanner, ScanResult, scan

from .support import (
    EICAR,
    STREAM_MAX_LENGTH,
    FakeClamd,
    closed_endpoint,
    fails,
    use_environment,
)

CLEAN = b"%PDF-1.7 a perfectly ordinary statement, nothing to see here"
MIB = 1024 * 1024
UNSCANNABLE = ScanResult(False, "unscannable")
REAL_CLAMD = os.environ.get("ABACUS_SCANNER_ENDPOINT")  # read before the fixtures clear it


def archive_bomb() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("zeros.bin", bytes(20 * MIB))
    return buffer.getvalue()


# --- verdicts -----------------------------------------------------------------------------------


def test_ac16_clean_content_is_clean() -> None:
    with FakeClamd() as clamd:
        result = ClamdScanner(clamd.endpoint, timeout_seconds=5).scan(CLEAN)
    assert result.clean is True
    assert result.reason is None


def test_ac16_eicar_is_malware() -> None:
    with FakeClamd() as clamd:
        result = ClamdScanner(clamd.endpoint, timeout_seconds=5).scan(EICAR)
    assert result == ScanResult(False, "malware")


def test_ac16_the_content_is_streamed_with_instream_unaltered() -> None:
    content = os.urandom(300_000)  # more than one chunk
    with FakeClamd() as clamd:
        ClamdScanner(clamd.endpoint, timeout_seconds=5).scan(content)
        assert clamd.seen.commands == [b"INSTREAM"]
        assert clamd.seen.streamed == [content]


def test_ac16_empty_content_does_not_hang_or_crash() -> None:
    with FakeClamd() as clamd:
        result = ClamdScanner(clamd.endpoint, timeout_seconds=5).scan(b"")
    assert result.clean is True or result == UNSCANNABLE  # never an exception, never malware


def test_ac16_each_scan_gets_its_own_verdict() -> None:
    with FakeClamd() as clamd:
        scanner = ClamdScanner(clamd.endpoint, timeout_seconds=5)
        assert scanner.scan(CLEAN).clean is True
        assert scanner.scan(EICAR).reason == "malware"
        assert scanner.scan(CLEAN).clean is True


# --- archive bombs come first -------------------------------------------------------------------


def test_ac16_an_archive_bomb_is_refused_before_anything_is_streamed() -> None:
    bomb = archive_bomb()
    assert LocalScanner().scan(bomb) == ScanResult(False, "archive_bomb")  # the oracle
    with FakeClamd() as clamd:
        result = ClamdScanner(clamd.endpoint, timeout_seconds=5).scan(bomb)
        assert result == ScanResult(False, "archive_bomb")
        assert clamd.seen.streamed == []


def test_ac16_an_archive_bomb_is_refused_even_when_clamd_is_down() -> None:
    result = ClamdScanner(closed_endpoint(), timeout_seconds=2).scan(archive_bomb())
    assert result.clean is False
    assert result.reason == "archive_bomb"


# --- the stream limit ---------------------------------------------------------------------------


def test_ac16_content_within_the_60_mib_stream_limit_is_scanned() -> None:
    content = bytes(59 * MIB)
    with FakeClamd() as clamd:
        result = ClamdScanner(clamd.endpoint, timeout_seconds=30).scan(content)
        assert result.clean is True
        assert [len(s) for s in clamd.seen.streamed] == [len(content)]


def test_ac16_content_over_the_60_mib_stream_limit_is_unscannable() -> None:
    assert STREAM_MAX_LENGTH == 60 * MIB
    with FakeClamd() as clamd:
        result = ClamdScanner(clamd.endpoint, timeout_seconds=30).scan(bytes(61 * MIB))
    assert result == UNSCANNABLE


# --- fail closed --------------------------------------------------------------------------------


def test_ac16_a_refused_connection_is_unscannable_not_an_exception() -> None:
    assert ClamdScanner(closed_endpoint(), timeout_seconds=2).scan(CLEAN) == UNSCANNABLE


def test_ac16_an_unresolvable_host_is_unscannable() -> None:
    # `.invalid` is reserved and never resolves (RFC 6761).
    assert ClamdScanner("scanner.invalid:3310", timeout_seconds=2).scan(CLEAN) == UNSCANNABLE


def test_ac16_a_silent_scanner_times_out_as_unscannable() -> None:
    with FakeClamd(mode="silent") as clamd:
        started = time.monotonic()
        result = ClamdScanner(clamd.endpoint, timeout_seconds=1).scan(CLEAN)
        elapsed = time.monotonic() - started
    assert result == UNSCANNABLE
    assert elapsed < 5  # bounded by the timeout, not by the peer


def test_ac16_a_scanner_that_never_reads_times_out_as_unscannable() -> None:
    with FakeClamd(mode="deaf") as clamd:
        started = time.monotonic()
        result = ClamdScanner(clamd.endpoint, timeout_seconds=1).scan(os.urandom(16 * MIB))
        elapsed = time.monotonic() - started
    assert result == UNSCANNABLE
    assert elapsed < 5


def test_ac16_a_dropped_connection_is_unscannable() -> None:
    with FakeClamd(mode="close") as clamd:
        assert ClamdScanner(clamd.endpoint, timeout_seconds=5).scan(CLEAN) == UNSCANNABLE


@pytest.mark.parametrize(
    "reply",
    [
        b"",
        b"stream: lookup failure ERROR\0",
        b"INSTREAM size limit exceeded. ERROR\0",
        b"PONG\0",
        b"garbage with no terminator",
        b"\xff\xfe\x00\x01",
        b"stream: \0",
        b"stream: OKAY\0",
    ],
)
def test_ac16_an_unexpected_reply_is_unscannable(reply: bytes) -> None:
    with FakeClamd(mode="reply", reply=reply) as clamd:
        result = ClamdScanner(clamd.endpoint, timeout_seconds=5).scan(CLEAN)
    assert result == UNSCANNABLE


@pytest.mark.parametrize("reply", [b"stream: NOT OK\0", b"stream: scan error: not OK\0"])
def test_ac16_only_the_clean_verdict_is_clean(reply: bytes) -> None:
    with FakeClamd(mode="reply", reply=reply) as clamd:
        result = ClamdScanner(clamd.endpoint, timeout_seconds=5).scan(CLEAN)
    assert result == UNSCANNABLE


def test_ac16_a_scanner_that_streams_an_endless_reply_is_unscannable() -> None:
    with FakeClamd(mode="reply", reply=b"stream: OK" + b"K" * 1_000_000) as clamd:
        result = ClamdScanner(clamd.endpoint, timeout_seconds=5).scan(CLEAN)
    assert result.clean is False


@pytest.mark.parametrize("reply", [b"stream: Win.Test.Signature-1 FOUND\0", b"stream: X FOUND\0"])
def test_ac16_any_signature_hit_is_malware(reply: bytes) -> None:
    with FakeClamd(mode="reply", reply=reply) as clamd:
        result = ClamdScanner(clamd.endpoint, timeout_seconds=5).scan(CLEAN)
    assert result == ScanResult(False, "malware")


def test_ac16_nothing_but_a_clean_verdict_is_clean() -> None:
    """ADR-153 "Don't": `except ScannerError: return CLEAN`. Every failure mode above is
    not clean; this pins that none of them is, in one place."""
    failures: list[ScanResult] = []
    failures.append(ClamdScanner(closed_endpoint(), timeout_seconds=1).scan(CLEAN))
    for mode, reply in (("close", b""), ("reply", b"?"), ("reply", b"")):
        with FakeClamd(mode=mode, reply=reply) as clamd:
            failures.append(ClamdScanner(clamd.endpoint, timeout_seconds=2).scan(CLEAN))
    assert all(result.clean is False for result in failures)


# --- readiness (/readyz: "scanner reachable") ---------------------------------------------------


def test_ac24_ping_succeeds_against_a_live_scanner() -> None:
    with FakeClamd() as clamd:
        ClamdScanner(clamd.endpoint, timeout_seconds=5).ping()
        assert clamd.seen.commands == [b"PING"]


def test_ac24_ping_fails_when_the_scanner_is_unreachable() -> None:
    fails(ClamdScanner(closed_endpoint(), timeout_seconds=2).ping)


@pytest.mark.parametrize("reply", [b"", b"NOPE\0", b"stream: OK\0"])
def test_ac24_ping_fails_when_the_peer_is_not_clamd(reply: bytes) -> None:
    with FakeClamd(ping_reply=reply) as clamd:
        fails(ClamdScanner(clamd.endpoint, timeout_seconds=2).ping)


# --- configuration ------------------------------------------------------------------------------


def test_ac16_the_default_timeout_is_30_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    use_environment(monkeypatch, {"ABACUS_ENVIRONMENT": "local"})
    assert settings().scanner_timeout_seconds == 30


def test_ac16_a_configured_endpoint_selects_the_clamd_scanner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with FakeClamd() as clamd:
        use_environment(
            monkeypatch,
            {"ABACUS_ENVIRONMENT": "local", "ABACUS_SCANNER_ENDPOINT": clamd.endpoint},
        )
        assert scan(EICAR) == ScanResult(False, "malware")
        assert scan(CLEAN).clean is True
        assert clamd.seen.commands == [b"INSTREAM", b"INSTREAM"]


def test_ac16_a_configured_endpoint_that_is_down_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_environment(
        monkeypatch,
        {
            "ABACUS_ENVIRONMENT": "local",
            "ABACUS_SCANNER_ENDPOINT": closed_endpoint(),
            "ABACUS_SCANNER_TIMEOUT_SECONDS": "2",
        },
    )
    assert scan(CLEAN) == UNSCANNABLE  # no fall back to the local scanner's "clean"


def test_ac16_the_local_scanner_still_refuses_eicar_and_bombs() -> None:
    assert LocalScanner().scan(EICAR) == ScanResult(False, "malware")
    assert LocalScanner().scan(archive_bomb()) == ScanResult(False, "archive_bomb")
    assert LocalScanner().scan(CLEAN).clean is True


# --- against a real clamd (skipped unless ABACUS_SCANNER_ENDPOINT is set) -----------------------

real_clamd = pytest.mark.skipif(
    not REAL_CLAMD,
    reason="needs a real clamd: set ABACUS_SCANNER_ENDPOINT=host:port (TASK-346 #346)",
)


@real_clamd
def test_ac16_real_clamd_refuses_eicar() -> None:
    assert REAL_CLAMD is not None
    assert ClamdScanner(REAL_CLAMD, timeout_seconds=30).scan(EICAR) == ScanResult(False, "malware")


@real_clamd
def test_ac16_real_clamd_passes_clean_content() -> None:
    assert REAL_CLAMD is not None
    assert ClamdScanner(REAL_CLAMD, timeout_seconds=30).scan(CLEAN).clean is True


@real_clamd
def test_ac16_real_clamd_refuses_an_oversize_stream() -> None:
    assert REAL_CLAMD is not None
    result = ClamdScanner(REAL_CLAMD, timeout_seconds=60).scan(bytes(61 * MIB))
    assert result == UNSCANNABLE


@real_clamd
def test_ac24_real_clamd_answers_ping() -> None:
    assert REAL_CLAMD is not None
    ClamdScanner(REAL_CLAMD, timeout_seconds=30).ping()
