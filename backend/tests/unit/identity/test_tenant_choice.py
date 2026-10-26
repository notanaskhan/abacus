"""P-01 AC 2.1.4 (ED-024, TASK-1175): tenant resolution from a held membership, never the header
alone. A member's header naming a tenant they do not hold is `TenantNotHeld` (the API's 404),
whether the firm exists or not: `choose_tenant` reads only the person's memberships, never the
named firm, so the two cases cannot differ. Every other refusal stays `NoActiveTenant` (403).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import abacus.modules.identity.routing as routing
from abacus.kernel.errors import NotFound
from abacus.modules.identity.context import NoActiveTenant, TenantNotHeld
from abacus.modules.identity.repository import MembershipRecord, UserRecord
from abacus.modules.identity.service import SignedIn, choose_tenant
from abacus.modules.identity.tokens import VerifiedIdentity

FIRM = uuid.uuid4()
SANDBOX = uuid.uuid4()


def _signed_in(*tenants: uuid.UUID) -> SignedIn:
    return SignedIn(
        UserRecord(uuid.uuid4(), "grace@example.test", "Grace Holloway"),
        VerifiedIdentity("https://idp.example.test", "sub-grace", None),
        [MembershipRecord(t, uuid.uuid4(), "firm_admin", "Brightwater Hale LLP") for t in tenants],
    )


@pytest.mark.parametrize("tenant", [FIRM, SANDBOX])
def test_ac214_a_held_tenant_named_in_the_header_is_chosen(tenant: uuid.UUID) -> None:
    assert choose_tenant(_signed_in(FIRM, SANDBOX), str(tenant)).tenant_id == tenant


def test_ac214_one_membership_and_no_header_is_that_firm() -> None:
    assert choose_tenant(_signed_in(FIRM), None).tenant_id == FIRM


@pytest.mark.parametrize("held", [(FIRM,), (FIRM, SANDBOX)])
def test_ac214_a_header_naming_a_tenant_not_held_is_not_held(held: tuple[uuid.UUID, ...]) -> None:
    with pytest.raises(TenantNotHeld):
        choose_tenant(_signed_in(*held), str(uuid.uuid4()))


def test_ac214_not_held_is_still_a_refusal_to_choose() -> None:
    """Callers that catch `NoActiveTenant` (agents' run loaders) still catch it."""
    assert issubclass(TenantNotHeld, NoActiveTenant)


@pytest.mark.parametrize("held", [(FIRM, SANDBOX), ()])
def test_no_header_with_several_or_no_memberships_stays_a_403_refusal(
    held: tuple[uuid.UUID, ...],
) -> None:
    with pytest.raises(NoActiveTenant) as raised:
        choose_tenant(_signed_in(*held), None)
    assert not isinstance(raised.value, TenantNotHeld)


def test_spec000_ac2_no_membership_at_all_stays_403_whatever_the_header_names() -> None:
    """SPEC-000 AC-2: a person with no membership is refused 403; the header changes nothing."""
    for named in (FIRM, uuid.uuid4()):
        with pytest.raises(NoActiveTenant) as raised:
            choose_tenant(_signed_in(), str(named))
        assert not isinstance(raised.value, TenantNotHeld)


@pytest.mark.parametrize("value", ["not-a-uuid", "", " ", "12345"])
def test_a_malformed_header_names_no_tenant_and_stays_a_403_refusal(value: str) -> None:
    with pytest.raises(NoActiveTenant) as raised:
        choose_tenant(_signed_in(FIRM, SANDBOX), value)
    assert not isinstance(raised.value, TenantNotHeld)


# --- the HTTP answer: the app's own 404 ----------------------------------------------------------


@pytest.fixture
def grace_in_one_firm(monkeypatch: pytest.MonkeyPatch) -> None:
    async def signed_in(authorization: str | None = None) -> SignedIn:
        del authorization
        return _signed_in(FIRM)

    monkeypatch.setattr(routing, "current_signed_in", signed_in)

    # DEC-383: the request-time access-end check reads the firm's database; a unit test has none.
    async def not_ended(*_: object) -> bool:
        return False

    monkeypatch.setattr(routing, "access_has_ended", not_ended)


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "headers": [], "path": "/v1/engagements"})


@pytest.mark.usefixtures("grace_in_one_firm")
async def test_ac214_current_context_answers_not_held_with_the_kernels_not_found() -> None:
    """The app renders `NotFound` as every missing record: `{"detail": "not found"}`, 404."""
    with pytest.raises(NotFound):
        await routing.current_context(_request(), "Bearer x", str(uuid.uuid4()), None)


@pytest.mark.usefixtures("grace_in_one_firm")
async def test_current_context_keeps_403_for_a_malformed_header() -> None:
    with pytest.raises(HTTPException) as refused:
        await routing.current_context(_request(), "Bearer x", "not-a-uuid", None)
    assert (refused.value.status_code, refused.value.detail) == (403, "forbidden")


@pytest.mark.usefixtures("grace_in_one_firm")
async def test_current_context_still_resolves_a_held_tenant() -> None:
    ctx = await routing.current_context(_request(), "Bearer x", str(FIRM), None)
    assert ctx.tenant_id == FIRM
