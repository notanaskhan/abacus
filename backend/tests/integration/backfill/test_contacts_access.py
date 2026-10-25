"""P-07-T25 (TASK-1123; DEC-300 to DEC-303): contacts and portal access live, the implementing
suite beside P-07-T26's independent one (`test_p07t26_contacts_g2_independent.py`, whose seeding
it reuses): replayed invitations, the inviter re-checked on the new acceptance path (DEC-277),
a client-wide owner invitation after G1 with its MFA step, change scope on an invited contact,
contact create and edit, the human-only rule, and the delegations a revoke ends."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.team import remove_member as remove_team_member
from abacus.modules.organisations import contacts as contacts_service

from . import test_p07t26_contacts_g2_independent as t26
from .support import Net
from .test_p07t26_contacts_g2_independent import World

pytestmark = pytest.mark.asyncio

# The independent suite's seeding and calls, shared rather than copied.
_accept = t26._accept  # pyright: ignore[reportPrivateUsage] -- shared seeding
_accepted = t26._accepted  # pyright: ignore[reportPrivateUsage] -- shared seeding
_grants_of = t26._grants_of  # pyright: ignore[reportPrivateUsage] -- shared seeding
_harborline_grants = t26._harborline_grants  # pyright: ignore[reportPrivateUsage] -- shared seeding
_invite = t26._invite  # pyright: ignore[reportPrivateUsage] -- shared seeding
_json = t26._json  # pyright: ignore[reportPrivateUsage] -- shared seeding
_portal_session = t26._portal_session  # pyright: ignore[reportPrivateUsage] -- shared seeding
_token = t26._token  # pyright: ignore[reportPrivateUsage] -- shared seeding
_world = t26._world  # pyright: ignore[reportPrivateUsage] -- shared seeding


@pytest.fixture
async def world(net: Net) -> World:
    return await _world(net)


async def _activate(world: World) -> None:
    """Northwind's engagement at Active (G1 met), moved as the app moves it."""
    async with uow(TenantContext(world.tenant, "system", "test-seed")) as tx:
        await tx.session.execute(
            text("UPDATE engagements SET status = 'active' WHERE id = :id"),
            {"id": world.site.engagement_id},
        )
        tx.record("engagement.probed", target=Target("engagement", world.site.engagement_id))


async def test_a_replayed_invitation_key_answers_the_first_invitation(world: World) -> None:
    replay = f"harborline-{uuid.uuid4().hex[:8]}"
    first = _json(
        await _invite(world, world.harborline, _harborline_grants(world), key=replay),
        201,
    )
    again = _json(
        await _invite(world, world.harborline, _harborline_grants(world), key=replay),
        201,
    )
    assert again["invitation_id"] == first["invitation_id"]
    assert len(await _grants_of(world, world.harborline)) == 2
    invited = await world.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'contact.invited'",
        world.tenant,
    )
    assert invited == 1


async def test_dec277_an_inviter_who_left_before_acceptance_grants_nothing(world: World) -> None:
    body = _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    token = await _token(world, cast(str, body["invitation_id"]))
    access = await _portal_session(world, world.email, token)
    await world.seed.revoke(world.grace)
    refused = await _accept(world, access, token)
    assert refused.status_code == 404
    assert {s[3] for s in await _grants_of(world, world.harborline)} == {"pending"}
    refusals = await world.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'client_invitation.accept_refused'",
        world.tenant,
    )
    assert refusals == 1


async def test_a_client_wide_owner_invitation_after_g1_asks_for_the_second_step(
    world: World,
) -> None:
    owner_grant: list[dict[str, object]] = [
        {"role": "owner", "scope_kind": "client", "scope_id": str(world.site.client_id)}
    ]
    await world.seed.run(
        "UPDATE engagements SET status = 'prospect' WHERE id = $1", world.site.engagement_id
    )
    refused = await _invite(world, world.harborline, owner_grant)
    assert refused.status_code == 409 and refused.json()["detail"] == "gate_unmet"
    await _activate(world)
    body = _json(await _invite(world, world.harborline, owner_grant), 201)
    assert body["mfa_policy"] == "required_by_firm"
    anchored = await world.seed.value(
        "SELECT engagement_id FROM client_invitations WHERE id = $1",
        uuid.UUID(cast(str, body["invitation_id"])),
    )
    assert anchored == world.site.engagement_id
    token = await _token(world, cast(str, body["invitation_id"]))
    access = await _portal_session(world, world.email, token)
    accepted = _json(await _accept(world, access, token))
    assert cast(dict[str, object], accepted["session"])["state"] in (
        "mfa_required",
        "mfa_setup_required",
    )
    assert {(s[0], s[1], s[3]) for s in await _grants_of(world, world.harborline)} == {
        ("owner", "client", "active")
    }


async def test_change_scope_on_an_invited_contact_joins_the_pending_invitation(
    world: World,
) -> None:
    body = _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    drawer = _json(await world.net.call("GET", f"/v1/contacts/{world.harborline}", world.grace))
    target = [str(world.items[1]), str(world.items[2])]
    _json(
        await world.net.call(
            "PUT",
            f"/v1/contacts/{world.harborline}/access",
            world.grace,
            body={
                "seen_version": drawer["version"],
                "grants": [
                    {
                        "role": "third_party",
                        "scope_kind": "request_item",
                        "scope_id": target[0],
                        "request_item_ids": target,
                    }
                ],
            },
        )
    )
    token = await _token(world, cast(str, body["invitation_id"]))
    access = await _portal_session(world, world.email, token)
    assert (await _accept(world, access, token)).status_code == 200
    live = {(s[2], s[3]) for s in await _grants_of(world, world.harborline)}
    assert live == {
        (world.items[0], "revoked"),
        (world.items[1], "active"),
        (world.items[2], "active"),
    }


async def test_create_and_edit_a_contact_with_roles_and_versions(world: World) -> None:
    made = _json(
        await world.net.call(
            "POST",
            f"/v1/clients/{world.site.client_id}/contacts",
            world.grace,
            body={
                "name": "Priya Raman",
                "email": "priya.raman@example.test",
                "roles": [
                    {
                        "role": "controller",
                        "scope_kind": "client_entity",
                        "scope_id": str(world.site.entity_id),
                        "title_text": "Controller",
                    }
                ],
            },
        ),
        201,
    )
    contact = cast(dict[str, object], made["contact"])
    roles = cast(list[dict[str, object]], contact["roles"])
    assert [(r["role"], r["scope_kind"]) for r in roles] == [("controller", "client_entity")]
    assert contact["portal_status"] == "not_invited" and made["version"] == 1
    duplicate = await world.net.call(
        "POST",
        f"/v1/clients/{world.site.client_id}/contacts",
        world.grace,
        body={"name": "Priya again", "email": "priya.raman@example.test"},
    )
    assert duplicate.status_code == 409 and duplicate.json()["detail"] == "contact_exists"
    path = f"/v1/contacts/{contact['id']}"
    edited = _json(
        await world.net.call(
            "PATCH", path, world.grace, body={"seen_version": 1, "phone": "555-0100", "roles": []}
        )
    )
    assert edited["version"] == 2
    assert cast(dict[str, object], edited["contact"])["roles"] == []
    stale = await world.net.call("PATCH", path, world.grace, body={"seen_version": 1})
    assert stale.status_code == 409 and stale.json()["detail"] == "stale_version"
    staff = await world.seed.person(world.tenant)
    await world.seed.member(world.site, staff, "staff")
    refused = await world.net.call("PATCH", path, staff, body={"seen_version": 2})
    assert refused.status_code == 403
    actions = await world.seed.actions(world.tenant)
    assert actions.count("contact.created") == 1 and actions.count("contact.updated") == 1


async def test_inv1_an_agent_or_system_context_is_refused_before_anything(world: World) -> None:
    for kind in ("agent", "system"):
        ctx = AuthContext(
            TenantContext(world.tenant, kind, "probe"),
            world.grace.user_id,
            uuid.uuid4(),
            "firm_admin",
            None,
        )
        with pytest.raises(Forbidden):
            await contacts_service.invite(
                ctx,
                world.harborline,
                [
                    contacts_service.GrantAsked(
                        "third_party", "request_item", world.items[0], (world.items[0],)
                    )
                ],
            )
    assert await _grants_of(world, world.harborline) == []


async def test_revoke_ends_the_delegations_and_the_footer_drops_them(world: World) -> None:
    invitation, _, _ = await _accepted(world)
    page = _json(
        await world.net.call("GET", f"/v1/clients/{world.site.client_id}/contacts", world.grace)
    )
    assert cast(dict[str, object], page["delegated"])["total"] == 2
    _json(
        await world.net.call(
            "POST", f"/v1/invitations/{invitation['invitation_id']}/revoke", world.grace
        )
    )
    open_delegations = await world.seed.value(
        "SELECT count(*) FROM request_delegations WHERE contact_id = $1 AND revoked_at IS NULL",
        world.harborline,
    )
    assert open_delegations == 0
    after = _json(
        await world.net.call("GET", f"/v1/clients/{world.site.client_id}/contacts", world.grace)
    )
    assert after["delegated"] == {"parts": [], "total": 0, "received": 0}
    row = cast(list[dict[str, object]], after["items"])[0]
    assert row["portal_status"] == "not_invited"


async def test_ed049_the_row_names_the_live_invitation_that_resend_and_revoke_take(
    world: World,
) -> None:
    """ED-049 (P-07-T33): CLI-04's Resend and Revoke take an invitation id, so the row carries
    the contact's live invitation (Invited, then Active) and none once Not invited again."""

    async def harborline() -> dict[str, object]:
        page = _json(
            await world.net.call(
                "GET", f"/v1/clients/{world.site.client_id}/contacts", world.grace
            )
        )
        rows = cast(list[dict[str, object]], page["items"])
        return next(r for r in rows if r["id"] == str(world.harborline))

    before = await harborline()
    assert (before["portal_status"], before["invitation_id"]) == ("not_invited", None)
    invitation, _, _ = await _accepted(world)
    active = await harborline()
    assert (active["portal_status"], active["invitation_id"]) == (
        "active",
        invitation["invitation_id"],
    )
    _json(
        await world.net.call(
            "POST", f"/v1/invitations/{active['invitation_id']}/revoke", world.grace
        )
    )
    after = await harborline()
    assert (after["portal_status"], after["invitation_id"]) == ("not_invited", None)


async def test_dec277_leaving_the_engagement_closes_the_contact_invitation_and_its_grants(
    world: World,
) -> None:
    _json(await _invite(world, world.harborline, _harborline_grants(world), who=world.hannah), 201)
    partner = await world.seed.person(world.tenant)
    await world.seed.member(world.site, partner, "engagement_partner")
    ctx = AuthContext(
        TenantContext(world.tenant, "human", str(partner.user_id)),
        partner.user_id,
        cast(
            uuid.UUID,
            await world.seed.value(
                "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2",
                world.tenant,
                partner.user_id,
            ),
        ),
        None,
        datetime.now(UTC),
    )
    async with uow(ctx.tenant) as tx:
        await remove_team_member(tx, ctx, world.site.engagement_id, world.hannah.user_id)
    assert {s[3] for s in await _grants_of(world, world.harborline)} == {"revoked"}
    page = _json(
        await world.net.call("GET", f"/v1/clients/{world.site.client_id}/contacts", world.grace)
    )
    assert cast(dict[str, object], page["delegated"])["total"] == 0
    # The firm invites again from CLI-04: a fresh invitation, and the old delegations end.
    _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    open_delegations = await world.seed.value(
        "SELECT count(*) FROM request_delegations WHERE contact_id = $1 AND revoked_at IS NULL",
        world.harborline,
    )
    assert open_delegations == 2


# ================================================================================================
# Security review of P-07-T25 (DEC-303)
# ================================================================================================

_preview = t26._preview  # pyright: ignore[reportPrivateUsage] -- shared seeding
_lock = t26._lock  # pyright: ignore[reportPrivateUsage] -- shared seeding


def _owner_grant(world: World) -> list[dict[str, object]]:
    return [{"role": "owner", "scope_kind": "client", "scope_id": str(world.site.client_id)}]


async def _invited(world: World, grants: list[dict[str, object]], **kw: object) -> tuple[str, str]:
    body = _json(await _invite(world, world.harborline, grants, **kw), 201)  # pyright: ignore[reportArgumentType] -- the helper's keywords
    token = await _token(world, cast(str, body["invitation_id"]))
    return cast(str, body["invitation_id"]), token


async def test_review1_an_inviter_demoted_to_firm_partner_grants_nothing_at_acceptance(
    world: World,
) -> None:
    await _activate(world)
    _, token = await _invited(world, _owner_grant(world))
    await world.seed.run(
        "UPDATE memberships SET firm_role = NULL, level = 'partner' "
        "WHERE tenant_id = $1 AND user_id = $2",
        world.tenant,
        world.grace.user_id,
    )
    access = await _portal_session(world, world.email, token)
    assert (await _accept(world, access, token)).status_code == 404
    assert {s[3] for s in await _grants_of(world, world.harborline)} == {"pending"}


async def test_review1_a_manager_whose_independence_lapsed_grants_nothing_on_an_attest_client(
    world: World,
) -> None:
    await world.seed.attest(world.tenant, world.site.engagement_id)
    _, token = await _invited(world, _harborline_grants(world), who=world.hannah)
    await world.seed.run(
        "UPDATE independence_confirmations SET status = 'requested', answered_at = NULL "
        "WHERE engagement_id = $1 AND user_id = $2",
        world.site.engagement_id,
        world.hannah.user_id,
    )
    access = await _portal_session(world, world.email, token)
    assert (await _accept(world, access, token)).status_code == 404
    assert {s[3] for s in await _grants_of(world, world.harborline)} == {"pending"}


async def test_review2_the_hosted_accept_path_refuses_a_contact_invitation(world: World) -> None:
    _, token = await _invited(world, _harborline_grants(world))
    _, headers = world.net.newcomer(world.email)
    refused = await world.net.http.post(
        "/v1/invitations/accept", json={"token": token}, headers=headers
    )
    assert refused.status_code == 404
    assert {s[3] for s in await _grants_of(world, world.harborline)} == {"pending"}


async def test_review3_an_email_change_kills_the_pending_invitation(world: World) -> None:
    _, token = await _invited(world, _harborline_grants(world))
    drawer = _json(await world.net.call("GET", f"/v1/contacts/{world.harborline}", world.grace))
    _json(
        await world.net.call(
            "PATCH",
            f"/v1/contacts/{world.harborline}",
            world.grace,
            body={"seen_version": drawer["version"], "email": "new.address@example.test"},
        )
    )
    assert (await _preview(world, token)).status_code == 404
    assert {s[3] for s in await _grants_of(world, world.harborline)} == {"revoked"}
    status = await world.seed.value(
        "SELECT portal_state FROM contacts WHERE id = $1", world.harborline
    )
    assert status == "not_invited"


async def test_review3_a_bound_contacts_email_cannot_change_and_bad_addresses_are_422(
    world: World,
) -> None:
    await _accepted(world)
    drawer = _json(await world.net.call("GET", f"/v1/contacts/{world.harborline}", world.grace))
    path = f"/v1/contacts/{world.harborline}"
    refused = await world.net.call(
        "PATCH",
        path,
        world.grace,
        body={"seen_version": drawer["version"], "email": "other@example.test"},
    )
    assert refused.status_code == 409 and refused.json()["detail"] == "contact_bound"
    for bad in ("no-at-sign", "a@b\r\nBcc: x@y.test", "two@@example.test"):
        made = await world.net.call(
            "POST",
            f"/v1/clients/{world.site.client_id}/contacts",
            world.grace,
            body={"name": "Bad address", "email": bad},
        )
        assert made.status_code == 422, bad


async def test_review4_unlock_and_locked_state_follow_the_persons_identity_not_the_field(
    world: World,
) -> None:
    await _accepted(world)
    decoy = f"decoy.{uuid.uuid4().hex[:8]}@example.test"
    await _lock(world, decoy)
    # The contact's field is pointed at another address: no state or unlock may follow it.
    await world.seed.run("UPDATE contacts SET email = $2 WHERE id = $1", world.harborline, decoy)
    page = _json(
        await world.net.call("GET", f"/v1/clients/{world.site.client_id}/contacts", world.grace)
    )
    assert cast(dict[str, int], page["summary"])["locked"] == 0
    stale = await world.net.call(
        "POST", f"/v1/contacts/{world.harborline}/unlock", world.grace, mfa=False
    )
    assert stale.status_code == 403  # contact.unlock needs a fresh second factor
    _json(await world.net.call("POST", f"/v1/contacts/{world.harborline}/unlock", world.grace))
    still = await world.seed.value(
        "SELECT count(*) FROM sign_in_locks WHERE host_tenant_id = $1 "
        "AND email_sha256 = encode(sha256(convert_to(lower($2), 'UTF8')), 'hex') "
        "AND locked_until > now()",
        world.tenant,
        decoy,
    )
    assert still == 1
    audited = await world.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'contact.unlocked'",
        world.tenant,
    )
    assert audited == 1


async def test_review5_revoking_through_an_old_invitation_kills_the_newer_pending_one(
    world: World,
) -> None:
    first, _, _ = await _accepted(world)
    _json(
        await world.net.call(
            "POST", f"/v1/invitations/{first['invitation_id']}/revoke", world.grace
        )
    )
    _, newer = await _invited(world, _harborline_grants(world))
    assert (await _preview(world, newer)).status_code == 200
    _json(
        await world.net.call(
            "POST", f"/v1/invitations/{first['invitation_id']}/revoke", world.grace
        )
    )
    assert (await _preview(world, newer)).status_code == 404
    assert {s[3] for s in await _grants_of(world, world.harborline)} == {"revoked"}


async def test_review6_reinviting_after_a_revoke_gives_working_access(world: World) -> None:
    first, _, user = await _accepted(world)
    _json(
        await world.net.call(
            "POST", f"/v1/invitations/{first['invitation_id']}/revoke", world.grace
        )
    )
    _, token = await _invited(world, _harborline_grants(world))
    access = await _portal_session(world, world.email, token)
    assert (await _accept(world, access, token)).status_code == 200
    live = await world.seed.rows(
        "SELECT scope_id FROM client_access_grants WHERE tenant_id = $1 AND user_id = $2 "
        "AND status = 'active'",
        world.tenant,
        user,
    )
    assert sorted(r["scope_id"] for r in live) == sorted(world.items[:2])


async def test_review7_resend_rechecks_g1_and_needs_the_grants_still_pending(
    world: World,
) -> None:
    await _activate(world)
    invitation, _ = await _invited(world, _owner_grant(world))
    await world.seed.run(
        "UPDATE engagements SET status = 'prospect' WHERE id = $1", world.site.engagement_id
    )
    refused = await world.net.call("POST", f"/v1/invitations/{invitation}/resend", world.grace)
    assert refused.status_code == 409 and refused.json()["detail"] == "gate_unmet"
    other, _ = await _invited(world, _harborline_grants(world))
    await world.seed.run(
        "UPDATE client_access_grants SET status = 'revoked' WHERE contact_id = $1 "
        "AND status = 'pending'",
        world.harborline,
    )
    gone = await world.net.call("POST", f"/v1/invitations/{other}/resend", world.grace)
    assert gone.status_code == 404
