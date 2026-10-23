"""F-04-T27 (F-04.24; F-04 §4.8; DEC-155): the WorkOS fake. The staff half walks SHL-06's hosted
pages on the local sign-in server: the work email (a), the emailed code read from the mailbox (b),
the authenticator code (c), a wrong code with the attempts left (e), the lock after five (f) and
the redirect the BFF lands on (g). The portal half is the `PortalIdp` port (its contract tests run
against it in tests/contracts/portal_idp/); here, what only the fake adds."""

from __future__ import annotations

import base64
import hashlib
import inspect
import re
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from abacus.modules.communications.api import on_sink
from abacus.modules.identity.api import JwtVerifier
from abacus_tools.fakes import oidc_server, workos
from abacus_tools.fakes.identity import AUDIENCE, ISSUER
from abacus_tools.fakes.workos import (
    FakeWorkOsPortalIdp,
    StaffSignIn,
    StaffUser,
    scenario_portal_personas,
    scenario_staff,
    seed_portal_personas,
)
from abacus_tools.harness.mailbox import LocalMailboxReader
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import DEMO_INSTANT

REDIRECT = "http://localhost:5173/v1/auth/callback"
VERIFIER = "w" * 64
HANNAH = "hannah.leclerc@brightwaterhale.com"


def _challenge() -> str:
    digest = hashlib.sha256(VERIFIER.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class _Clock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at


@pytest.fixture(autouse=True)
def key_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "keys" / "oidc-key.pem"
    monkeypatch.setattr(oidc_server, "KEY_FILE", path)
    return path


@pytest.fixture
def clock() -> _Clock:
    return _Clock(DEMO_INSTANT)


@pytest.fixture
def staff(tmp_path: Path, clock: _Clock) -> StaffSignIn:
    return StaffSignIn(clock=clock, mailbox_dir=tmp_path / "mailbox")


@pytest.fixture
async def client(staff: StaffSignIn) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=oidc_server.create_app(staff=staff))
    async with httpx.AsyncClient(transport=transport, base_url="http://idp.test") as http:
        yield http


def _token(page: str) -> str:
    found = re.search(r"name='token' value='([^']+)'", page)
    assert found is not None
    return found.group(1)


async def _start(client: httpx.AsyncClient, email: str = HANNAH) -> str:
    response = await client.post(
        "/authorize/email",
        data={
            "redirect_uri": REDIRECT,
            "state": "state-9",
            "code_challenge": _challenge(),
            "email": email,
        },
    )
    assert response.status_code == 200
    assert "Check your email" in response.text
    return _token(response.text)


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


# --- the staff half: SHL-06 ---------------------------------------------------------------------


async def test_t27_shl06a_the_chooser_page_also_takes_a_work_email(
    client: httpx.AsyncClient,
) -> None:
    page = await client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": "abacus-web",
            "redirect_uri": REDIRECT,
            "code_challenge_method": "S256",
            "code_challenge": _challenge(),
            "state": "s",
        },
    )
    assert "<label for='email'>Work email</label>" in page.text
    assert "action='/authorize/email'" in page.text
    assert "Dana Leader (practice leader)" in page.text  # the chooser stays


async def test_t27_shl06b_c_g_email_code_then_authenticator_then_signed_in(
    client: httpx.AsyncClient, staff: StaffSignIn, tmp_path: Path
) -> None:
    token = await _start(client)
    # b: the code went to the synthetic sink, never to the firm's domain; the harness reads it.
    [mail] = LocalMailboxReader(tmp_path / "mailbox").messages()
    assert on_sink(mail.to) and "brightwaterhale.com" not in mail.to.split("@")[1]
    assert mail.to.startswith("hannah.leclerc+")
    code = staff.latest_code(HANNAH)
    assert code is not None and mail.code == code
    assert (await client.get("/_harness/code", params={"email": HANNAH})).json() == {"code": code}
    # c: the second factor.
    second = await client.post("/authorize/code", data={"token": token, "code": code})
    assert "Two-step verification" in second.text
    assert "Trust this device for 30 days" in second.text
    totp = (await client.get("/_harness/totp", params={"email": HANNAH})).json()["code"]
    assert totp == staff.current_totp(HANNAH)
    # g: back to the BFF's callback with a single-use code for the scenario person.
    done = await client.post("/authorize/mfa", data={"token": token, "code": totp})
    assert done.status_code == 303
    location = urlparse(done.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == REDIRECT
    query = parse_qs(location.query)
    assert query["state"] == ["state-9"]
    tokens = await client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": REDIRECT,
            "client_id": "abacus-web",
            "code_verifier": VERIFIER,
        },
    )
    jwks = (await client.get("/jwks")).text
    identity = JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=jwks).verify(
        tokens.json()["access_token"]
    )
    assert identity.subject == "scenario-hannah-leclerc"
    assert identity.email == HANNAH
    assert identity.mfa_at is not None
    # The pending sign-in is spent.
    again = await client.post("/authorize/mfa", data={"token": token, "code": totp})
    assert again.status_code == 400


async def test_t27_shl06e_a_wrong_code_says_how_many_attempts_are_left(
    client: httpx.AsyncClient, staff: StaffSignIn
) -> None:
    token = await _start(client)
    code = staff.latest_code(HANNAH)
    assert code is not None
    wrong = await client.post("/authorize/code", data={"token": token, "code": _wrong(code)})
    assert "<p role='alert'>That code didn&#x27;t match. 4 attempts left.</p>" in wrong.text
    right = await client.post("/authorize/code", data={"token": token, "code": code})
    assert "Two-step verification" in right.text


async def test_t27_shl06f_the_fifth_wrong_code_locks_and_names_it_security(
    client: httpx.AsyncClient, staff: StaffSignIn, clock: _Clock, tmp_path: Path
) -> None:
    box = LocalMailboxReader(tmp_path / "mailbox")
    token = await _start(client)
    code = staff.latest_code(HANNAH)
    assert code is not None
    seen: list[str] = []
    for _ in range(5):
        page = await client.post("/authorize/code", data={"token": token, "code": _wrong(code)})
        seen.append(page.text)
    assert "3 attempts left" in seen[1] and "1 attempt left." in seen[3]
    assert "Account locked" in seen[4]
    assert (
        "Too many incorrect codes. Try again at 9:54 AM, or ask Felix Andersen (IT / Security) "
        "to unlock your account." in seen[4]
    )
    # Locked: even the right code is refused, and a new sign-in sends no code until it lifts.
    still = await client.post("/authorize/code", data={"token": token, "code": code})
    assert "Account locked" in still.text
    await _start(client)
    assert len(box.messages()) == 1  # no new email while locked
    clock.at = DEMO_INSTANT + timedelta(minutes=30)
    assert staff.locked_until(HANNAH) is None
    fresh = await _start(client)
    assert len(box.messages()) == 2
    new_code = staff.latest_code(HANNAH)
    assert new_code is not None
    assert staff.submit_code(fresh, new_code).state == "mfa_required"


async def test_t27_wrong_authenticator_codes_count_toward_the_same_lock(
    client: httpx.AsyncClient, staff: StaffSignIn
) -> None:
    token = await _start(client)
    code = staff.latest_code(HANNAH)
    assert code is not None
    await client.post("/authorize/code", data={"token": token, "code": code})
    wrong = await client.post(
        "/authorize/mfa", data={"token": token, "code": _wrong(staff.current_totp(HANNAH))}
    )
    assert "4 attempts left" in wrong.text


async def test_t27_an_unknown_email_gets_the_same_page_and_no_mail(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    token = await _start(client, "someone.else@brightwaterhale.com")
    assert LocalMailboxReader(tmp_path / "mailbox").messages() == []
    page = await client.post("/authorize/code", data={"token": token, "code": "000000"})
    assert "4 attempts left" in page.text


def test_t27_an_expired_code_is_refused(staff: StaffSignIn, clock: _Clock) -> None:
    token = staff.start(HANNAH)
    code = staff.latest_code(HANNAH)
    assert code is not None
    clock.at = DEMO_INSTANT + timedelta(minutes=10)
    assert staff.submit_code(token, code).state == "expired"


def test_t27_the_scenario_staff_are_the_loaders_users() -> None:
    people = scenario_staff()
    assert len(people) == 46
    hannah = next(p for p in people if p.name == "Hannah Leclerc")
    assert hannah == StaffUser(HANNAH, "scenario-hannah-leclerc", "Hannah Leclerc")
    assert workos.it_security_person() == "Felix Andersen"


# --- the portal half: what the fake adds to the port --------------------------------------------


async def test_t27_portal_ids_are_workos_shaped_and_the_harness_reads_the_current_code() -> None:
    idp = FakeWorkOsPortalIdp(now=1_800_000_000.0)
    user = await idp.upsert_user("luis.ferrante@sink.brightwaterhale.test", name="Luis Ferrante")
    assert re.fullmatch(r"user_01[0-9A-Z]{24}", user)
    enrolment = await idp.enrol_totp(user, issuer="Brightwater Hale", account="luis")
    assert enrolment.factor_id.startswith("auth_factor_01")
    assert idp.factors_of(user) == [enrolment.factor_id]
    challenge = await idp.challenge(enrolment.factor_id)
    assert challenge.startswith("auth_challenge_01")
    assert await idp.verify(challenge, idp.current_code(enrolment.factor_id))


async def test_t27_scenario_portal_personas_are_on_the_sink_and_owners_get_a_factor() -> None:
    idp = FakeWorkOsPortalIdp()
    factors = await seed_portal_personas(idp)
    people = scenario_portal_personas()
    assert {p.email for p in people} == set(factors)
    assert all(on_sink(p.email) for p in people)
    owners = {p.email for p in people if p.mfa}
    assert owners == {
        "dana.kowalski@sink.brightwaterhale.test",
        "luis.ferrante@sink.brightwaterhale.test",
    }
    assert {e for e, f in factors.items() if f is not None} == owners


def test_t27_the_portal_fake_never_sends_email() -> None:
    """DEC-155: WorkOS keeps users and factors; the portal issues and sends its own codes."""
    members = {name for name, _ in inspect.getmembers(FakeWorkOsPortalIdp)}
    assert not {m for m in members if re.search(r"magic|email_code|send", m)}


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_t27_the_fake_is_refused_outside_synthetic_environments(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setattr(workos, "settings", lambda: SimpleNamespace(environment=environment))
    with pytest.raises(RuntimeError, match="local runs and tests only"):
        FakeWorkOsPortalIdp()
    with pytest.raises(RuntimeError, match="local runs and tests only"):
        StaffSignIn()
