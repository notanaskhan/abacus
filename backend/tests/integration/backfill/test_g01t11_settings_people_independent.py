# ac-test-author: ayushkbhatia
"""G-01 AC1.2 to AC1.8, AC3.3 to AC3.5, AC4.2 to AC4.4, AC4.7, AC5.1 to AC5.3 (G-01-T04, T05;
G-01-T11): firm settings and people v2, read from G-01 §3.1 to §3.5, §4.3, the contract
`docs/contracts/firm-settings.md`, the identity permission matrix, `role-templates.yaml` and
DEC-35, DEC-170, DEC-285, DEC-286.

HTTP through `create_app()` against the migrated Postgres, with `firm_settings.v2` on; the
agent and system principals through `identity.api.authorise` and the compiled matrix `RULES`.
Decisions followed instead of the epic's wording:
- DEC-170: sections are `profile`, `defaults`, `plan`; Plan & seats answers 404 to a security
  admin (AC1.7 "absent from the response").
- DEC-285: the seat total is the provisioning-only key `plan.seats`; a pending invitation holds
  a seat (AC3.4).
- DEC-286: `GET /v1/firm/staff` stays `firm.manage_users` (so partner and IT views are the
  person drawer and the role templates, `firm.read_people`); the last firm admin and the last
  security admin are kept (409 `last_admin`); `security_admin` only for someone without another
  firm role (409 `firm_role_held`).
- The grid's drift rule is the one `role-templates.yaml` states for `source: matrix` rows: an
  `allow` cell is held (any non-deny decision) by one of the template's roles on every action,
  and a `deny` or `delegated` cell by none of them as a plain `allow`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final, cast

import asyncpg
import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import (
    RULES,
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    issue_staff_invitation_token,
)
from abacus.modules.identity.context import (
    _ISSUER,  # pyright: ignore[reportPrivateUsage] -- a test-only agent principal
)

from .support import Migrated, Net, Person, Seeder

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
FLAG: Final = "firm_settings.v2"
STAFF: Final = "/v1/firm/staff"
# G-01 §4.3: the actions this family adds or uses, every one denied to agent and system.
FAMILY_ACTIONS: Final = (
    "firm.read_settings",
    "firm.manage_settings",
    "firm.read_people",
    "firm.manage_users",
    "security_role.assign",
)
# G-01 §3.5 AC5.1: eight templates; AC5.3: the rows from "Approve source document" through
# "Reveal masked TIN/SSN" are the agent's never-list (I-AGENT-NEVER).
TEMPLATES: Final = (
    "partner",
    "manager",
    "tax_reviewer",
    "senior",
    "staff",
    "tax_preparer",
    "firm_admin",
    "it_security",
)
AGENT_NEVER_LABELS: Final = (
    "Approve source document",
    "Adopt agent work (L1 preparer)",
    "Reviewer sign-off L2/L3",
    "Partner sign-off L4",
    "Materiality, significant risks, deficiency severity, opinion",
    "Final return approval",
    "Export to tax engine",
    "Approve AJE within / above threshold",
    "Post to GL",
    "Release audit report",
    "Reveal masked TIN/SSN (logged)",
)


@dataclass(frozen=True)
class Firm:
    net: Net
    seed: Seeder
    tenant_id: uuid.UUID
    grace: Person  # Firm Admin

    async def person(
        self,
        firm_role: str | None = None,
        *,
        level: str | None = None,
        template: str | None = None,
    ) -> Person:
        who = await self.seed.person(self.tenant_id, firm_role)
        if level is not None or template is not None:
            await self.seed.run(
                "UPDATE memberships SET level = coalesce($3, level), "
                "role_template = coalesce($4, role_template) "
                "WHERE tenant_id = $1 AND user_id = $2",
                self.tenant_id,
                who.user_id,
                level,
                template,
            )
        return who

    async def seats(self, total: int) -> None:
        await self.seed.run(
            "INSERT INTO firm_settings (tenant_id, section, key, value, updated_by) "
            "VALUES ($1, 'plan', 'seats', to_jsonb($2::int), $3)",
            self.tenant_id,
            total,
            self.grace.user_id,
        )

    async def audit(self, action: str) -> list[asyncpg.Record]:
        return await self.seed.rows(
            "SELECT actor_kind, actor_id, target_id, before_ref, after_ref FROM audit_events "
            "WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
            self.tenant_id,
            action,
        )

    async def outbox(self, event_type: str) -> int:
        return int(
            str(
                await self.seed.value(
                    "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = $2",
                    self.tenant_id,
                    event_type,
                )
            )
        )

    async def membership(self, who: Person) -> asyncpg.Record:
        return (
            await self.seed.rows(
                "SELECT firm_role, level, role_template, status, office_id, offshore, "
                "access_ends_on FROM memberships WHERE tenant_id = $1 AND user_id = $2",
                self.tenant_id,
                who.user_id,
            )
        )[0]


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'G-01-T11')",
        tenant_id,
        FLAG,
    )
    grace = await seed.person(tenant_id, "firm_admin")
    return Firm(net, seed, tenant_id, grace)


def _detail(body: object) -> object:
    return cast(Json, body).get("detail")


async def _section(firm: Firm, who: Person, section: str = "profile") -> Json:
    response = await firm.net.call("GET", f"/v1/firm/settings/{section}", who)
    assert response.status_code == 200, response.text
    return cast(Json, response.json())


def _values(section: Json) -> dict[str, object]:
    return {cast(str, v["key"]): v["value"] for v in cast(list[Json], section["values"])}


def _key(section: Json, name: str) -> str:
    """The key as the section names it (bare or section-qualified)."""
    for key in _values(section):
        if key == name or key.endswith(f".{name}"):
            return key
    raise AssertionError(f"{name} is not a key of {section['section']}: {list(_values(section))}")


# ================================================================================================
# ADM-01: version 409, display name 422, region immutable, partner and IT views (AC1.2 to AC1.8)
# ================================================================================================


async def test_ac1_2_a_save_writes_one_audit_row_naming_grace_and_never_the_value(
    firm: Firm,
) -> None:
    profile = await _section(firm, firm.grace)
    website = _key(profile, "website")
    marker = f"https://firm-{uuid.uuid4().hex[:8]}.example.test"
    stale = await firm.net.call(
        "PATCH",
        "/v1/firm/settings/profile",
        firm.grace,
        body={"version": profile["version"], "values": {website: marker}},
        mfa=False,
    )
    assert stale.status_code == 403, stale.text  # fresh MFA (`firm.manage_settings`)
    saved = await firm.net.call(
        "PATCH",
        "/v1/firm/settings/profile",
        firm.grace,
        body={"version": profile["version"], "values": {website: marker}},
    )
    assert saved.status_code == 200, saved.text
    assert _values(await _section(firm, firm.grace))[website] == marker
    rows = await firm.audit("firm_setting.updated")
    assert len(rows) == 1
    assert (rows[0]["actor_kind"], rows[0]["actor_id"]) == ("human", str(firm.grace.user_id))
    assert marker not in f"{rows[0]['before_ref']}{rows[0]['after_ref']}"  # keys, never values


async def test_ac1_4_a_save_with_the_version_read_before_another_save_answers_409_stale_version(
    firm: Firm,
) -> None:
    second_admin = await firm.person("firm_admin")
    profile = await _section(firm, firm.grace)
    website = _key(profile, "website")
    first = await firm.net.call(
        "PATCH",
        "/v1/firm/settings/profile",
        firm.grace,
        body={"version": profile["version"], "values": {website: "https://a.example.test"}},
    )
    assert first.status_code == 200, first.text
    second = await firm.net.call(
        "PATCH",
        "/v1/firm/settings/profile",
        second_admin,
        body={"version": profile["version"], "values": {website: "https://b.example.test"}},
    )
    assert second.status_code == 409, second.text
    assert _detail(second.json()) == "stale_version"
    assert _values(await _section(firm, firm.grace))[website] == "https://a.example.test"
    assert len(await firm.audit("firm_setting.updated")) == 1


async def test_ac1_3_an_emptied_display_name_answers_422_display_name_required(
    firm: Firm,
) -> None:
    profile = await _section(firm, firm.grace)
    display_name = _key(profile, "display_name")
    for empty in ("", None):
        refused = await firm.net.call(
            "PATCH",
            "/v1/firm/settings/profile",
            firm.grace,
            body={"version": profile["version"], "values": {display_name: empty}},
        )
        assert refused.status_code == 422, (empty, refused.text)
        assert _detail(refused.json()) == "display_name_required", refused.text
    assert await firm.audit("firm_setting.updated") == []


async def test_ac1_5_region_is_never_writable_through_any_section_or_by_the_app_role(
    firm: Firm, migrated_db: Migrated
) -> None:
    for section in ("profile", "defaults", "plan"):
        read = await _section(firm, firm.grace, section)
        assert not any(k == "region" or k.endswith(".region") for k in _values(read))
        for key in ("region", f"{section}.region"):
            refused = await firm.net.call(
                "PATCH",
                f"/v1/firm/settings/{section}",
                firm.grace,
                body={"version": read["version"], "values": {key: "eu"}},
            )
            assert refused.status_code == 422, (section, key, refused.text)
            assert _detail(refused.json()) == "unknown_setting", refused.text
    assert await firm.seed.value(
        "SELECT region FROM firms WHERE tenant_id = $1", firm.tenant_id
    ) == ("us")
    # AC1.5: only provisioning changes it; the application's database role holds no UPDATE on it.
    app_role = Seeder(migrated_db.app_url.replace("postgresql+asyncpg://", "postgresql://"))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app_role.run("UPDATE firms SET region = 'us' WHERE tenant_id = $1", firm.tenant_id)


async def test_ac1_6_a_partner_reads_the_settings_and_cannot_write_them(firm: Firm) -> None:
    daniel = await firm.person(level="partner", template="partner")
    overview = await firm.net.call("GET", "/v1/firm/settings/overview", daniel)
    assert overview.status_code == 200, overview.text
    profile = await _section(firm, daniel)
    assert "firm.manage_settings" not in cast(list[str], profile["allowed_actions"])
    assert profile["read_only_reason"] is not None
    refused = await firm.net.call(
        "PATCH",
        "/v1/firm/settings/profile",
        daniel,
        body={"version": profile["version"], "values": {_key(profile, "website"): "x"}},
    )
    assert refused.status_code == 403, refused.text
    assert await firm.audit("firm_setting.updated") == []


async def test_ac1_7_it_security_reads_read_only_without_plan_and_seats(firm: Firm) -> None:
    felix = await firm.person("security_admin", level="admin", template="it_security")
    profile = await _section(firm, felix)
    assert "firm.manage_settings" not in cast(list[str], profile["allowed_actions"])
    plan = await firm.net.call("GET", "/v1/firm/settings/plan", felix)
    assert plan.status_code == 404, plan.text  # absent, not hidden (DEC-170)
    assert plan.json() == {"detail": "not found"}
    overview = await firm.net.call("GET", "/v1/firm/settings/overview", felix)
    assert overview.status_code == 200, overview.text
    sections = cast(list[Json], overview.json()["sections"])
    assert not [s for s in sections if s["key"] == "plan" and s["visible"]]
    refused = await firm.net.call(
        "PATCH",
        "/v1/firm/settings/profile",
        felix,
        body={"version": profile["version"], "values": {_key(profile, "website"): "x"}},
    )
    assert refused.status_code == 403, refused.text
    # Grace (Firm Admin) still reads Plan & seats.
    assert (await firm.net.call("GET", "/v1/firm/settings/plan", firm.grace)).status_code == 200


async def test_ac1_8_staff_without_a_firm_role_get_404_on_the_overview_and_sections(
    firm: Firm,
) -> None:
    kevin = await firm.person(level="staff", template="staff")
    for path in ("/v1/firm/settings/overview", "/v1/firm/settings/profile"):
        refused = await firm.net.call("GET", path, kevin)
        assert refused.status_code == 404, (path, refused.text)
        assert refused.json() == {"detail": "not found"}


async def test_ac4_1_partner_and_it_views_read_a_person_and_the_role_templates(
    firm: Firm,
) -> None:
    """`firm.read_people`: firm admin, security admin and partners by level; staff are refused
    (contract §6: 403 with no action)."""
    daniel = await firm.person(level="partner", template="partner")
    felix = await firm.person("security_admin", level="admin", template="it_security")
    kevin = await firm.person(level="staff", template="staff")
    for reader in (firm.grace, daniel, felix):
        person = await firm.net.call("GET", f"{STAFF}/{kevin.user_id}", reader)
        assert person.status_code == 200, person.text
        assert person.json()["row"]["user_id"] == str(kevin.user_id)
        grid = await firm.net.call("GET", "/v1/firm/role-templates", reader)
        assert grid.status_code == 200, grid.text
    for path in (f"{STAFF}/{daniel.user_id}", "/v1/firm/role-templates"):
        refused = await firm.net.call("GET", path, kevin)
        assert refused.status_code in (403, 404), (path, refused.text)
        assert "row" not in refused.json() and "grid" not in refused.json()
    # A partner reads people but never writes them.
    refused = await firm.net.call(
        "PUT", f"{STAFF}/{kevin.user_id}/role", daniel, body={"role_template": "senior"}
    )
    assert refused.status_code == 403, refused.text


async def test_ac4_1_another_firms_person_answers_404(firm: Firm, seed: Seeder) -> None:
    other = await seed.firm()
    stranger = await seed.person(other)
    response = await firm.net.call("GET", f"{STAFF}/{stranger.user_id}", firm.grace)
    assert response.status_code == 404, response.text


# ================================================================================================
# Invitations: seats_full, 14-day single use, validation (AC3.3 to AC3.5; DEC-35, DEC-285)
# ================================================================================================


async def _invite(firm: Firm, email: str, **extra: object) -> httpx.Response:
    body: Json = {"email": email, "role_template": "staff", "level": "staff", **extra}
    return await firm.net.call("POST", f"{STAFF}/invitations", firm.grace, body=body)


async def test_ac3_3_a_full_firm_answers_409_seats_full_with_used_and_total(firm: Firm) -> None:
    await firm.seats(2)
    await firm.person(level="staff", template="staff")  # Grace and one member hold both seats
    refused = await _invite(firm, f"new-{uuid.uuid4().hex[:6]}@example.test")
    assert refused.status_code == 409, refused.text
    body = cast(Json, refused.json())
    assert body["detail"] == "seats_full"
    assert body["facts"] == {"used": 2, "total": 2}
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM staff_invitations WHERE tenant_id = $1", firm.tenant_id
        )
        == 0
    )


async def test_ac3_4_a_pending_invitation_holds_a_seat(firm: Firm) -> None:
    await firm.seats(2)
    first = await _invite(firm, "first@example.test")
    assert first.status_code == 201, first.text
    refused = await _invite(firm, "second@example.test")
    assert refused.status_code == 409, refused.text
    assert refused.json()["facts"] == {"used": 2, "total": 2}


async def test_ac3_4_the_invitation_lasts_14_days_is_single_use_and_carries_its_attributes(
    firm: Firm,
) -> None:
    await firm.seats(10)
    office = cast(
        uuid.UUID,
        await firm.seed.value(
            "INSERT INTO offices (tenant_id, name) VALUES ($1, 'Denver') RETURNING id",
            firm.tenant_id,
        ),
    )
    ends = date(2027, 10, 31)
    email = f"lena-{uuid.uuid4().hex[:6]}@example.test"
    sent = await _invite(
        firm,
        email,
        role_template="tax_preparer",
        level="seasonal",
        office_id=str(office),
        service_lines=["tax"],
        access_ends_on=ends.isoformat(),
        offshore=False,
        display_name="Lena Park",
    )
    assert sent.status_code == 201, sent.text
    invitation_id = uuid.UUID(cast(str, sent.json()["id"]))
    span = await firm.seed.value(
        "SELECT expires_at - created_at FROM staff_invitations WHERE id = $1", invitation_id
    )
    # DEC-35: 14 days (ending at the firm's business time, so within a day either side).
    assert timedelta(days=13) < cast(timedelta, span) <= timedelta(days=15)
    issued = await issue_staff_invitation_token(firm.tenant_id, invitation_id)
    assert issued is not None
    subject, headers = firm.net.newcomer(email)
    accepted = await firm.net.http.post(
        "/v1/invitations/staff/accept", json={"token": issued.token}, headers=headers
    )
    assert accepted.status_code == 200, accepted.text
    again = await firm.net.http.post(
        "/v1/invitations/staff/accept",
        json={"token": issued.token},
        headers=firm.net.newcomer(email)[1],
    )
    assert again.status_code == 404, again.text  # single use: a used link is not found
    user_id = cast(
        uuid.UUID, await firm.seed.value("SELECT id FROM users WHERE idp_subject = $1", subject)
    )
    lena = await firm.membership(Person(user_id, firm.tenant_id, subject))
    assert (lena["role_template"], lena["level"], lena["office_id"]) == (
        "tax_preparer",
        "seasonal",
        office,
    )
    assert (lena["access_ends_on"], lena["offshore"], lena["status"]) == (ends, False, "active")


async def test_ac3_4_an_expired_invitation_does_not_join(firm: Firm) -> None:
    await firm.seats(10)
    email = f"late-{uuid.uuid4().hex[:6]}@example.test"
    sent = await _invite(firm, email)
    assert sent.status_code == 201, sent.text
    invitation_id = uuid.UUID(cast(str, sent.json()["id"]))
    issued = await issue_staff_invitation_token(firm.tenant_id, invitation_id)
    assert issued is not None
    await firm.seed.run(
        "UPDATE staff_invitations SET expires_at = now() - interval '1 minute' WHERE id = $1",
        invitation_id,
    )
    subject, headers = firm.net.newcomer(email)
    late = await firm.net.http.post(
        "/v1/invitations/staff/accept", json={"token": issued.token}, headers=headers
    )
    assert late.status_code in (404, 410), late.text
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM memberships m JOIN users u ON u.id = m.user_id "
            "WHERE m.tenant_id = $1 AND u.idp_subject = $2",
            firm.tenant_id,
            subject,
        )
        == 0
    )


async def test_ac3_5_a_seasonal_invite_needs_an_access_end_and_a_member_is_already_one(
    firm: Firm,
) -> None:
    await firm.seats(10)
    seasonal = await _invite(
        firm, "season@example.test", role_template="tax_preparer", level="seasonal"
    )
    assert seasonal.status_code == 422, seasonal.text
    assert seasonal.json()["detail"] == "access_ends_required"
    member_email = cast(
        str,
        await firm.seed.value("SELECT email FROM users WHERE id = $1", firm.grace.user_id),
    )
    already = await _invite(firm, member_email)
    assert already.status_code == 409, already.text
    assert already.json()["detail"] == "already_member"


# ================================================================================================
# Role change with fresh MFA and audit; last admin; deactivation keeps attribution (AC4.2 to 4.4)
# ================================================================================================


async def test_ac4_2_a_role_change_needs_fresh_mfa_and_is_audited_as_grace(firm: Firm) -> None:
    kevin = await firm.person(level="staff", template="tax_preparer")
    path = f"{STAFF}/{kevin.user_id}/role"
    body: Json = {"role_template": "senior", "level": "senior"}
    stale = await firm.net.call("PUT", path, firm.grace, body=body, mfa=False)
    assert stale.status_code == 403, stale.text
    assert (await firm.membership(kevin))["role_template"] == "tax_preparer"
    changed = await firm.net.call("PUT", path, firm.grace, body=body)
    assert changed.status_code == 200, changed.text
    row = await firm.membership(kevin)
    assert (row["role_template"], row["level"]) == ("senior", "senior")
    audited = await firm.audit("membership.role_changed")
    assert [(r["actor_kind"], r["actor_id"]) for r in audited] == [
        ("human", str(firm.grace.user_id))
    ]
    assert await firm.outbox("access.changed") >= 1
    person = await firm.net.call("GET", f"{STAFF}/{kevin.user_id}", firm.grace)
    assert person.json()["row"]["role_template"] == "senior"


async def test_ac4_3_the_last_firm_admin_cannot_be_moved_or_deactivated(firm: Firm) -> None:
    to_staff = await firm.net.call(
        "PUT",
        f"{STAFF}/{firm.grace.user_id}/role",
        firm.grace,
        body={"role_template": "staff", "level": "staff"},
    )
    assert to_staff.status_code == 409, to_staff.text
    assert to_staff.json()["detail"] == "last_admin"
    gone = await firm.net.call(
        "POST", f"{STAFF}/{firm.grace.user_id}/deactivate", firm.grace, body={"reason": "manual"}
    )
    assert gone.status_code == 409, gone.text
    assert gone.json()["detail"] == "last_admin"
    row = await firm.membership(firm.grace)
    assert (row["firm_role"], row["status"]) == ("firm_admin", "active")


async def test_ac4_3_the_last_security_admin_stays_and_another_firm_role_is_refused(
    firm: Firm,
) -> None:
    felix = await firm.person("security_admin", level="admin", template="it_security")
    path = f"{STAFF}/{felix.user_id}/security-role"
    last = await firm.net.call("PUT", path, felix, body={"security_admin": False})
    assert last.status_code == 409, last.text
    assert last.json()["detail"] == "last_admin"
    assert (await firm.membership(felix))["firm_role"] == "security_admin"
    # Felix grants security_admin to a staff member, but not to Grace (a firm role held).
    kevin = await firm.person(level="staff", template="staff")
    granted = await firm.net.call(
        "PUT", f"{STAFF}/{kevin.user_id}/security-role", felix, body={"security_admin": True}
    )
    assert granted.status_code == 200, granted.text
    assert (await firm.membership(kevin))["firm_role"] == "security_admin"
    held = await firm.net.call(
        "PUT",
        f"{STAFF}/{firm.grace.user_id}/security-role",
        felix,
        body={"security_admin": True},
    )
    assert held.status_code == 409, held.text
    assert held.json()["detail"] == "firm_role_held"
    audited = await firm.audit("membership.security_role_changed")
    assert [(r["actor_kind"], r["actor_id"]) for r in audited] == [("human", str(felix.user_id))]
    # Felix changes no other role (AC4.3: "Only firm admins change these roles").
    refused = await firm.net.call(
        "PUT", f"{STAFF}/{kevin.user_id}/role", felix, body={"role_template": "senior"}
    )
    assert refused.status_code == 403, refused.text
    stale = await firm.net.call("PUT", path, felix, body={"security_admin": False}, mfa=False)
    assert stale.status_code == 403, stale.text


async def test_ac4_4_deactivation_frees_the_seat_and_keeps_every_attribution(
    firm: Firm,
) -> None:
    await firm.seats(10)
    ada = await firm.person("firm_admin", level="admin", template="firm_admin")
    kevin = await firm.person(level="staff", template="staff")
    site = await firm.seed.site(firm.tenant_id, ada.user_id, "Attribution")
    await firm.seed.member(site, ada, "manager")
    # Ada acts first: her role change on Kevin is audited as hers.
    changed = await firm.net.call(
        "PUT",
        f"{STAFF}/{kevin.user_id}/role",
        ada,
        body={"role_template": "senior", "level": "senior"},
    )
    assert changed.status_code == 200, changed.text
    before = await firm.seed.rows(
        "SELECT id, actor_kind, actor_id, action FROM audit_events WHERE tenant_id = $1 "
        "AND actor_id = $2 ORDER BY seq",
        firm.tenant_id,
        str(ada.user_id),
    )
    assert [r["action"] for r in before] == ["membership.role_changed"]
    listed = await firm.net.call("GET", STAFF, firm.grace)
    used = cast(Json, listed.json()["tallies"])["seats_used"]

    wrong = await firm.net.call(
        "POST", f"{STAFF}/{ada.user_id}/deactivate", firm.grace, body={"reason": "access_ended"}
    )
    assert wrong.status_code == 422, wrong.text
    assert wrong.json()["detail"] == "deactivation_reason_invalid"
    stale = await firm.net.call(
        "POST",
        f"{STAFF}/{ada.user_id}/deactivate",
        firm.grace,
        body={"reason": "manual"},
        mfa=False,
    )
    assert stale.status_code == 403, stale.text
    gone = await firm.net.call(
        "POST", f"{STAFF}/{ada.user_id}/deactivate", firm.grace, body={"reason": "manual"}
    )
    assert gone.status_code == 200, gone.text
    assert (await firm.membership(ada))["status"] == "revoked"
    audited = await firm.audit("membership.deactivated")
    assert [(r["actor_kind"], r["actor_id"]) for r in audited] == [
        ("human", str(firm.grace.user_id))
    ]
    assert await firm.outbox("membership.deactivated") == 1
    assert await firm.outbox("access.changed") >= 1
    # Every row Ada wrote is still hers, unchanged (ADR-004, ADR-007).
    after = await firm.seed.rows(
        "SELECT id, actor_kind, actor_id, action FROM audit_events WHERE tenant_id = $1 "
        "AND actor_id = $2 ORDER BY seq",
        firm.tenant_id,
        str(ada.user_id),
    )
    assert after == before
    # Her engagement role stays as history.
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM engagement_members WHERE engagement_id = $1 AND user_id = $2",
            site.engagement_id,
            ada.user_id,
        )
        == 1
    )
    # The seat frees; Ada can no longer administer the firm.
    listed = await firm.net.call("GET", STAFF, firm.grace)
    assert cast(Json, listed.json()["tallies"])["seats_used"] == cast(int, used) - 1
    locked_out = await firm.net.call("GET", STAFF, ada, tenant=firm.tenant_id)
    assert locked_out.status_code in (403, 404), locked_out.text


# ================================================================================================
# INV-1: agent and system refused (AC4.7); grid drift and I-AGENT-NEVER (AC5.1 to AC5.3)
# ================================================================================================


def _agent(firm: Firm, actions: tuple[str, ...]) -> AgentContext:
    person = AuthContext(
        TenantContext(firm.tenant_id, "human", str(firm.grace.user_id)),
        firm.grace.user_id,
        uuid.uuid4(),
        "firm_admin",
        datetime.now(UTC) - timedelta(minutes=1),
    )
    run = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(firm.tenant_id, "agent", f"agent:probe:{run}", firm.grace.user_id),
        agent_id="probe",
        agent_run_id=run,
        engagement_id=None,
        task_scope=frozenset(actions),
        initiator=person,
        issued_by=_ISSUER,
    )


async def test_ac4_7_agent_and_system_are_refused_every_settings_and_people_action(
    firm: Firm,
) -> None:
    for action in FAMILY_ACTIONS:
        decisions = RULES[action].decisions
        for principal in ("agent", "system"):
            assert decisions.get(principal, "deny") == "deny", (action, decisions)
        assert not {r for r, d in decisions.items() if r.startswith("client_") and d != "deny"}
        with pytest.raises(Forbidden):
            await authorise(_agent(firm, FAMILY_ACTIONS), action, Resource.firm(firm.tenant_id))


async def _grid(firm: Firm) -> Json:
    response = await firm.net.call("GET", "/v1/firm/role-templates", firm.grace)
    assert response.status_code == 200, response.text
    return cast(Json, response.json())


async def test_ac5_1_eight_templates_and_sixteen_rows_with_matrix_sources_where_actions_exist(
    firm: Firm,
) -> None:
    grid = await _grid(firm)
    templates = cast(list[Json], grid["templates"])
    assert [t["key"] for t in templates] == list(TEMPLATES)
    rows = [r for r in cast(list[Json], grid["grid"]) if not r["locked"]]
    assert len(rows) == 16  # the capability rows; the locked agent row is AC5.3's
    for row in rows:
        actions = cast(list[str], row["actions"])
        assert set(cast(Json, row["cells"])) == set(TEMPLATES), row["key"]
        if row["source"] == "matrix":
            assert actions and all(a in RULES for a in actions), row
        if actions and all(a in RULES for a in actions):
            assert row["source"] in ("matrix", "policy"), row


def _roles(template: str) -> frozenset[str]:
    """`role-templates.yaml`'s `roles` per template (the contract, typed here)."""
    return frozenset(
        {
            "partner": (
                "firm_partner",
                "engagement_partner",
                "practice_leader",
                "quality_partner",
            ),
            "manager": ("manager",),
            "tax_reviewer": ("manager", "senior"),
            "senior": ("senior",),
            "staff": ("staff",),
            "tax_preparer": ("staff",),
            "firm_admin": ("firm_admin", "client_service"),
            "it_security": ("security_admin",),
        }[template]
    )


async def test_ac5_2_every_matrix_sourced_cell_agrees_with_the_compiled_matrix(
    firm: Firm,
) -> None:
    rows = cast(list[Json], (await _grid(firm))["grid"])
    drift: list[tuple[object, str, str, str]] = []
    matrix_rows = [r for r in rows if r["source"] == "matrix"]
    assert matrix_rows  # the grid carries computed rows, not only declared policy
    for row in matrix_rows:
        for template, cell in cast(dict[str, str], row["cells"]).items():
            for action in cast(list[str], row["actions"]):
                decisions = RULES[action].decisions
                held = {decisions.get(r, "deny") for r in _roles(template)} - {"deny"}
                if cell == "allow" and not held:
                    drift.append((row["key"], template, action, cell))
                if cell in ("deny", "delegated") and "allow" in held:
                    drift.append((row["key"], template, action, cell))
    assert drift == []


async def test_ac5_3_the_agent_row_is_locked_and_the_agent_is_denied_every_never_action(
    firm: Firm,
) -> None:
    grid = await _grid(firm)
    rows = {cast(str, r["key"]): r for r in cast(list[Json], grid["grid"])}
    locked = [r for r in cast(list[Json], grid["grid"]) if r["locked"]]
    assert len(locked) == 1  # one locked row: the Accrued Agent's, no cell of it grants
    assert not set(cast(dict[str, str], locked[0]["cells"]).values()) & {
        "allow",
        "conditional",
        "delegated",
    }
    never: list[str] = []
    for row in cast(list[Json], grid["grid"]):
        if row.get("label") in AGENT_NEVER_LABELS or row["key"] in {
            "approve_source_document",
            "adopt_agent_work",
            "reviewer_sign_off",
            "partner_sign_off",
            "materiality_risk_opinion",
            "final_return_approval",
            "export_to_tax_engine",
            "approve_aje",
            "post_to_gl",
            "release_audit_report",
            "reveal_tin",
        }:
            never.extend(cast(list[str], row["actions"]))
    assert {"evidence.accept", "sign_off.partner", "report.release", "tin.reveal"} <= set(never)
    agent = _agent(firm, tuple(never))
    for action in never:
        assert RULES[action].decisions.get("agent", "deny") == "deny", action
        with pytest.raises(Forbidden):
            await authorise(agent, action, Resource.firm(firm.tenant_id))
    assert rows  # the grid answered
    # No API sets a grid cell: the role-templates resource is read-only.
    for method in ("PUT", "PATCH", "POST"):
        write = await firm.net.call(
            method, "/v1/firm/role-templates", firm.grace, body={"cells": {"agent": "allow"}}
        )
        assert write.status_code in (404, 405), (method, write.text)
