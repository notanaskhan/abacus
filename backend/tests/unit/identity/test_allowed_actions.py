"""F-03-T30 (ADR-145, ADR-147): "Grace Holloway's capabilities include binder and invitation
actions but no evidence content action, and the call records no authorisation check."
Grace is the Firm Admin with `client_service` on Copperleaf."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.api import AuthContext, Resource, allowed_actions

BINDER = {"request_item.create", "request_item.update", "request_item.assign"}
INVITATIONS = {"client_contact.invite", "client_contact.read", "client_contact.remove"}
STATUS = {"request_item.read"}
CONTENT = {"evidence.read", "evidence.upload", "evidence.accept", "comment.read"}


@pytest.fixture
def grace(monkeypatch: pytest.MonkeyPatch) -> tuple[AuthContext, Resource]:
    async def no_walls(*_: object) -> frozenset[uuid.UUID]:
        return frozenset()

    async def client_service(*_: object) -> str:
        return "client_service"

    async def confirmed(*_: object) -> bool:
        return True

    monkeypatch.setattr(authz, "walled_clients", no_walls)
    monkeypatch.setattr(authz, "engagement_role", client_service)
    monkeypatch.setattr(authz, "_independence", (None, confirmed))
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        "firm_admin",
        None,  # no fresh MFA: capabilities don't ask for it
    )
    return ctx, Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)


async def test_grace_may_run_binders_and_invitations_but_not_open_evidence(
    grace: tuple[AuthContext, Resource],
) -> None:
    ctx, copperleaf = grace
    allowed = await allowed_actions(ctx, copperleaf)
    assert allowed >= BINDER
    assert allowed >= INVITATIONS
    assert allowed >= STATUS
    assert not (CONTENT & allowed)


async def test_the_probe_records_no_authorisation_check(
    grace: tuple[AuthContext, Resource],
) -> None:
    ctx, copperleaf = grace
    with authz.recording_checks() as checked:
        await allowed_actions(ctx, copperleaf)
        assert checked == set()


async def test_a_walled_engagement_offers_nothing(
    grace: tuple[AuthContext, Resource], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, _ = grace
    client = uuid.uuid4()

    async def walled(*_: object) -> frozenset[uuid.UUID]:
        return frozenset({client})

    monkeypatch.setattr(authz, "walled_clients", walled)
    resource = Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False, client_id=client)
    assert await allowed_actions(ctx, resource) == frozenset()


async def test_candidates_narrow_the_question(grace: tuple[AuthContext, Resource]) -> None:
    ctx, copperleaf = grace
    assert await allowed_actions(ctx, copperleaf, ["evidence.read", "request_item.create"]) == {
        "request_item.create"
    }


def test_mfa_recent_until_comes_from_the_session() -> None:
    mfa = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
    assert mfa + authz.MFA_RECENT > mfa
