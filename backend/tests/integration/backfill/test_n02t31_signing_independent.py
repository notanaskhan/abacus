# ac-test-author: ayushkbhatia
"""N-02-T31 (TASK-2335; ADR-078): independent AC tests for N-02-T23, T24 and T25, written from
the task row and N-02 §9, not from the implementation.

Acceptance (the task row): "The suite passes and fails if Jonah's principal can fetch Claire's
signing session."

- **INV-4:** only the named signer reaches a session; Jonah's principal gets 404 on Claire's
  envelope, her session and her return.
- **Spouses never act for each other:** one spouse's ERSD acceptance and session never count for
  the other's signer row.
- **One-time, expiring sessions:** a replay answers the same session while it is open; a new
  session abandons the old one; an expired or abandoned session is never reopened.
- **Return parameters are never trusted:** the return answers from the provider's poll alone.
- **date_as_of in the firm's time zone:** refused while the firm's own date is earlier, even
  when the UTC date has reached it.
- **C7 v1.1 (T25):** the superseded marker is the system's alone; retention only ever extends.

Boundary: HTTP through `create_app()` against the fake provider, as T23's suite drives it (its
world-building helpers are reused; its assertions are not); the C7 functions through
`signatures.api` with the principal each rule names.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Final, cast
from zoneinfo import ZoneInfo

import pytest

from abacus.kernel.clock import frozen
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import records, storage
from abacus.modules.signatures import status_poll
from abacus.modules.signatures.api import (
    RetentionNotExtended,
    SystemOnly,
    configure_provider,
    extend_retention,
    supersede_for_amount_change,
)
from abacus_tools.fakes.esign import FakeEsign

from .support import Net
from .test_n02t23_portal_envelopes import (  # T23's world-building helpers, shared harness
    BASE,
    Body,
    World,
    _consent,  # pyright: ignore[reportPrivateUsage] -- T23's helper
    _ok,  # pyright: ignore[reportPrivateUsage] -- T23's helper
    _refused,  # pyright: ignore[reportPrivateUsage] -- T23's helper
    _send,  # pyright: ignore[reportPrivateUsage] -- T23's helper
    _signer,  # pyright: ignore[reportPrivateUsage] -- T23's helper
    _world,  # pyright: ignore[reportPrivateUsage] -- T23's helper
)

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
EVIDENCE: Final = "n02t31-evidence"
RECORDS: Final = "n02t31-records"
MASTER: Final = b"n02t31-independent-master-key-012345678"
CHICAGO: Final = ZoneInfo("America/Chicago")


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    """This suite's own buckets (T23's module creates its own)."""
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    for bucket in (EVIDENCE, RECORDS):
        client.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture
def fake(raw: S3Client, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeEsign]:
    settings.cache_clear()
    forget_flags()
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, EVIDENCE)
    records.configure_records(raw, RECORDS)
    provider = FakeEsign()
    configure_provider(provider)

    async def hinted(tenant_id: uuid.UUID, envelope_id: uuid.UUID) -> None:
        del tenant_id, envelope_id  # no worker: the routes' own poll is the one under test

    monkeypatch.setattr(status_poll, "hint_envelope", hinted)
    yield provider
    configure_provider(None)
    records.reset_records()
    storage.reset_storage()
    reset_key_service()
    forget_flags()


async def _session(w: World, envelope: uuid.UUID, who: object, key: str) -> Body:
    response = await w.net.http.post(
        f"{BASE}/{envelope}/signing-session",
        headers=w.net.headers(who) | {"Idempotency-Key": key},  # type: ignore[arg-type]  # a Person
    )
    assert response.status_code == 200, response.text
    return cast(Body, response.json())


# --- INV-4: the named signer only --------------------------------------------------------------


async def test_ac_jonahs_principal_cannot_fetch_claires_signing_session(
    net: Net, fake: FakeEsign
) -> None:
    w = await _world(net)
    claire = await _signer(w, "Claire Feld")
    jonah = await _signer(w, "Jonah Feld")
    envelope, _ = await _send(w, [claire])  # Claire's alone
    await _consent(w, envelope, claire)
    claires = await _ok(w, "POST", f"{BASE}/{envelope}/signing-session", claire)

    for method, path in (
        ("GET", f"{BASE}/{envelope}"),
        ("GET", f"{BASE}/{envelope}/signing-session/{claires['session_id']}/return"),
        ("GET", f"{BASE}/{envelope}/download"),
    ):
        got = await net.http.request(method, path, headers=net.headers(jonah))
        assert got.status_code == 404, (path, got.text)
    status, _code = await _refused(w, f"{BASE}/{envelope}/signing-session", jonah)
    assert status == 404
    listed = await _ok(w, "GET", BASE, jonah)
    assert listed["items"] == []
    sessions = await net.seed.rows(
        "SELECT principal_id FROM signing_sessions WHERE envelope_id = $1", envelope
    )
    assert {r["principal_id"] for r in sessions} == {claire.user_id}


# --- Spouses never act for each other ------------------------------------------------------------


async def test_ac_one_spouses_consent_and_session_never_count_for_the_other(
    net: Net, fake: FakeEsign
) -> None:
    w = await _world(net)
    claire = await _signer(w, "Claire Feld")
    jonah = await _signer(w, "Jonah Feld")
    envelope, (claire_signer, jonah_signer) = await _send(
        w, [claire, jonah], signer_order="parallel"
    )
    await _consent(w, envelope, jonah)
    # Jonah's ERSD acceptance is his row's: Claire still has to accept for herself.
    assert await _refused(w, f"{BASE}/{envelope}/signing-session", claire) == (
        409,
        "esign_consent_required",
    )
    view = await _ok(w, "GET", f"{BASE}/{envelope}", claire)
    assert view["esign_consent_needed"] is True
    jonahs = await _session(w, envelope, jonah, uuid.uuid4().hex)
    # Jonah's session never reads as Claire's, and never moves her row.
    got = await net.http.get(
        f"{BASE}/{envelope}/signing-session/{jonahs['session_id']}/return",
        headers=net.headers(claire),
    )
    assert got.status_code == 404, got.text
    accepted = await net.seed.rows(
        "SELECT signer_id FROM esign_acceptances WHERE signer_id = ANY($1::uuid[])",
        [claire_signer, jonah_signer],
    )
    assert {r["signer_id"] for r in accepted} == {jonah_signer}


# --- One-time, expiring sessions -----------------------------------------------------------------


async def test_ac_a_session_is_one_time_and_expires(net: Net, fake: FakeEsign) -> None:
    w = await _world(net)
    owen = await _signer(w, "Owen Calder")
    envelope, _ = await _send(w, [owen])
    await _consent(w, envelope, owen)
    first_key = uuid.uuid4().hex
    first = await _session(w, envelope, owen, first_key)
    issued = datetime.fromisoformat(str(first["expires_at"]))
    assert issued - datetime.now(UTC) <= timedelta(minutes=5)  # five minutes at most

    replay = await _session(w, envelope, owen, first_key)
    assert replay["session_id"] == first["session_id"]  # a replay answers the same, while open

    second = await _session(w, envelope, owen, uuid.uuid4().hex)
    assert second["session_id"] != first["session_id"]
    state = await net.seed.value(
        "SELECT state FROM signing_sessions WHERE id = $1", uuid.UUID(str(first["session_id"]))
    )
    assert state == "abandoned"  # a new session replaces the old one
    assert await _refused(w, f"{BASE}/{envelope}/signing-session", owen, key=first_key) == (
        409,
        "session_not_open",
    )

    second_key = uuid.uuid4().hex
    third = await _session(w, envelope, owen, second_key)
    await net.seed.run_untriggered_many(
        [
            (
                # Issued ten minutes ago and lapsed five later (the CHECK keeps the window).
                "UPDATE signing_sessions SET issued_at = now() - interval '10 minutes', "
                "expires_at = now() - interval '5 minutes' WHERE id = $1",
                (uuid.UUID(str(third["session_id"])),),
            )
        ]
    )
    assert await _refused(w, f"{BASE}/{envelope}/signing-session", owen, key=second_key) == (
        409,
        "session_not_open",
    )


# --- Return parameters are never trusted ---------------------------------------------------------


async def test_ac_the_return_answers_from_the_provider_not_from_its_parameters(
    net: Net, fake: FakeEsign
) -> None:
    w = await _world(net)
    owen = await _signer(w, "Owen Calder")
    envelope, (signer,) = await _send(w, [owen])
    await _consent(w, envelope, owen)
    made = await _session(w, envelope, owen, uuid.uuid4().hex)
    back = f"{BASE}/{envelope}/signing-session/{made['session_id']}/return"
    forged = (
        f"{back}?status=completed&event=signing_complete&outcome=signed"
        f"&signer_id={signer}&envelope_status=completed"
    )
    got = await _ok(w, "GET", forged, owen)
    assert got["outcome"] is None
    assert got["row"]["status"] == "sent" and got["row"]["my_status"] == "pending"
    status = await net.seed.value("SELECT status FROM envelope_signers WHERE id = $1", signer)
    assert status != "signed"


# --- date_as_of in the firm's time zone ----------------------------------------------------------


async def test_ac_date_as_of_is_the_firms_date_in_its_own_zone(net: Net, fake: FakeEsign) -> None:
    w = await _world(net)
    await net.seed.run(
        "UPDATE firms SET time_zone = 'America/Chicago' WHERE tenant_id = $1", w.tenant
    )
    owen = await _signer(w, "Owen Calder")
    today_utc = datetime.now(UTC).date()
    envelope, _ = await _send(w, [owen], date_as_of=today_utc)
    await _consent(w, envelope, owen)
    path = f"{BASE}/{envelope}/signing-session"

    # 03:00 UTC on the day is still the evening before in Chicago: the firm's date is earlier.
    evening_before = datetime(today_utc.year, today_utc.month, today_utc.day, 3, tzinfo=UTC)
    assert evening_before.astimezone(CHICAGO).date() < today_utc
    with frozen(evening_before):
        assert await _refused(w, path, owen) == (409, "before_date_as_of")
    # 07:00 UTC is the same date in Chicago: the session opens.
    morning = datetime(today_utc.year, today_utc.month, today_utc.day, 7, tzinfo=UTC)
    assert morning.astimezone(CHICAGO).date() == today_utc
    with frozen(morning):
        opened = await _session(w, envelope, owen, uuid.uuid4().hex)
    assert opened["session_id"]


# --- C7 v1.1: the superseded marker and retention ------------------------------------------------


async def test_ac_only_the_system_marks_an_envelope_superseded(net: Net, fake: FakeEsign) -> None:
    w = await _world(net)
    owen = await _signer(w, "Owen Calder")
    envelope, _ = await _send(w, [owen])
    for kind in ("human", "agent", "support"):
        with pytest.raises(SystemOnly):
            await supersede_for_amount_change(
                TenantContext(w.tenant, kind, f"{kind}:test"), envelope, "binding-1"
            )
    system = TenantContext(w.tenant, "system", "test.n02t31")
    assert await supersede_for_amount_change(system, envelope, "binding-1") is True
    assert await supersede_for_amount_change(system, envelope, "binding-1") is False  # once


async def test_ac_retention_only_ever_extends(net: Net, fake: FakeEsign) -> None:
    w = await _world(net)
    owen = await _signer(w, "Owen Calder")
    envelope, _ = await _send(w, [owen])
    system = TenantContext(w.tenant, "system", "test.n02t31")
    later = date.today() + timedelta(days=3650)
    held = await extend_retention(system, envelope, later)
    assert held >= later
    with pytest.raises(RetentionNotExtended):
        await extend_retention(system, envelope, held - timedelta(days=1))
    assert await extend_retention(system, envelope, held + timedelta(days=1)) == held + timedelta(
        days=1
    )
