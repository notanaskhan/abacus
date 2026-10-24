"""G-01-T05 against Postgres (G-01 AC3.1 to AC4.7, AC5.1): ADM-02's people list on the envelope
with bands, counts and tallies that foot; search; seats and the 14-day invitation that counts
against them and carries its terms into the membership; the person drawer; a role change in one
unit of work, audited as the person who made it; the security role; deactivation that ends
sessions and keeps history; offshore's fail-closed conflict; the role templates' counts and grid.

Expectations come from G-01 section 3, not from the implementation."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import cast

import pytest

import abacus.modules.organisations.api  # registers the office list and member teams
from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import uow
from abacus.modules.identity import people, settings_registry
from abacus.modules.identity.api import AuthContext, Forbidden, issue_staff_invitation_token
from abacus.modules.identity.people import (
    AccessEndsRequired,
    AlreadyMember,
    FirmRoleHeld,
    InviteTerms,
    LastAdministrator,
    OffshoreAssignmentConflict,
    SeatsFull,
    SeatsNotProvisioned,
    StaffFilters,
    StalePerson,
)
from abacus.modules.identity.staff import StaffInvitationNotFound, accept_staff_invitation
from abacus.modules.identity.staff import revoke as staff_revoke
from abacus.modules.identity.tokens import VerifiedIdentity

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.organisations.api


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


class Firm:
    def __init__(self, seed: Seeder, tenant: uuid.UUID, office: uuid.UUID) -> None:
        self.seed = seed
        self.tenant = tenant
        self.office = office
        self.people: dict[str, AuthContext] = {}

    async def add(
        self,
        name: str,
        *,
        firm_role: str | None = None,
        level: str | None = None,
        template: str | None = None,
        office: uuid.UUID | None = None,
        ends: date | None = None,
    ) -> AuthContext:
        email = f"{name.lower().replace(' ', '.')}.{uuid.uuid4().hex[:6]}@example.test"
        user = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
                uuid.uuid4().hex,
                email,
                name,
            ),
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, "
            "role_template, office_id, access_ends_on) "
            "VALUES ($1, $2, $3, 'active', $4, $5, $6, $7)",
            self.tenant,
            user,
            firm_role,
            level,
            template,
            office or self.office,
            ends,
        )
        ctx = AuthContext(
            tenant=TenantContext(self.tenant, "human", str(user)),
            user_id=user,
            membership_id=uuid.uuid4(),
            firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
            mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        self.people[name] = ctx
        return ctx

    async def seats(self, total: int) -> None:
        grace = self.people["Grace Holloway"]
        async with uow(grace.tenant) as tx:
            await settings_registry.provision_setting(
                tx, self.tenant, "plan", "seats", total, grace.user_id
            )


async def _firm(seed: Seeder) -> Firm:
    tenant = await seed.firm()
    office = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO offices (tenant_id, name, time_zone) VALUES ($1, 'Denver', "
            "'America/Denver') RETURNING id",
            tenant,
        ),
    )
    firm = Firm(seed, tenant, office)
    await firm.add("Grace Holloway", firm_role="firm_admin", level="admin")
    await firm.add("Felix Andersen", firm_role="security_admin", level="admin")
    await firm.add("Daniel Reyes", level="partner", template="partner")
    await firm.add("Hannah Leclerc", level="manager", template="manager")
    await firm.add("Samuel Ito", level="manager", template="tax_reviewer")
    await firm.add("Olivia Brandt", level="senior", template="senior")
    await firm.add("Kevin Osei", level="staff", template="tax_preparer")
    await firm.add("Lena Park", level="seasonal", template="tax_preparer", ends=date(2026, 10, 31))
    return firm


async def test_ac3_1_bands_counts_and_tallies_foot(seed: Seeder) -> None:
    firm = await _firm(seed)
    await firm.seats(8)
    grace = firm.people["Grace Holloway"]
    page = await people.staff_page(grace, StaffFilters())
    assert page.total == 8 and sum(page.counts.values()) == 8
    assert page.counts == {
        "partners": 1,
        "managers": 2,
        "seniors": 1,
        "staff": 1,
        "seasonal": 1,
        "operations": 2,
    }
    bands = [r.band for r in page.items]
    assert bands == sorted(bands, key=people.BANDS.index)  # in band order
    t = page.tallies
    assert (t.seats_used, t.seats_total, t.seats_pending) == (8, 8, 0)
    assert (t.partners, t.professionals, t.operations) == (1, 5, 2)
    assert (t.sso_mfa, t.signed_in_of) == (8, 8)
    assert (t.seasonal, t.seasonal_access_ends_on) == (1, date(2026, 10, 31))
    lena = next(r for r in page.items if r.display_name == "Lena Park")
    assert (lena.role_template, lena.level, lena.status) == ("tax_preparer", "seasonal", "active")
    # A membership with no stored template reads the one its firm role implies.
    felix = next(r for r in page.items if r.display_name == "Felix Andersen")
    assert felix.role_template == "it_security" and felix.band == "operations"
    # Office filter; the band filter leaves the counts alone.
    other = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO offices (tenant_id, name) VALUES ($1, 'Chicago') RETURNING id",
            firm.tenant,
        ),
    )
    await firm.add("Ana Cruz", level="staff", template="staff", office=other)
    chicago = await people.staff_page(grace, StaffFilters(office_id=other))
    assert [r.display_name for r in chicago.items] == ["Ana Cruz"]
    staff_band = await people.staff_page(grace, StaffFilters(band="staff"))
    assert staff_band.total == 2 and staff_band.counts["partners"] == 1


async def test_ac3_1_pages_with_a_cursor_bound_to_its_filters(seed: Seeder) -> None:
    firm = await _firm(seed)
    grace = firm.people["Grace Holloway"]
    first = await people.staff_page(grace, StaffFilters(limit=5))
    assert len(first.items) == 5 and first.next_cursor is not None
    rest = await people.staff_page(grace, StaffFilters(limit=5, cursor=first.next_cursor))
    names = [r.display_name for r in first.items + rest.items]
    assert len(names) == 8 and len(set(names)) == 8 and rest.next_cursor is None


async def test_ac3_2_search_by_name_or_email(seed: Seeder) -> None:
    firm = await _firm(seed)
    found = await people.staff_page(firm.people["Grace Holloway"], StaffFilters(q="park"))
    assert [r.display_name for r in found.items] == ["Lena Park"]


async def test_reading_people_is_for_admins_security_admins_and_partners(seed: Seeder) -> None:
    firm = await _firm(seed)
    for name in ("Grace Holloway", "Felix Andersen", "Daniel Reyes"):
        assert (await people.staff_page(firm.people[name], StaffFilters())).total == 8
    with pytest.raises(NotFound):  # ADR-024: nothing to see
        await people.staff_page(firm.people["Kevin Osei"], StaffFilters())
    with pytest.raises(NotFound):
        await people.staff_user(firm.people["Kevin Osei"], firm.people["Lena Park"].user_id)


async def test_ac3_3_seats_full_refuses_an_invitation(seed: Seeder) -> None:
    firm = await _firm(seed)
    await firm.seats(8)
    with pytest.raises(SeatsFull) as refused:
        await people.invite(
            firm.people["Grace Holloway"],
            InviteTerms(email="new.person@example.test", role_template="staff"),
        )
    assert refused.value.facts == {"used": 8, "total": 8}


async def test_ac3_4_a_pending_invitation_counts_and_carries_its_terms(seed: Seeder) -> None:
    firm = await _firm(seed)
    await firm.seats(9)
    grace = firm.people["Grace Holloway"]
    email = f"newcomer.{uuid.uuid4().hex[:6]}@example.test"
    invitation = await people.invite(
        grace,
        InviteTerms(
            email=email,
            role_template="tax_preparer",
            level="seasonal",
            office_id=firm.office,
            service_lines=["tax"],
            access_ends_on=date(2026, 10, 31),
            display_name="Noel Kirby",
        ),
    )
    page = await people.staff_page(grace, StaffFilters())
    pending = next(r for r in page.items if r.invitation_id == invitation)
    assert (pending.status, pending.band, pending.display_name) == (
        "invited",
        "seasonal",
        "Noel Kirby",
    )
    today = (await clock.now(grace.tenant)).astimezone(clock.FIRM_ZONE).date()
    assert pending.invitation_expires_on == today + timedelta(days=14)  # DEC-35
    assert pending.last_sign_in_at is None and pending.user_id is None
    assert (page.tallies.seats_used, page.tallies.seats_pending) == (9, 1)
    with pytest.raises(SeatsFull):  # the pending invitation holds the ninth seat
        await people.invite(grace, InviteTerms(email="tenth@example.test", role_template="staff"))

    issued = await issue_staff_invitation_token(firm.tenant, invitation)
    assert issued is not None
    subject = uuid.uuid4().hex
    await accept_staff_invitation(
        VerifiedIdentity("https://probe.test", subject, datetime.now(UTC), email), issued.token
    )
    row = (
        await seed.rows(
            "SELECT m.role_template, m.level, m.office_id, m.service_lines, m.access_ends_on "
            "FROM memberships m JOIN users u ON u.id = m.user_id "
            "WHERE m.tenant_id = $1 AND u.idp_subject = $2",
            firm.tenant,
            subject,
        )
    )[0]
    assert (row["role_template"], row["level"], row["office_id"]) == (
        "tax_preparer",
        "seasonal",
        firm.office,
    )
    assert list(row["service_lines"]) == ["tax"] and row["access_ends_on"] == date(2026, 10, 31)
    after = await people.staff_page(grace, StaffFilters())
    assert (after.total, after.tallies.seats_used, after.tallies.seats_pending) == (9, 9, 0)


async def test_ac3_5_invitation_validation(seed: Seeder) -> None:
    firm = await _firm(seed)
    grace = firm.people["Grace Holloway"]
    with pytest.raises(AccessEndsRequired):
        await people.invite(
            grace,
            InviteTerms(email="s@example.test", role_template="tax_preparer", level="seasonal"),
        )
    kevin_email = cast(
        str,
        await seed.value(
            "SELECT email FROM users WHERE id = $1", firm.people["Kevin Osei"].user_id
        ),
    )
    with pytest.raises(AlreadyMember):
        await people.invite(grace, InviteTerms(email=kevin_email.upper(), role_template="staff"))


async def test_ac4_1_the_person_drawer(seed: Seeder) -> None:
    firm = await _firm(seed)
    grace = firm.people["Grace Holloway"]
    lena = firm.people["Lena Park"]
    client = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Ashford Manufacturing Co.') "
            "RETURNING id",
            firm.tenant,
        ),
    )
    wall = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            firm.tenant,
            lena.user_id,
            client,
            grace.user_id,
        ),
    )
    await seed.run(
        "UPDATE memberships SET created_at = now() - interval '100 hours' WHERE user_id = $1",
        lena.user_id,
    )
    for hours in (1, 30, 60, 90):
        await seed.run(
            "INSERT INTO auth_sessions (user_id, provider, mfa_at, created_at, "
            "idle_expires_at, absolute_expires_at) VALUES ($1, 'workos', now(), "
            "now() - make_interval(hours => $2), now(), now())",
            lena.user_id,
            hours,
        )
    found = await people.staff_user(grace, lena.user_id)
    assert found.row.display_name == "Lena Park" and found.row.access_ends_on == date(2026, 10, 31)
    assert found.wall_ids == [wall]
    assert len(found.recent_sign_ins) == 3  # the last three
    assert found.recent_sign_ins[0].at > found.recent_sign_ins[1].at
    assert all(s.mfa and s.method == "workos" for s in found.recent_sign_ins)
    assert found.row.last_sign_in_at == found.recent_sign_ins[0].at
    # A partner reads the drawer; walls only show to someone who may list them.
    daniel_view = await people.staff_user(firm.people["Daniel Reyes"], lena.user_id)
    assert daniel_view.wall_ids == []
    with pytest.raises(NotFound):
        await people.staff_user(grace, uuid.uuid4())


async def test_ac4_2_a_role_change_is_one_unit_of_work_audited_as_the_person(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    grace = firm.people["Grace Holloway"]
    kevin = firm.people["Kevin Osei"]
    await people.change_template(grace, kevin.user_id, "senior")
    row = (
        await seed.rows(
            "SELECT role_template, level, version FROM memberships WHERE user_id = $1",
            kevin.user_id,
        )
    )[0]
    assert (row["role_template"], row["level"], row["version"]) == ("senior", "senior", 2)
    audit = await seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'membership.role_changed' AND target_id = $2",
        firm.tenant,
        str(kevin.user_id),
    )
    assert [(a["actor_kind"], a["actor_id"]) for a in audit] == [("human", str(grace.user_id))]
    assert (
        await seed.value(
            "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'access.changed'",
            firm.tenant,
        )
        == 1
    )
    # A template carries its firm role; the last firm admin can't be moved off it.
    with pytest.raises(LastAdministrator):
        await people.change_template(grace, grace.user_id, "partner")
    # Seasonal needs an access end.
    with pytest.raises(AccessEndsRequired):
        await people.change_template(grace, kevin.user_id, "tax_preparer", "seasonal")


async def test_ac4_3_a_security_admin_changes_only_the_security_role(seed: Seeder) -> None:
    firm = await _firm(seed)
    felix = firm.people["Felix Andersen"]
    olivia = firm.people["Olivia Brandt"]
    await people.set_security_role(felix, olivia.user_id, security_admin=True)
    assert (
        await seed.value("SELECT firm_role FROM memberships WHERE user_id = $1", olivia.user_id)
        == "security_admin"
    )
    with pytest.raises(Forbidden):  # every other role control is a firm admin's
        await people.change_template(felix, olivia.user_id, "manager")
    with pytest.raises(FirmRoleHeld):
        await people.set_security_role(
            felix, firm.people["Grace Holloway"].user_id, security_admin=True
        )
    await people.set_security_role(felix, olivia.user_id, security_admin=False)
    with pytest.raises(LastAdministrator):  # Felix is now the only one
        await people.set_security_role(felix, felix.user_id, security_admin=False)


async def test_ac4_4_deactivation_ends_sessions_and_keeps_history(seed: Seeder) -> None:
    firm = await _firm(seed)
    grace = firm.people["Grace Holloway"]
    hannah = firm.people["Hannah Leclerc"]
    await seed.run(
        "INSERT INTO auth_sessions (user_id, provider, idle_expires_at, absolute_expires_at) "
        "VALUES ($1, 'workos', now() + interval '1 hour', now() + interval '1 hour')",
        hannah.user_id,
    )
    await people.deactivate(grace, hannah.user_id)
    row = (
        await seed.rows(
            "SELECT status, revoked_reason FROM memberships WHERE user_id = $1", hannah.user_id
        )
    )[0]
    assert (row["status"], row["revoked_reason"]) == ("revoked", "manual")
    assert (
        await seed.value("SELECT end_reason FROM auth_sessions WHERE user_id = $1", hannah.user_id)
        == "membership_removed"
    )
    page = await people.staff_page(grace, StaffFilters())
    gone = next(r for r in page.items if r.user_id == hannah.user_id)
    assert gone.status == "deactivated" and gone.deactivated_on is not None
    assert gone.allowed_actions == []
    assert page.tallies.seats_used == 7
    events = await seed.rows(
        "SELECT event_type FROM outbox WHERE tenant_id = $1 ORDER BY event_type", firm.tenant
    )
    assert {"membership.deactivated", "access.changed"} <= {e["event_type"] for e in events}
    with pytest.raises(NotFound):  # already deactivated
        await people.deactivate(grace, hannah.user_id)
    with pytest.raises(LastAdministrator):
        await people.deactivate(grace, grace.user_id)


async def test_ac4_6_offshore_fails_closed_while_assigned(seed: Seeder) -> None:
    firm = await _firm(seed)
    grace = firm.people["Grace Holloway"]
    kevin = firm.people["Kevin Osei"]
    entity = await seed.entity(firm.tenant)
    engagement = await seed.engagement(firm.tenant, entity, grace.user_id)
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'staff')",
        firm.tenant,
        engagement,
        kevin.user_id,
    )
    with pytest.raises(OffshoreAssignmentConflict) as refused:
        await people.update_person(grace, kevin.user_id, 1, {"offshore": True})
    assert refused.value.facts == {"assignments": 1}
    assert (
        await seed.value("SELECT offshore FROM memberships WHERE user_id = $1", kevin.user_id)
        is False
    )


async def test_attributes_save_against_the_version(seed: Seeder) -> None:
    firm = await _firm(seed)
    grace = firm.people["Grace Holloway"]
    olivia = firm.people["Olivia Brandt"]
    await people.update_person(
        grace, olivia.user_id, 1, {"title": "Tax Senior", "service_lines": ["tax"]}
    )
    found = await people.staff_user(grace, olivia.user_id)
    assert (found.row.title, found.row.service_lines, found.version) == ("Tax Senior", ["tax"], 2)
    with pytest.raises(StalePerson):
        await people.update_person(grace, olivia.user_id, 1, {"title": "Again"})
    await people.update_person(grace, olivia.user_id, 2, {"title": None})  # a null clears
    assert (await people.staff_user(grace, olivia.user_id)).row.title is None
    with pytest.raises(AccessEndsRequired):
        await people.update_person(
            grace, firm.people["Lena Park"].user_id, 1, {"access_ends_on": None}
        )
    with pytest.raises(Forbidden):  # a partner reads people and changes nobody
        await people.update_person(firm.people["Daniel Reyes"], olivia.user_id, 3, {"title": "X"})


async def test_ac5_1_role_templates_count_the_members_and_lock_the_agent(seed: Seeder) -> None:
    firm = await _firm(seed)
    grace = firm.people["Grace Holloway"]
    found = await people.role_templates(grace)
    counts = {t.key: t.member_count for t in found.templates}
    assert counts == {
        "partner": 1,
        "manager": 1,
        "tax_reviewer": 1,
        "senior": 1,
        "staff": 0,
        "tax_preparer": 2,
        "firm_admin": 1,
        "it_security": 1,
    }
    assert sum(counts.values()) == 8
    assert len(found.grid) == 17  # sixteen rows and the locked agent row
    agent = found.grid[-1]
    assert agent.locked and set(agent.cells.values()) == {"locked"}
    assert "report.release" in agent.actions and "tin.reveal" in agent.actions
    release = next(g for g in found.grid if g.key == "release_audit_report")
    assert release.source == "matrix" and release.cells["partner"] == "allow"
    # A stricter-only override narrows the grid for this firm.
    await seed.run(
        "INSERT INTO firm_policy_overrides (tenant_id, action, role, decision, reason, set_by) "
        "VALUES ($1, 'tin.reveal', 'manager', 'deny', 'Firm policy', $2)",
        firm.tenant,
        grace.user_id,
    )
    narrowed = await people.role_templates(grace)
    tin = next(g for g in narrowed.grid if g.key == "reveal_tin")
    assert tin.cells["manager"] == "deny" and tin.cells["partner"] == "allow"


# --- security review fixes (TASK-1150 follow-up) -----------------------------------------------


async def _issued_email(seed: Seeder, user: uuid.UUID) -> str:
    return cast(str, await seed.value("SELECT email FROM users WHERE id = $1", user))


async def _pending(seed: Seeder, invitation: uuid.UUID) -> tuple[str, int]:
    status = cast(
        str, await seed.value("SELECT status FROM staff_invitations WHERE id = $1", invitation)
    )
    tokens = cast(
        int,
        await seed.value(
            "SELECT count(*) FROM staff_invitation_tokens WHERE invitation_id = $1", invitation
        ),
    )
    return status, tokens


async def test_deactivating_someone_revokes_invitations_from_and_for_them(seed: Seeder) -> None:
    firm = await _firm(seed)
    await firm.seats(20)
    grace = firm.people["Grace Holloway"]
    second = await firm.add("Second Admin", firm_role="firm_admin", level="admin")
    sent = await people.invite(
        second, InviteTerms(email="personal@example.test", firm_role="firm_admin")
    )
    assert await issue_staff_invitation_token(firm.tenant, sent) is not None
    for_them = uuid.uuid4()  # sent before they joined: a pending invitation to their own email
    await seed.run(
        "INSERT INTO staff_invitations (id, tenant_id, email, invited_by, expires_at) "
        "VALUES ($1, $2, $3, $4, now() + interval '14 days')",
        for_them,
        firm.tenant,
        await _issued_email(seed, second.user_id),
        grace.user_id,
    )
    await people.deactivate(grace, second.user_id)
    assert await _pending(seed, sent) == ("revoked", 0)
    assert (await _pending(seed, for_them))[0] == "revoked"
    revoked = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'staff_invitation.revoked' AND target_id = ANY($2::text[])",
        firm.tenant,
        [str(sent), str(for_them)],
    )
    assert revoked == 2


async def test_the_legacy_revoke_and_a_demotion_revoke_the_persons_invitations(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    await firm.seats(20)
    grace = firm.people["Grace Holloway"]
    second = await firm.add("Second Admin", firm_role="firm_admin", level="admin")
    third = await firm.add("Third Admin", firm_role="firm_admin", level="admin")
    by_second = await people.invite(
        second, InviteTerms(email="a@example.test", role_template="staff")
    )
    by_third = await people.invite(
        third, InviteTerms(email="b@example.test", role_template="staff")
    )
    await staff_revoke(grace, second.user_id)  # SPEC-024's route
    await people.change_template(grace, third.user_id, "partner")  # no longer a firm admin
    assert (await _pending(seed, by_second))[0] == "revoked"
    assert (await _pending(seed, by_third))[0] == "revoked"


async def test_an_invitation_from_someone_who_has_left_cannot_be_accepted(seed: Seeder) -> None:
    firm = await _firm(seed)
    await firm.seats(20)
    second = await firm.add("Second Admin", firm_role="firm_admin", level="admin")
    email = f"leaver.{uuid.uuid4().hex[:6]}@example.test"
    sent = await people.invite(second, InviteTerms(email=email, role_template="staff"))
    issued = await issue_staff_invitation_token(firm.tenant, sent)
    assert issued is not None
    # The inviter leaves by a path that touches no invitation (directory sync, a fixture).
    await seed.run(
        "UPDATE memberships SET status = 'revoked', revoked_at = now() WHERE user_id = $1",
        second.user_id,
    )
    with pytest.raises(StaffInvitationNotFound):
        await accept_staff_invitation(
            VerifiedIdentity("https://probe.test", uuid.uuid4().hex, datetime.now(UTC), email),
            issued.token,
        )


async def test_sign_ins_show_only_this_firms_active_membership(seed: Seeder) -> None:
    firm = await _firm(seed)
    grace = firm.people["Grace Holloway"]
    kevin = firm.people["Kevin Osei"]
    joined = cast(
        datetime,
        await seed.value("SELECT created_at FROM memberships WHERE user_id = $1", kevin.user_id),
    )

    async def session_at(at: datetime) -> None:
        await seed.run(
            "INSERT INTO auth_sessions (user_id, provider, mfa_at, created_at, idle_expires_at, "
            "absolute_expires_at) VALUES ($1, 'workos', $2, $2, $2, $2)",
            kevin.user_id,
            at,
        )

    await session_at(joined - timedelta(days=30))  # before he joined: not this firm's
    await session_at(joined + timedelta(minutes=5))  # this firm's
    found = await people.staff_user(grace, kevin.user_id)
    assert [s.at for s in found.recent_sign_ins] == [joined + timedelta(minutes=5)]
    assert found.row.last_sign_in_at == joined + timedelta(minutes=5)
    # A consultant who belongs to another firm too: no session names a firm, so none shows.
    other = await seed.firm()
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')",
        other,
        kevin.user_id,
    )
    await session_at(joined + timedelta(minutes=20))
    consultant = await people.staff_user(grace, kevin.user_id)
    assert consultant.recent_sign_ins == [] and consultant.row.last_sign_in_at is None
    # An ex-member shows nothing after leaving, and no last sign-in.
    await people.deactivate(grace, firm.people["Hannah Leclerc"].user_id)
    hannah = firm.people["Hannah Leclerc"]
    await session_at_user(seed, hannah.user_id, datetime.now(UTC) + timedelta(minutes=1))
    gone = await people.staff_user(grace, hannah.user_id)
    assert gone.recent_sign_ins == [] and gone.row.last_sign_in_at is None


async def session_at_user(seed: Seeder, user: uuid.UUID, at: datetime) -> None:
    await seed.run(
        "INSERT INTO auth_sessions (user_id, provider, mfa_at, created_at, idle_expires_at, "
        "absolute_expires_at) VALUES ($1, 'workos', $2, $2, $2, $2)",
        user,
        at,
    )


async def test_the_template_follows_the_firm_role(seed: Seeder) -> None:
    firm = await _firm(seed)
    felix = firm.people["Felix Andersen"]
    olivia = firm.people["Olivia Brandt"]
    await people.set_security_role(felix, olivia.user_id, security_admin=True)
    granted = await people.staff_user(felix, olivia.user_id)
    assert granted.row.role_template == "it_security"
    await people.set_security_role(felix, olivia.user_id, security_admin=False)
    removed = await people.staff_user(felix, olivia.user_id)
    assert removed.row.role_template != "it_security"


async def test_a_reactivated_member_does_not_keep_an_old_admin_template(seed: Seeder) -> None:
    firm = await _firm(seed)
    await firm.seats(20)
    grace = firm.people["Grace Holloway"]
    second = await firm.add(
        "Second Admin", firm_role="firm_admin", level="admin", template="firm_admin"
    )
    await people.deactivate(grace, second.user_id)
    email = await _issued_email(seed, second.user_id)
    sent = await people.invite(grace, InviteTerms(email=email))  # SPEC-024: no firm role
    issued = await issue_staff_invitation_token(firm.tenant, sent)
    assert issued is not None
    subject = cast(
        str, await seed.value("SELECT idp_subject FROM users WHERE id = $1", second.user_id)
    )
    await accept_staff_invitation(
        VerifiedIdentity("https://probe.test", subject, datetime.now(UTC), email), issued.token
    )
    row = (
        await seed.rows(
            "SELECT status, firm_role, role_template FROM memberships WHERE user_id = $1",
            second.user_id,
        )
    )[0]
    assert (row["status"], row["firm_role"]) == ("active", None)
    assert row["role_template"] != "firm_admin"


async def test_seats_unset_fail_closed_for_a_real_firm(seed: Seeder) -> None:
    firm = await _firm(seed)  # no plan.seats
    with pytest.raises(SeatsNotProvisioned):
        await people.invite(
            firm.people["Grace Holloway"],
            InviteTerms(email="x@example.test", role_template="staff"),
        )
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", firm.tenant)
    await people.invite(
        firm.people["Grace Holloway"], InviteTerms(email="x@example.test", role_template="staff")
    )


async def test_seats_are_rechecked_at_acceptance_and_held_under_a_lock(seed: Seeder) -> None:
    firm = await _firm(seed)
    await firm.seats(9)
    grace = firm.people["Grace Holloway"]
    results = await asyncio.gather(
        people.invite(grace, InviteTerms(email="one@example.test", role_template="staff")),
        people.invite(grace, InviteTerms(email="two@example.test", role_template="staff")),
        return_exceptions=True,
    )
    assert sum(isinstance(r, SeatsFull) for r in results) == 1
    sent = next(r for r in results if isinstance(r, uuid.UUID))
    issued = await issue_staff_invitation_token(firm.tenant, sent)
    assert issued is not None
    await firm.seats(8)  # provisioning lowered the seats while the invitation was pending
    email = cast(str, await seed.value("SELECT email FROM staff_invitations WHERE id = $1", sent))
    with pytest.raises(SeatsFull):
        await accept_staff_invitation(
            VerifiedIdentity("https://probe.test", uuid.uuid4().hex, datetime.now(UTC), email),
            issued.token,
        )
