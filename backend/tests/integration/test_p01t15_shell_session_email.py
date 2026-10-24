# ac-test-author: ayushkbhatia
"""P-01-T15: independent AC tests (ADR-078) for N's red P-01 work (T04 capabilities, T05 email
templates, T09 the staff session, T11 switching, T13 Undo) and C16's email-half contract.

P-01 §3.2: the SHL-03 admin rows come only from `/v1/me/capabilities.nav` (AC 2.1.2: Hannah sees
none, Daniel firm settings read and the audit log, Felix the security center and the audit log,
and Developer & API stays `none`); switching firms resolves the tenant from a held membership,
never the header alone, and a firm not held answers 404 (AC 2.1.4); sign-out ends the session
and the old cookie no longer refreshes (AC 2.1.6). §3.3: Undo is insert-only, and after it the
same version is decided again; a second Undo and a second effective decision are refused
(AC 3.1.4, 3.1.4b; the Undo contract itself is in the shared C3 suite, where T15 registers this
route). §3.5: the callback refuses a session without a second factor and sets `__Host-` cookie
flags (AC 5.1.2); refresh rotates the cookie, and a reused value revokes the session (AC 5.1.4).
C16 email half: templates use only the whitelisted variables (`recipient_first_name`,
`kind_sentence`, `engagement_display_name`, `app_link`), and anything else is refused.

Boundary: `create_app()` over HTTP with an in-process provider for the BFF's code exchange (the
shape `test_staff_session.py` gives it), the public communications template functions, and the
superuser for seeding. Expectations: `docs/plan/epics/P-01.md` §3.2, §3.3, §3.5,
`docs/contracts/notifications.md` §3, ADR-165, DEC-140, ADR-161.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Final, cast
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.clock import frozen
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.communications.templates import (
    UnknownTemplateVariable,
    current_version,
    import_platform_version,
    render,
)
from abacus.modules.identity.api import configure_verifier, reset_verifier
from abacus.modules.identity.staff_session import (
    COOKIE_NAME,
    ProviderRefused,
    ProviderTokens,
    configure_staff_idp,
)
from abacus_tools.fakes.identity import ISSUER, FakeIdentityProvider

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

ORIGIN: Final = "https://app.test"
REFRESH: Final = {"X-Abacus-CSRF": "1", "Origin": ORIGIN}
TENANT_HEADER: Final = "X-Abacus-Tenant"
T0: Final = datetime.fromisoformat("2026-09-14T09:42:00-05:00")


class Provider:
    """The provider half of the code exchange: a code names a subject and whether it did MFA."""

    def __init__(self, signer: FakeIdentityProvider) -> None:
        self.signer = signer
        self.codes: dict[str, tuple[str, bool]] = {}
        self.refresh_tokens: dict[str, str] = {}

    def authorize_url(
        self, *, state: str, challenge: str, redirect_uri: str, reauthenticate: bool
    ) -> str:
        return f"https://idp.test/authorize?state={state}&code_challenge={challenge}"

    def issue(self, subject: str, *, mfa: bool) -> str:
        code = uuid.uuid4().hex
        self.codes[code] = (subject, mfa)
        return code

    def _tokens(self, subject: str, mfa: bool) -> ProviderTokens:
        refresh = uuid.uuid4().hex
        self.refresh_tokens[refresh] = subject
        return ProviderTokens(self.signer.token(subject, mfa=mfa, expires_in=600), 600, refresh)

    async def exchange(self, *, code: str, verifier: str, redirect_uri: str) -> ProviderTokens:
        if code not in self.codes:
            raise ProviderRefused("authorization_code")
        return self._tokens(*self.codes.pop(code))

    async def refresh(self, refresh_token: str) -> ProviderTokens:
        subject = self.refresh_tokens.pop(refresh_token, None)
        if subject is None:
            raise ProviderRefused("refresh_token")
        return self._tokens(subject, True)

    async def revoke(self, refresh_token: str) -> None:
        self.refresh_tokens.pop(refresh_token, None)


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    monkeypatch.setenv("ABACUS_WEB_ORIGIN", ORIGIN)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def provider() -> Iterator[Provider]:
    signer = FakeIdentityProvider()
    configure_verifier(signer.verifier())
    fake = Provider(signer)
    configure_staff_idp(fake)
    yield fake
    configure_staff_idp(None)
    reset_verifier()


@pytest.fixture
async def http(provider: Provider) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        yield client


async def _member(
    seed: Seeder, tenant: uuid.UUID, name: str, firm_role: str | None = None
) -> tuple[uuid.UUID, str]:
    subject = f"sub-{uuid.uuid4().hex}"
    user = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            ISSUER,
            subject,
            f"{subject}@example.test",
            name,
        ),
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, $3, 'active')",
        tenant,
        user,
        firm_role,
    )
    return user, subject


def _bearer(provider: Provider, subject: str, tenant: uuid.UUID | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {provider.signer.token(subject)}"}
    if tenant is not None:
        headers[TENANT_HEADER] = str(tenant)
    return headers


async def _sign_in(
    http: httpx.AsyncClient, provider: Provider, subject: str, *, mfa: bool = True
) -> httpx.Response:
    started = await http.get("/v1/auth/sign-in", params={"return_to": "/engagements"})
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    response = await http.get(
        "/v1/auth/callback", params={"code": provider.issue(subject, mfa=mfa), "state": state}
    )
    http.cookies.clear()
    return response


def _cookie(response: httpx.Response) -> tuple[str, str]:
    """(the Set-Cookie header for the session cookie, its value)."""
    [header] = [h for h in response.headers.get_list("set-cookie") if h.startswith(COOKIE_NAME)]
    return header, header.split(";", 1)[0].split("=", 1)[1]


async def _refresh(http: httpx.AsyncClient, value: str) -> httpx.Response:
    response = await http.post(
        "/v1/auth/refresh", headers={**REFRESH, "Cookie": f"{COOKIE_NAME}={value}"}
    )
    http.cookies.clear()
    return response


async def _audits(seed: Seeder, action: str) -> int:
    return int(
        cast(int, await seed.value("SELECT count(*) FROM audit_events WHERE action = $1", action))
    )


# --- AC 2.1.2: the admin rows come from capabilities ---------------------------------------------


async def test_ac212_the_admin_rows_are_computed_from_capabilities_nav(
    seed: Seeder, http: httpx.AsyncClient, provider: Provider
) -> None:
    tenant = await seed.firm()
    people = {
        "hannah": await _member(seed, tenant, "Hannah Leclerc"),
        "felix": await _member(seed, tenant, "Felix Andersen", "security_admin"),
        "grace": await _member(seed, tenant, "Grace Holloway", "firm_admin"),
    }
    nav: dict[str, dict[str, str]] = {}
    for who, (_user, subject) in people.items():
        response = await http.get("/v1/me/capabilities", headers=_bearer(provider, subject))
        assert response.status_code == 200, response.text
        nav[who] = cast(dict[str, str], response.json()["nav"])
    assert set(nav["hannah"].values()) == {"none"}  # (b) no admin section at all
    # (d) Felix's Security center reads `security.manage`, which G-02-T02 adds to the matrix; until
    # then the row is `none` like Developer & API, and fixture scenario d renders it.
    assert nav["felix"]["firm_settings"] != "write"  # IT/Security does not manage the firm
    assert nav["grace"]["firm_settings"] == "write"  # (a) Firm settings, Users & roles, Audit log
    assert nav["grace"]["users_roles"] != "none"
    assert nav["grace"]["audit_log"] != "none"
    for who in nav:  # Developer & API waits for G-03's action
        assert nav[who]["developer_api"] == "none", who


# --- AC 2.1.4: switching firms -------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="ED-024: a tenant header naming a firm the person does not hold answers 403, not "
    "P-01 AC 2.1.4's 404; tenant resolution is cross-cutting, held for the main session, "
    "TASK-1140 (#393: the S7 batch PR)",
)
async def test_ac214_the_tenant_comes_from_a_held_membership_never_the_header_alone(
    seed: Seeder, http: httpx.AsyncClient, provider: Provider
) -> None:
    firm, sandbox, stranger = await seed.firm(), await seed.firm(), await seed.firm()
    user, subject = await _member(seed, firm, "Grace Holloway", "firm_admin")
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, 'firm_admin', 'active')",
        sandbox,
        user,
    )
    await _member(seed, stranger, "Someone else", "firm_admin")
    for tenant in (firm, sandbox):  # each held firm answers as itself
        me = await http.get("/v1/me", headers=_bearer(provider, subject, tenant))
        assert me.status_code == 200, me.text
        assert str(tenant) in me.text
    for tenant in (stranger, uuid.uuid4()):  # a firm she does not hold, real or not
        refused = await http.get("/v1/engagements", headers=_bearer(provider, subject, tenant))
        assert refused.status_code == 404, refused.text
        assert str(firm) not in refused.text and str(sandbox) not in refused.text


# --- AC 5.1.2, 5.1.4, 2.1.6: the staff session ---------------------------------------------------


async def test_ac512_the_session_cookie_carries_the_host_flags(
    seed: Seeder, http: httpx.AsyncClient, provider: Provider
) -> None:
    tenant = await seed.firm()
    _user, subject = await _member(seed, tenant, "Hannah Leclerc")
    response = await _sign_in(http, provider, subject)
    assert response.status_code in (302, 303, 307), response.text
    header, _value = _cookie(response)
    flags = {part.strip().lower() for part in header.split(";")[1:]}
    assert COOKIE_NAME.startswith("__Host-")
    assert {"httponly", "secure", "samesite=strict", "path=/"} <= flags
    assert not any(f.startswith("domain=") for f in flags)  # __Host- forbids a Domain
    assert await _audits(seed, "session.started") >= 1


async def test_ac512_a_session_without_a_second_factor_is_refused(
    seed: Seeder, http: httpx.AsyncClient, provider: Provider
) -> None:
    tenant = await seed.firm()
    user, subject = await _member(seed, tenant, "Hannah Leclerc")
    before = await _audits(seed, "auth.sign_in_refused")
    response = await _sign_in(http, provider, subject, mfa=False)
    assert not [
        h
        for h in response.headers.get_list("set-cookie")
        if h.startswith(COOKIE_NAME) and "=;" not in h and "Max-Age=0" not in h
    ]
    assert await _audits(seed, "auth.sign_in_refused") == before + 1
    sessions = await seed.value("SELECT count(*) FROM auth_sessions WHERE user_id = $1", user)
    assert sessions == 0


async def test_ac514_refresh_rotates_and_a_reused_value_revokes_the_session(
    seed: Seeder, http: httpx.AsyncClient, provider: Provider
) -> None:
    tenant = await seed.firm()
    _user, subject = await _member(seed, tenant, "Hannah Leclerc")
    _header, first = _cookie(await _sign_in(http, provider, subject))
    rotated = await _refresh(http, first)
    assert rotated.status_code == 200, rotated.text
    assert rotated.json().get("access_token")
    _header, second = _cookie(rotated)
    assert second != first
    reused = await _refresh(http, first)  # the rotated-out value comes back: a stolen cookie
    assert reused.status_code == 401
    assert await _audits(seed, "session.refresh_reused") >= 1
    after = await _refresh(http, second)  # the whole session is revoked, not just the old value
    assert after.status_code == 401


async def test_ac216_sign_out_ends_the_session_and_the_old_cookie_never_refreshes(
    seed: Seeder, http: httpx.AsyncClient, provider: Provider
) -> None:
    tenant = await seed.firm()
    _user, subject = await _member(seed, tenant, "Hannah Leclerc")
    _header, value = _cookie(await _sign_in(http, provider, subject))
    out = await http.post(
        "/v1/auth/sign-out",
        headers={**_bearer(provider, subject), **REFRESH, "Cookie": f"{COOKIE_NAME}={value}"},
    )
    http.cookies.clear()
    assert out.status_code in (200, 204), out.text
    assert await _audits(seed, "session.ended") >= 1
    assert (await _refresh(http, value)).status_code == 401


# --- AC 3.1.4, 3.1.4b: Undo is insert-only, then the version is decided again --------------------


async def test_ac314b_undo_then_another_reviewer_decides_the_same_version(
    seed: Seeder, http: httpx.AsyncClient, provider: Provider
) -> None:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    hannah, hannah_sub = await _member(seed, tenant, "Hannah Leclerc")
    marcus, marcus_sub = await _member(seed, tenant, "Marcus Webb")
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, hannah)
    for user, role in ((hannah, "engagement_partner"), (marcus, "manager")):
        await seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            tenant,
            engagement,
            user,
            role,
        )
        await seed.run(
            "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
            "statement_version, answered_at) "
            "VALUES ($1, $2, $3, 'confirmed', 'v1', clock_timestamp())",
            tenant,
            engagement,
            user,
        )
    item = await seed.item(tenant, engagement, hannah)
    evidence = await seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, 'Certified trust report', 'system', 'seed') RETURNING id",
        tenant,
        engagement,
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    version = await seed.value(
        "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, version_no, "
        "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method) "
        "VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', 'upload', 'uploaded') "
        "RETURNING id",
        tenant,
        engagement,
        evidence,
        fingerprint,
        f"tenants/{tenant}/sha256/{fingerprint}",
    )
    await seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, evidence_version_id, "
        "created_by_kind, created_by_id) VALUES ($1, $2, $3, $4, 'human', 'seed')",
        tenant,
        engagement,
        item,
        version,
    )
    await seed.run("UPDATE request_items SET status = 'uploaded' WHERE id = $1", item)
    base = f"/v1/engagements/{engagement}"

    async def post(subject: str, path: str, second: int) -> httpx.Response:
        with frozen(T0.replace(second=second)):
            return await http.post(path, json={}, headers=_bearer(provider, subject, tenant))

    accepted = await post(hannah_sub, f"{base}/evidence-versions/{version}/decision/accept", 0)
    assert accepted.status_code == 201, accepted.text
    first = accepted.json()["id"]
    second = await post(marcus_sub, f"{base}/evidence-versions/{version}/decision/accept", 2)
    assert second.status_code == 409 and second.json()["detail"] == "already_decided"
    undone = await post(hannah_sub, f"{base}/review-decisions/{first}/undo", 4)
    assert undone.status_code in (200, 201), undone.text
    assert await seed.item_status(item) == "uploaded"  # "Uploaded - needs review" again
    rows = await seed.rows(
        "SELECT id, decision, undoes_decision_id FROM review_decisions "
        "WHERE evidence_version_id = $1 ORDER BY decision_seq",
        version,
    )
    assert (str(rows[0]["id"]), rows[0]["decision"]) == (first, "accept")
    assert rows[1]["decision"] == "undone" and str(rows[1]["undoes_decision_id"]) == first
    again = await post(marcus_sub, f"{base}/evidence-versions/{version}/decision/accept", 6)
    assert again.status_code == 201, again.text  # another reviewer decides the same version
    twice = await post(hannah_sub, f"{base}/review-decisions/{first}/undo", 7)
    assert twice.status_code == 409 and twice.json() == {"detail": "undo_window_closed"}
    final = await seed.rows(
        "SELECT decision FROM review_decisions WHERE evidence_version_id = $1 "
        "ORDER BY decision_seq",
        version,
    )
    assert [r["decision"] for r in final] == ["accept", "undone", "accept"]  # nothing removed


# --- C16 email half: the renderer's whitelist ----------------------------------------------------

WHITELIST: Final = ("recipient_first_name", "kind_sentence", "engagement_display_name", "app_link")


async def test_c16_a_template_may_use_only_the_whitelisted_variables(
    migrated_db: MigratedDatabase,
) -> None:
    key = "notification." + "".join(chr(97 + b % 26) for b in uuid.uuid4().bytes[:10])
    body = (
        "Hi {{recipient_first_name}},\n"
        "{{kind_sentence}} in {{engagement_display_name}}: {{app_link}}\n"
    )
    made = await import_platform_version(
        "s-1", key, "en-US", "{{kind_sentence}}", body, list(WHITELIST)
    )
    assert made.created
    for bad in ("client_tin", "comment_quote", "file_name", "amount", "recipient_email"):
        with pytest.raises(UnknownTemplateVariable):
            await import_platform_version(
                "s-2", key, "en-US", "S", f"{{{{{bad}}}}} {{{{app_link}}}}", ["app_link", bad]
            )
        with pytest.raises(UnknownTemplateVariable):  # used in the text, never declared
            await import_platform_version("s-3", key, "en-US", "S", f"{{{{{bad}}}}}", [])


async def test_c16_rendering_refuses_a_fact_outside_the_whitelist(
    migrated_db: MigratedDatabase,
) -> None:
    key = "notification." + "".join(chr(97 + b % 26) for b in uuid.uuid4().bytes[:10])
    await import_platform_version(
        "s-1",
        key,
        "en-US",
        "{{kind_sentence}}",
        "{{kind_sentence}}: {{app_link}}",
        ["kind_sentence", "app_link"],
    )
    found = await current_version(key)
    assert found is not None
    facts = {"kind_sentence": "Margaret mentioned you", "app_link": "https://app.test/x/1"}
    assert render(found, facts).subject == "Margaret mentioned you"
    with pytest.raises(UnknownTemplateVariable):
        render(found, {**facts, "client_tin": "900-00-0001"})
