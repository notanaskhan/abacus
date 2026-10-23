"""P-08-T06: the portal identity provider port's contract (DEC-155). Every implementation passes
the same tests: the in-memory provider always, WorkOS staging when `ABACUS_TEST_WORKOS_API_KEY` and
`ABACUS_TEST_WORKOS_CLIENT_ID` are set (the persona users live on the sink domain), and F-04-T27's
WorkOS fake when it lands. No code path sends a client a WorkOS-branded email: Magic Auth is never
called, and sign-in codes are the portal's own."""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from abacus.kernel.clock import system_now
from abacus.modules.identity import portal_idp as port
from abacus.modules.identity.portal_idp import (
    InMemoryPortalIdp,
    PortalIdp,
    PortalIdpUnavailable,
    WorkOsPortalIdp,
    email_code_matches,
    issue_email_code,
    totp_at,
)

SRC = Path(port.__file__).parents[2]  # src/abacus
SINK = os.environ.get("ABACUS_TEST_WORKOS_SINK_DOMAIN", "sink.example.test")


def _workos() -> PortalIdp:
    return WorkOsPortalIdp(
        api_key=os.environ["ABACUS_TEST_WORKOS_API_KEY"],
        client_id=os.environ["ABACUS_TEST_WORKOS_CLIENT_ID"],
    )


# WorkOS staging joins only where its test credentials are present (a CI job or a person's
# shell), so the suite never needs a skip.
PROVIDERS = ["memory", *(["workos"] if os.environ.get("ABACUS_TEST_WORKOS_API_KEY") else [])]


@pytest.fixture(params=PROVIDERS)
async def idp(request: pytest.FixtureRequest) -> AsyncIterator[PortalIdp]:
    yield InMemoryPortalIdp() if request.param == "memory" else _workos()


def _email() -> str:
    return f"portal-contract-{uuid.uuid4().hex[:10]}@{SINK}"


async def test_t06_upsert_is_idempotent_and_ignores_case(idp: PortalIdp) -> None:
    email = _email()
    first = await idp.upsert_user(email, name="Claire Feld")
    assert await idp.upsert_user(email.upper()) == first


async def test_t06_a_totp_factor_enrols_under_the_firms_name(idp: PortalIdp) -> None:
    user = await idp.upsert_user(_email())
    enrolment = await idp.enrol_totp(user, issuer="Brightwater Hale", account="claire")
    assert enrolment.factor_id and enrolment.secret
    assert enrolment.otpauth_uri.startswith("otpauth://totp/")
    assert "Brightwater" in enrolment.otpauth_uri
    assert "accrued" not in enrolment.otpauth_uri.casefold()
    with pytest.raises(ValueError, match="display name"):
        await idp.enrol_totp(user, issuer="Accrued", account="claire")


async def test_t06_a_challenge_verifies_the_current_code_once(idp: PortalIdp) -> None:
    user = await idp.upsert_user(_email())
    enrolment = await idp.enrol_totp(user, issuer="Brightwater Hale", account="claire")
    challenge = await idp.challenge(enrolment.factor_id)
    code = totp_at(enrolment.secret, system_now().timestamp())
    assert await idp.verify(challenge, code)
    again = await idp.challenge(enrolment.factor_id)
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    assert not await idp.verify(again, wrong)


async def test_t06_a_removed_factor_no_longer_verifies(idp: PortalIdp) -> None:
    user = await idp.upsert_user(_email())
    enrolment = await idp.enrol_totp(user, issuer="Brightwater Hale", account="claire")
    await idp.remove_factor(enrolment.factor_id)
    await idp.remove_factor(enrolment.factor_id)  # gone either way
    with pytest.raises(PortalIdpUnavailable):
        await idp.challenge(enrolment.factor_id)


# --- in-memory only ----------------------------------------------------------------------------


async def test_t06_the_in_memory_challenge_is_single_use_and_drift_tolerant() -> None:
    idp = InMemoryPortalIdp(now=1_800_000_000.0)
    user = await idp.upsert_user(_email())
    enrolment = await idp.enrol_totp(user, issuer="Brightwater Hale", account="claire")
    challenge = await idp.challenge(enrolment.factor_id)
    previous_step = totp_at(enrolment.secret, 1_800_000_000.0 - 30)
    assert await idp.verify(challenge, previous_step)
    assert not await idp.verify(challenge, previous_step)  # spent
    late = await idp.challenge(enrolment.factor_id)
    assert not await idp.verify(late, totp_at(enrolment.secret, 1_800_000_000.0 - 90))


def test_t06_totp_matches_rfc_6238() -> None:
    # RFC 6238 appendix B, SHA-1 secret "12345678901234567890", truncated to six digits.
    rfc_key = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp_at(rfc_key, 59) == "287082"
    assert totp_at(rfc_key, 1111111109) == "081804"
    assert totp_at(rfc_key, 2000000000) == "279037"


async def test_t06_an_unavailable_provider_raises_the_ports_error() -> None:
    idp = InMemoryPortalIdp(unavailable=True)
    with pytest.raises(PortalIdpUnavailable):
        await idp.upsert_user(_email())


# --- own email codes ---------------------------------------------------------------------------


def test_t06_an_email_code_is_six_digits_and_only_its_hash_is_kept() -> None:
    issued = issue_email_code()
    assert re.fullmatch(r"[0-9]{6}", issued.code)
    assert issued.code.encode() not in issued.digest + issued.salt
    assert email_code_matches(issued.salt, issued.digest, issued.code)
    other = f"{(int(issued.code) + 1) % 1_000_000:06d}"
    assert not email_code_matches(issued.salt, issued.digest, other)
    for junk in ("", "12345", "1234567", "abcdef", " " + issued.code):
        assert not email_code_matches(issued.salt, issued.digest, junk)


def test_t06_two_codes_never_share_a_salt() -> None:
    assert issue_email_code().salt != issue_email_code().salt


def test_t06_no_code_path_calls_workos_magic_auth() -> None:
    """WorkOS emails its own branded code from Magic Auth; the portal never asks it to (R1)."""
    calls = [
        path.relative_to(SRC)
        for path in SRC.rglob("*.py")
        if re.search(
            r"\b(create_magic_auth|authenticate_with_magic_auth|magic_auth)\b", path.read_text()
        )
    ]
    assert calls == []


def test_t06_only_tests_and_local_runs_may_swap_the_provider() -> None:
    port.configure_portal_idp(InMemoryPortalIdp())
    try:
        assert isinstance(port.portal_idp(), InMemoryPortalIdp)
    finally:
        port.configure_portal_idp(None)
