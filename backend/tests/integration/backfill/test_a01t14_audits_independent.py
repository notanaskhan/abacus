# ac-test-author: ayushkbhatia
"""A-01-T14: independent tests (ADR-078) of A-01-T05, T08, T09 and T10 (SPEC-330 AC-9 to AC-14,
AC-18 to AC-27): INV-1 phase refusals, INV-3 walls with no counts, metadata-only tags, tile
footing, and the PBC and archive-clock rules.

Boundary: `create_app()` over HTTP (`/v1/audits*`, `/v1/binders/{id}/requests`) as the firm's
people, a client admin and another firm, with `audits.cockpit` and `binders.engine` on; the
`assurance.api` slots (`register_index_tag`, `register_audit_section`) where the spec promises a
later epic can extend the cockpit without editing A-01; seed rows as the superuser. Expectations
come from SPEC-330 §5, `docs/contracts/audits-cockpit.md`, the matrix (`assurance.yaml`,
`engagements.yaml`, `requests.yaml`), `error-codes.yaml` and the later decisions that sharpen the
outline spec: DEC-262 (Completion is not offered, so In review is followed by Ready to release;
G6 to G9 are computed, so Ready to release onwards follow their gates), DEC-263 (report-due
tones; archived rows group under Released), DEC-311 (the index base, segments over the base
without the segment, the release date as the business date the phase became Released until
A-01-T23), DEC-312 (the cockpit's action is `engagement.read_metadata`; bands, dock and actions
need `engagement.read`) and DEC-313 (owed by, latest upload, match confidence, Linked (n), PBC
counts). The clock is `kernel.clock` (a non-synthetic firm reads the system's date).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final, cast

import httpx
import pytest
from asyncpg.exceptions import PostgresError

from abacus.kernel import clock
from abacus.kernel._statuses import AuditSectionStatus
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.assurance import api as assurance_api
from abacus.modules.assurance.api import IndexTag, SectionState
from abacus.modules.identity.api import Forbidden, agent_context_for_run

from .support import Net, Person, Seeder

assert assurance_api.ROUTERS  # A-01's own segments, Overview rows and tags are registered

ZONE: Final = clock.FIRM_ZONE
PHASES: Final = (
    "planning",
    "fieldwork",
    "in_review",
    "completion",
    "ready_to_release",
    "released",
    "archiving",
    "archived",
)
TILES: Final = ("planning", "fieldwork", "in_review", "ready_to_release", "released")


@pytest.fixture(autouse=True)
def flags() -> Iterator[None]:
    forget_flags()
    yield
    forget_flags()


# --- Seeding ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Audit:
    engagement_id: uuid.UUID
    client_id: uuid.UUID
    work_item_id: uuid.UUID
    name: str


@dataclass
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    partner: Person
    manager: Person
    staff: Person
    reviewer: Person
    label: str

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    async def audit(
        self,
        name: str,
        *,
        kind: str = "fs_audit",
        phase: str = "planning",
        due_on: date | None = None,
        team: Sequence[tuple[Person, str]] = (),
    ) -> Audit:
        """An active attest engagement whose assurance work item stands at `phase`."""
        full = f"{name} {self.label}"
        client_id = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
                self.tenant_id,
                full,
            ),
        )
        entity_id = await self.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            self.tenant_id,
            client_id,
            full,
        )
        engagement_id = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, type, "
                "status, fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, "
                "$4, $5, 'active', '2025-01-01', '2025-12-31', $6) RETURNING id",
                self.tenant_id,
                client_id,
                entity_id,
                full,
                kind,
                self.partner.user_id,
            ),
        )
        await self.seed.open_engagement(self.tenant_id, engagement_id)
        work_item_id = cast(
            uuid.UUID,
            await self.seed.value(
                "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
                engagement_id,
            ),
        )
        if due_on is not None:
            await self.seed.run(
                "UPDATE work_items SET due_on = $2 WHERE id = $1", work_item_id, due_on
            )
        for who, role in ((self.partner, "engagement_partner"), *team):
            await self.join(engagement_id, who, role)
        made = Audit(engagement_id, client_id, work_item_id, full)
        if phase != "planning":
            await self.at_phase(made, phase)
        return made

    async def join(self, engagement_id: uuid.UUID, who: Person, role: str) -> None:
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant_id,
            engagement_id,
            who.user_id,
            role,
        )
        await self.seed.run(
            "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
            "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
            "clock_timestamp()) ON CONFLICT DO NOTHING",
            self.tenant_id,
            engagement_id,
            who.user_id,
        )

    async def at_phase(self, audit: Audit, phase: str, changed_on: date | None = None) -> None:
        """Seed the projection where earlier moves would have left it (the superuser)."""
        at = datetime.combine(changed_on or date.today(), time(12, 0), ZONE)
        await self.seed.run(
            "UPDATE assurance_work_items SET phase = $2, phase_changed_at = $3 "
            "WHERE work_item_id = $1",
            audit.work_item_id,
            phase,
            at,
        )

    async def call(
        self, method: str, path: str, who: Person, body: Mapping[str, object] | None = None
    ) -> httpx.Response:
        return await self.net.call(method, path, who, body=body)

    async def index(self, who: Person, **query: str) -> httpx.Response:
        return await self.net.http.get("/v1/audits", params=query, headers=self.net.headers(who))

    async def page(self, who: Person, **query: str) -> dict[str, object]:
        response = await self.index(who, **query)
        assert response.status_code == 200, response.text
        return cast(dict[str, object], response.json())

    async def record(
        self, who: Person, audit: Audit, to: str, key: str | None = None
    ) -> httpx.Response:
        return await self.net.http.post(
            f"/v1/audits/{audit.work_item_id}/phase",
            json={"to": to},
            headers={**self.net.headers(who), "Idempotency-Key": key or uuid.uuid4().hex},
        )

    async def phase(self, audit: Audit) -> str:
        return str(
            await self.seed.value(
                "SELECT phase FROM assurance_work_items WHERE work_item_id = $1",
                audit.work_item_id,
            )
        )

    async def binder(
        self, audit: Audit, *, status: str = "published"
    ) -> tuple[uuid.UUID, list[uuid.UUID]]:
        """A PBC binder on the audit's work item with two categories, in that order."""
        binder = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO request_lists (tenant_id, engagement_id, work_item_id, created_at, "
                "kind, status, published_at, published_by) VALUES ($1, $2, $3, "
                "clock_timestamp(), 'pbc', $4, CASE WHEN $4 = 'draft' THEN NULL ELSE "
                "clock_timestamp() END, CASE WHEN $4 = 'draft' THEN NULL ELSE $5::uuid END) "
                "RETURNING id",
                self.tenant_id,
                audit.engagement_id,
                audit.work_item_id,
                status,
                self.partner.user_id,
            ),
        )
        categories = [
            cast(
                uuid.UUID,
                await self.seed.value(
                    "INSERT INTO request_categories (tenant_id, request_list_id, name, "
                    "position, family) VALUES ($1, $2, $3, $4, 'audit_area') RETURNING id",
                    self.tenant_id,
                    binder,
                    name,
                    position,
                ),
            )
            for position, name in enumerate(("Plan documents", "Cash"))
        ]
        return binder, categories

    async def request(
        self,
        audit: Audit,
        binder: uuid.UUID,
        category: uuid.UUID,
        title: str,
        status: str,
        *,
        visible: bool | None = None,
        assignee: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """A draft is a request the client cannot see yet (0071: a hidden request is Draft)."""
        if visible is None:
            visible = status != "draft"
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, title, audit_area, category_id, status, created_by, "
                "client_visible, client_assignee_user_id, due_on, requested_at, na_reason, "
                "na_by, na_at) VALUES ($1, $2, $3, $4, $4, 'Area', $5, $6, $7, $8, $9, "
                "'2026-09-18', CASE WHEN $6 <> 'draft' THEN clock_timestamp() END, "
                "CASE WHEN $6 = 'not_applicable' THEN "
                "'firm_waived' END, CASE WHEN $6 = 'not_applicable' THEN $7::uuid END, "
                "CASE WHEN $6 = 'not_applicable' THEN clock_timestamp() END) RETURNING id",
                self.tenant_id,
                audit.engagement_id,
                binder,
                title,
                category,
                status,
                self.partner.user_id,
                visible,
                assignee,
            ),
        )

    async def wall(self, who: Person, audit: Audit) -> None:
        response = await self.call(
            "POST",
            "/v1/walls",
            self.admin,
            {"user_id": str(who.user_id), "client_id": str(audit.client_id)},
        )
        assert response.status_code == 201, response.text

    async def actions(self) -> list[str]:
        return await self.seed.actions(self.tenant_id)


async def _named(
    seed: Seeder, tenant: uuid.UUID, name: str, firm_role: str | None = None
) -> Person:
    who = await seed.person(tenant, firm_role)
    await seed.run("UPDATE users SET display_name = $2 WHERE id = $1", who.user_id, name)
    return who


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant = await seed.firm()
    for flag in ("audits.cockpit", "binders.engine"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'A-01-T14')",
            tenant,
            flag,
        )
    return Firm(
        net,
        tenant,
        await _named(seed, tenant, "Grace Holloway", "firm_admin"),
        await _named(seed, tenant, "Margaret Okonkwo"),
        await _named(seed, tenant, "Hannah Leclerc"),
        await _named(seed, tenant, "Ana Cruz"),
        await _named(seed, tenant, "Tomas Weller"),
        uuid.uuid4().hex[:6],
    )


def _codes(response: httpx.Response) -> str:
    return str(response.json().get("code") or response.json().get("detail"))


# --- A-01-T05: record-mode phases (AC-9 to AC-14) ----------------------------------------------


async def test_ac9_a_person_records_only_the_next_phase(firm: Firm) -> None:
    audit = await firm.audit("Sterling Freight", team=[(firm.manager, "manager")])
    moved = await firm.record(firm.manager, audit, "fieldwork")
    assert moved.status_code == 201, moved.text
    body = moved.json()
    assert (body["from_phase"], body["to_phase"], body["mode"]) == (
        "planning",
        "fieldwork",
        "recorded",
    )
    for again in ("fieldwork", "planning"):  # the current phase, and a backward move
        refused = await firm.record(firm.manager, audit, again)
        assert refused.status_code == 409 and _codes(refused) == "phase_backward", refused.text
    skipped = await firm.record(firm.manager, audit, "released")
    assert skipped.status_code == 409 and _codes(skipped) == "phase_skip", skipped.text
    assert await firm.phase(audit) == "fieldwork"
    assert (await firm.record(firm.partner, audit, "in_review")).status_code == 201


async def test_ac10_a_phase_whose_gate_is_computed_cannot_be_recorded(firm: Firm) -> None:
    """DEC-262: SPEC-314 computes G6 and G7, so Ready to release follows its gates."""
    audit = await firm.audit("Cobalt Ridge", phase="in_review")
    refused = await firm.record(firm.partner, audit, "ready_to_release")
    assert refused.status_code == 409 and _codes(refused) == "phase_follows_gate", refused.text
    assert await firm.phase(audit) == "in_review"


async def test_ac11_staff_reviewer_client_and_the_firm_admin_may_not_record(firm: Firm) -> None:
    audit = await firm.audit(
        "Halden Health", team=[(firm.staff, "staff"), (firm.reviewer, "reviewer")]
    )
    client = await firm.seed.person(firm.tenant_id)
    await firm.seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        client.user_id,
    )
    await firm.seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'owner', 'engagement', $3)",
        firm.tenant_id,
        client.user_id,
        audit.engagement_id,
    )
    for who in (firm.staff, firm.reviewer, firm.admin, client):
        refused = await firm.record(who, audit, "fieldwork")
        assert refused.status_code == 403, (who, refused.text)
    assert await firm.phase(audit) == "planning"
    assert not await firm.seed.value(
        "SELECT count(*) FROM assurance_phase_events WHERE work_item_id = $1", audit.work_item_id
    )


async def test_ac11_an_agent_context_is_refused_by_the_service(firm: Firm) -> None:
    audit = await firm.audit("Pinewood Labs")
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="engagement.agent",
        engagement_id=audit.engagement_id,
        task_scope=frozenset({"assurance.record_phase", "engagement.read"}),
        initiator_user_id=firm.partner.user_id,
    )
    with pytest.raises(Forbidden):
        await assurance_api.record_phase(agent, audit.work_item_id, "fieldwork")  # type: ignore[arg-type]  # an agent where a person goes: refused (INV-1)
    assert await firm.phase(audit) == "planning"


@pytest.mark.parametrize("actor", [("agent", None), ("system", None), ("human", None)])
async def test_ac11_the_table_refuses_a_recorded_row_without_its_human(
    firm: Firm, actor: tuple[str, None]
) -> None:
    """A recorded row needs a human actor with a user (and an agent row is refused at all)."""
    audit = await firm.audit("Juniper Row")
    with pytest.raises(PostgresError):
        await firm.seed.run(
            "INSERT INTO assurance_phase_events (tenant_id, engagement_id, work_item_id, "
            "from_phase, to_phase, mode, actor_kind, actor_user_id) VALUES ($1, $2, $3, "
            "'planning', 'fieldwork', 'recorded', $4, NULL)",
            firm.tenant_id,
            audit.engagement_id,
            audit.work_item_id,
            actor[0],
        )
    assert await firm.phase(audit) == "planning"


async def test_ac12_one_recorded_move_writes_its_event_projection_audit_and_outbox(
    firm: Firm,
) -> None:
    audit = await firm.audit("Meridian Trust")
    version_before = await firm.seed.value(
        "SELECT version FROM assurance_work_items WHERE work_item_id = $1", audit.work_item_id
    )
    moved = await firm.record(firm.partner, audit, "fieldwork")
    assert moved.status_code == 201, moved.text
    [event] = await firm.seed.rows(
        "SELECT id, mode, actor_kind, actor_user_id, from_phase, to_phase "
        "FROM assurance_phase_events WHERE work_item_id = $1",
        audit.work_item_id,
    )
    assert str(event["id"]) == moved.json()["event_id"]
    assert (event["mode"], event["actor_kind"], event["actor_user_id"]) == (
        "recorded",
        "human",
        firm.partner.user_id,
    )
    [row] = await firm.seed.rows(
        "SELECT phase, phase_source, phase_changed_at, version FROM assurance_work_items "
        "WHERE work_item_id = $1",
        audit.work_item_id,
    )
    assert (row["phase"], row["phase_source"]) == ("fieldwork", "recorded")
    assert row["phase_changed_at"] is not None
    assert int(row["version"]) == int(cast(int, version_before)) + 1
    assert moved.json()["version"] == int(row["version"])
    assert (await firm.actions()).count("assurance.phase_recorded") == 1
    emitted = await firm.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = "
        "'assurance.phase_changed'",
        firm.tenant_id,
    )
    assert emitted == 1


async def test_ac12_the_phase_event_is_insert_only(firm: Firm) -> None:
    audit = await firm.audit("Bayside Event")
    assert (await firm.record(firm.partner, audit, "fieldwork")).status_code == 201
    for statement in (
        "UPDATE assurance_phase_events SET to_phase = 'in_review' WHERE work_item_id = $1",
        "DELETE FROM assurance_phase_events WHERE work_item_id = $1",
    ):
        with pytest.raises(PostgresError):
            await firm.seed.run(statement, audit.work_item_id)


async def test_ac3_a_retried_phase_record_with_the_same_key_moves_once(firm: Firm) -> None:
    audit = await firm.audit("Keystone Retry")
    key = uuid.uuid4().hex
    first = await firm.record(firm.partner, audit, "fieldwork", key)
    second = await firm.record(firm.partner, audit, "fieldwork", key)
    assert first.status_code == 201, first.text
    assert second.status_code == 201 and second.json() == first.json()
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM assurance_phase_events WHERE work_item_id = $1",
            audit.work_item_id,
        )
        == 1
    )


async def test_inv3_a_walled_partner_and_another_firm_get_404_on_a_record(
    firm: Firm, net: Net
) -> None:
    audit = await firm.audit("Granite Peak", team=[(firm.manager, "manager")])
    await firm.wall(firm.manager, audit)
    assert (await firm.record(firm.manager, audit, "fieldwork")).status_code == 404
    other = await net.seed.firm()
    stranger = await net.seed.person(other)
    assert (await firm.record(stranger, audit, "fieldwork")).status_code == 404
    assert await firm.phase(audit) == "planning"


async def test_ac4_with_the_flag_off_the_audits_routes_answer_404(firm: Firm) -> None:
    audit = await firm.audit("Flagless")
    await firm.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'audits.cockpit'",
        firm.tenant_id,
    )
    forget_flags()
    assert (await firm.index(firm.partner)).status_code == 404
    assert (await firm.record(firm.partner, audit, "fieldwork")).status_code == 404
    path = f"/v1/audits/{audit.work_item_id}/cockpit"
    assert (await firm.call("GET", path, firm.partner)).status_code == 404


async def test_ac14_the_ebp_profile_takes_its_kinds_a_version_and_an_audit(firm: Firm) -> None:
    audit = await firm.audit(
        "Northwind Robotics 401(k) Plan", kind="ebp_audit", team=[(firm.staff, "staff")]
    )
    path = f"/v1/audits/{audit.work_item_id}/profile"
    cockpit = await firm.call("GET", f"/v1/audits/{audit.work_item_id}/cockpit", firm.partner)
    assert cockpit.status_code == 200, cockpit.text
    seen = int(cockpit.json()["version"])
    changed = await firm.call(
        "PATCH",
        path,
        firm.partner,
        {"ebp_plan_kind": "dc", "limited_scope_103a3c": True, "seen_version": seen},
    )
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert (body["ebp_plan_kind"], body["limited_scope_103a3c"]) == ("dc", True)
    assert body["version"] > seen
    stale = await firm.call(
        "PATCH", path, firm.partner, {"ebp_plan_kind": "403b", "seen_version": seen}
    )
    assert stale.status_code == 409 and _codes(stale) == "stale_version", stale.text
    for kind in ("health_welfare", "hw"):  # no health and welfare plan (DEC-262)
        refused = await firm.call(
            "PATCH", path, firm.partner, {"ebp_plan_kind": kind, "seen_version": body["version"]}
        )
        assert refused.status_code == 422, refused.text
    nulled = await firm.call(
        "PATCH",
        path,
        firm.partner,
        {"limited_scope_103a3c": None, "seen_version": body["version"]},
    )
    assert nulled.status_code == 422, nulled.text
    staff = await firm.call(
        "PATCH", path, firm.staff, {"ebp_plan_kind": "db", "seen_version": body["version"]}
    )
    assert staff.status_code == 403, staff.text
    assert (await firm.actions()).count("assurance.profile_updated") == 1


# --- A-01-T08: the AUD-01 index (AC-18 to AC-21) -----------------------------------------------


def _counts(page: Mapping[str, object]) -> dict[str, int]:
    return {k: int(v) for k, v in cast(dict[str, int], page["counts"]).items()}


def _segments(page: Mapping[str, object]) -> dict[str, int]:
    facets = cast(dict[str, object], page["facets"])
    raw = cast(list[dict[str, str | int]], facets["segment"])  # P-36 facets: value, label, n
    return {str(f["value"]): int(f["n"]) for f in raw}


def _names(page: Mapping[str, object]) -> list[str]:
    return [str(r["name"]) for r in cast(list[dict[str, object]], page["items"])]


async def _portfolio(firm: Firm) -> dict[str, Audit]:
    """2 Planning, 1 Fieldwork, 1 In review, 1 Ready to release, 1 Released; FS 2, EBP 2,
    review 1, compilation 1."""
    made: dict[str, Audit] = {}
    for name, kind, phase in (
        ("Alder FS", "fs_audit", "planning"),
        ("Birch EBP", "ebp_audit", "planning"),
        ("Cedar EBP", "ebp_audit", "fieldwork"),
        ("Dogwood FS", "fs_audit", "in_review"),
        ("Elm Review", "review", "ready_to_release"),
        ("Fir Compilation", "compilation", "released"),
    ):
        made[name] = await firm.audit(name, kind=kind, phase=phase)
    return made


async def test_ac18_the_tiles_foot_to_the_total_and_a_pressed_tile_keeps_every_count(
    firm: Firm,
) -> None:
    await _portfolio(firm)
    page = await firm.page(firm.admin)
    counts = _counts(page)
    assert sum(counts.get(t, 0) for t in TILES) == page["total"] == 6
    assert {t: counts.get(t, 0) for t in TILES} == {
        "planning": 2,
        "fieldwork": 1,
        "in_review": 1,
        "ready_to_release": 1,
        "released": 1,
    }
    pressed = await firm.page(firm.admin, phase="planning")
    assert pressed["total"] == 2
    assert sorted(_names(pressed)) == sorted(
        f"{n} {firm.label}" for n in ("Alder FS", "Birch EBP")
    )
    assert {t: _counts(pressed).get(t, 0) for t in TILES} == {t: counts.get(t, 0) for t in TILES}


async def test_ac18_segments_count_the_base_without_the_segment_and_the_caption_counts_families(
    firm: Firm,
) -> None:
    await _portfolio(firm)
    page = await firm.page(firm.admin)
    segments = _segments(page)
    assert (segments.get("fs"), segments.get("ebp"), segments.get("review")) == (2, 2, 2)
    assert "soc" not in segments and "ia" not in segments  # no entitlement, no segment
    summary = cast(dict[str, object], page["summary"])
    assert (
        summary["ebp"],
        summary["fs_audit"],
        summary["review"],
        summary["compilation_preparation"],
    ) == (2, 2, 1, 1)
    narrowed = await firm.page(firm.admin, segment="ebp")
    assert narrowed["total"] == 2
    assert _segments(narrowed) == segments  # the segment pressed keeps every segment's count


async def test_ac19_a_walled_audit_is_absent_everywhere_and_nothing_counts_it(
    firm: Firm, net: Net
) -> None:
    team = [(firm.staff, "staff")]
    seen = [
        await firm.audit("Open One", phase="planning", team=team),
        await firm.audit("Open Two", kind="ebp_audit", phase="fieldwork", team=team),
    ]
    walled = await firm.audit("Granite Peak", kind="review", phase="planning", team=team)
    before = await firm.page(firm.staff)
    assert before["total"] == 3
    await firm.wall(firm.staff, walled)
    response = await firm.index(firm.staff)
    assert response.status_code == 200, response.text
    page = response.json()
    assert walled.name not in response.text
    assert str(walled.work_item_id) not in response.text
    assert page["total"] == 2
    assert sum(_counts(page).get(t, 0) for t in TILES) == 2
    assert _counts(page).get("planning", 0) == 1
    assert sum(_segments(page).values()) == 2 and _segments(page).get("review", 0) == 0
    summary = cast(dict[str, object], page["summary"])
    assert summary["review"] == 0
    assert sorted(_names(page)) == sorted(a.name for a in seen)
    assert "hidden" not in json.dumps(page).lower()  # no hidden-count field anywhere
    cockpit = await firm.call("GET", f"/v1/audits/{walled.work_item_id}/cockpit", firm.staff)
    assert cockpit.status_code == 404
    assert walled.name not in cockpit.text


async def test_ac19_the_keyset_cursor_walks_every_row_once(firm: Firm) -> None:
    made = await _portfolio(firm)
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(10):
        query = {"limit": "2"} | ({"cursor": cursor} if cursor else {})
        page = await firm.page(firm.admin, **query)
        seen.extend(str(r["work_item_id"]) for r in cast(list[dict[str, object]], page["items"]))
        cursor = cast(str | None, page["next_cursor"])
        if not cursor:
            break
    assert sorted(seen) == sorted(str(a.work_item_id) for a in made.values())


async def test_ac20_pbc_counts_asked_client_visible_requests_of_a_published_binder(
    firm: Firm,
) -> None:
    published = await firm.audit("Pbc Published")
    unpublished = await firm.audit("Pbc Draft")
    none = await firm.audit("Pbc None")
    binder, (plan, cash) = await firm.binder(published)
    await firm.request(published, binder, plan, "Plan document", "received")
    await firm.request(published, binder, plan, "Trust report", "uploaded")
    await firm.request(published, binder, cash, "Bank statements", "requested")
    await firm.request(published, binder, cash, "Draft ask", "draft")
    await firm.request(published, binder, cash, "Not needed", "not_applicable")
    await firm.request(published, binder, cash, "Firm-only ask", "requested", visible=False)
    # (hidden from the client, so it is a Draft too: neither counts)
    draft, (draft_cat, _) = await firm.binder(unpublished, status="draft")
    await firm.request(unpublished, draft, draft_cat, "Waiting", "draft")
    rows = {
        r["name"]: r
        for r in cast(list[dict[str, object]], (await firm.page(firm.partner))["items"])
    }
    assert rows[published.name]["pbc"] == {"received": 1, "total": 3}
    assert rows[unpublished.name]["pbc"] is None  # no published binder (before G3: "—")
    assert rows[none.name]["pbc"] is None


async def test_ac20_report_due_tones_read_kernel_clock(firm: Firm) -> None:
    today = await clock.today(TenantContext(firm.tenant_id, "system", "test"))
    cases = {
        "Due Past": (today - timedelta(days=3), "past_due"),
        "Due Soon": (today + timedelta(days=3), "within_7_days"),
        "Due Seven": (today + timedelta(days=7), "within_30_days"),  # DEC-263: 7 left is amber
        "Due Month": (today + timedelta(days=20), "within_30_days"),
        "Due Later": (today + timedelta(days=60), "later"),
    }
    for name, (due_on, _) in cases.items():
        await firm.audit(name, due_on=due_on)
    rows = {
        r["name"]: r
        for r in cast(list[dict[str, object]], (await firm.page(firm.partner))["items"])
    }
    for name, (due_on, tone) in cases.items():
        row = rows[f"{name} {firm.label}"]
        assert row["report_due_on"] == due_on.isoformat()
        assert row["report_due_tone"] == tone, (name, row["report_due_tone"])


async def test_ac20_a_released_audit_counts_60_days_to_archive_and_archived_groups_released(
    firm: Firm,
) -> None:
    today = await clock.today(TenantContext(firm.tenant_id, "system", "test"))
    released = await firm.audit("Bayside", kind="ebp_audit")
    await firm.at_phase(released, "released", today - timedelta(days=47))
    archived = await firm.audit("Meridian", kind="ebp_audit")
    await firm.at_phase(archived, "released", today - timedelta(days=200))
    await firm.seed.run(
        "UPDATE work_items SET status = 'archived', archived_at = now() WHERE id = $1",
        archived.work_item_id,
    )
    page = await firm.page(firm.partner)
    rows = {r["name"]: r for r in cast(list[dict[str, object]], page["items"])}
    bayside = rows[released.name]
    assert bayside["phase"] == "released"
    assert bayside["released_on"] == (today - timedelta(days=47)).isoformat()
    archive = cast(dict[str, object], bayside["archive"])
    assert (archive["state"], archive["days_left"]) == ("archiving", 13)
    meridian = rows[archived.name]
    assert meridian["phase"] == "released"  # archived rows group under Released (DEC-263)
    assert cast(dict[str, object], meridian["archive"])["state"] == "archived"
    assert _counts(page).get("released", 0) == 2


async def test_ac21_a_metadata_only_reader_sees_metadata_tags_and_never_a_content_tag(
    firm: Firm,
) -> None:
    audit = await firm.audit("Tagged Plan", phase="in_review", team=[(firm.reviewer, "reviewer")])
    content_text = f"Materiality decision pending {firm.label}"
    mine = {audit.work_item_id}

    async def content_tags(
        tenant: TenantContext, ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, Sequence[IndexTag]]:
        return {i: [IndexTag("a01t14_content", content_text)] for i in ids if i in mine}

    assurance_api.register_index_tag(f"a01t14_content_{firm.label}", content_tags, "content")
    admin = await firm.index(firm.admin)
    assert admin.status_code == 200, admin.text
    [row] = [r for r in admin.json()["items"] if r["work_item_id"] == str(audit.work_item_id)]
    tags = cast(list[dict[str, object]], row["tags"])
    assert all(t["classification"] == "metadata" for t in tags)
    assert content_text not in admin.text
    eqr = [t for t in tags if t["code"] == "eqr"]
    assert eqr and "TW" in str(eqr[0]["text"])  # "EQR · TW" from In review (DEC-312)
    partner = await firm.index(firm.partner)
    assert content_text in partner.text  # a content reader gets the content tag


async def test_ac21_a_client_principal_is_refused_the_index(firm: Firm) -> None:
    audit = await firm.audit("Client Peek")
    client = await firm.seed.person(firm.tenant_id)
    await firm.seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        client.user_id,
    )
    await firm.seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'owner', 'engagement', $3)",
        firm.tenant_id,
        client.user_id,
        audit.engagement_id,
    )
    for path in ("/v1/audits", f"/v1/audits/{audit.work_item_id}/cockpit"):
        response = await firm.call("GET", path, client)
        assert response.status_code == 403, (path, response.text)
        assert audit.name not in response.text


# --- A-01-T09: the cockpit (AC-22 to AC-24) ----------------------------------------------------


def _rows(cockpit: Mapping[str, object]) -> dict[str, dict[str, object]]:
    found: dict[str, dict[str, object]] = {}
    for band in cast(list[dict[str, object]], cockpit.get("bands") or []):
        for row in cast(list[dict[str, object]], band["rows"]):
            found[str(row["key"])] = row | {"band": band["key"]}
    return found


async def test_ac22_a_later_epic_registers_a_row_and_unanswered_rows_never_render(
    firm: Firm,
) -> None:
    audit = await firm.audit("Rail Plan")
    mine = audit.work_item_id

    async def shown(tenant: TenantContext, work_item_id: uuid.UUID) -> SectionState | None:
        return (
            SectionState(AuditSectionStatus.NOT_STARTED, "sub_line")
            if work_item_id == mine
            else None
        )

    async def silent(tenant: TenantContext, work_item_id: uuid.UUID) -> SectionState | None:
        return None

    async def broken(tenant: TenantContext, work_item_id: uuid.UUID) -> SectionState | None:
        raise RuntimeError("provider down")

    tag = firm.label
    assurance_api.register_audit_section(
        f"tb_{tag}", "planning", 900, "AUD-06", shown, title="Trial Balance", link="live"
    )
    assurance_api.register_audit_section(f"silent_{tag}", "planning", 901, "AUD-06", silent)
    assurance_api.register_audit_section(f"broken_{tag}", "planning", 902, "AUD-06", broken)
    with pytest.raises(ValueError):
        assurance_api.register_audit_section(f"none_{tag}", "planning", 903, "AUD-06", None)
    response = await firm.call("GET", f"/v1/audits/{audit.work_item_id}/cockpit", firm.partner)
    assert response.status_code == 200, response.text
    rows = _rows(response.json())
    assert rows[f"tb_{tag}"]["title"] == "Trial Balance"
    assert rows[f"tb_{tag}"]["band"] == "planning"
    for absent in (f"silent_{tag}", f"broken_{tag}", f"none_{tag}"):
        assert absent not in rows


async def test_ac23_a01s_overview_rows_read_source_documents_and_the_team_in_role_order(
    firm: Firm,
) -> None:
    senior = await _named(firm.seed, firm.tenant_id, "Marcus Delaney")
    audit = await firm.audit(
        "Overview Plan",
        team=[
            (firm.staff, "staff"),
            (senior, "senior"),
            (firm.manager, "manager"),
            (firm.reviewer, "reviewer"),
        ],
    )
    binder, (plan, cash) = await firm.binder(audit)
    await firm.request(audit, binder, plan, "Plan document", "received")
    await firm.request(audit, binder, cash, "Bank statements", "requested")
    response = await firm.call("GET", f"/v1/audits/{audit.work_item_id}/cockpit", firm.partner)
    assert response.status_code == 200, response.text
    body = response.json()
    rows = _rows(body)
    assert {"client", "source_documents", "team", "activity"} <= set(rows)
    assert "methodology" not in rows  # nothing pinned
    assert "standards_set" not in rows  # no named standards set
    assert rows["source_documents"]["sub_line"] == "1 of 2 received"
    assert rows["team"]["sub_line"] == "MO · TW · HL · MD · AC"  # partner, reviewer, manager...
    assert body["audit_bar"]["run_started_at"] is None  # no C6 run provider registered
    assert body["overview"]["phase"] == "planning"


async def test_ac24_a_metadata_only_reader_gets_the_bar_and_overview_only(firm: Firm) -> None:
    audit = await firm.audit("Metadata Plan", team=[(firm.manager, "manager")])
    admin = await firm.call("GET", f"/v1/audits/{audit.work_item_id}/cockpit", firm.admin)
    assert admin.status_code == 200, admin.text
    body = admin.json()
    assert body["audit_bar"] and body["overview"]["name"] == audit.name
    assert not body["bands"] and not body["dock_tabs"] and not body["allowed_actions"]
    manager = await firm.call("GET", f"/v1/audits/{audit.work_item_id}/cockpit", firm.manager)
    assert (
        manager.json()["bands"] and "assurance.record_phase" in manager.json()["allowed_actions"]
    )


async def test_ac24_an_archived_work_item_is_read_only(firm: Firm) -> None:
    audit = await firm.audit("Archived Plan", phase="released", team=[(firm.manager, "manager")])
    await firm.seed.run(
        "UPDATE work_items SET status = 'archived', archived_at = now() WHERE id = $1",
        audit.work_item_id,
    )
    response = await firm.call("GET", f"/v1/audits/{audit.work_item_id}/cockpit", firm.partner)
    assert response.status_code == 200, response.text
    assert response.json()["read_only_reason"] == "archived"
    assert response.json()["allowed_actions"] == []


# --- A-01-T10: C5 v1.1 request facts and Source Documents (AC-25 to AC-27) -----------------------


@dataclass(frozen=True)
class Pbc:
    audit: Audit
    binder: uuid.UUID
    dana: Person
    requested: uuid.UUID
    uploaded: uuid.UUID
    received: uuid.UUID
    delegated: uuid.UUID
    version: uuid.UUID


async def _pbc(firm: Firm) -> Pbc:
    audit = await firm.audit("Northwind Plan", kind="ebp_audit", team=[(firm.staff, "staff")])
    dana = await _named(firm.seed, firm.tenant_id, "Dana Kowalski")
    await firm.seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        dana.user_id,
    )
    await firm.seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'owner', 'engagement', $3)",
        firm.tenant_id,
        dana.user_id,
        audit.engagement_id,
    )
    binder, (plan, cash) = await firm.binder(audit)
    requested = await firm.request(
        audit, binder, plan, "IRS opinion letter", "requested", assignee=dana.user_id
    )
    uploaded = await firm.request(
        audit, binder, plan, "Certified trust report", "uploaded", assignee=dana.user_id
    )
    received = await firm.request(audit, binder, plan, "Summary plan description", "received")
    delegated = await firm.request(audit, binder, cash, "Bridge letter", "requested")
    await firm.request(audit, binder, cash, "Not needed", "not_applicable")
    await firm.request(audit, binder, cash, "Draft ask", "draft")
    contact = await firm.seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, organisation_name, "
        "contact_kind) VALUES ($1, $2, 'Sam Ortiz', 'Keystone', 'third_party') RETURNING id",
        firm.tenant_id,
        audit.client_id,
    )
    await firm.seed.run_untriggered(
        "INSERT INTO request_delegations (tenant_id, request_item_id, contact_id, grant_id, "
        "granted_by) VALUES ($1, $2, $3, $4, $5)",
        firm.tenant_id,
        delegated,
        contact,
        uuid.uuid4(),
        firm.partner.user_id,
    )
    evidence_item = await firm.seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, 'Harborline Certification PY2025.pdf', 'human', 'seed') "
        "RETURNING id",
        firm.tenant_id,
        audit.engagement_id,
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    version = cast(
        uuid.UUID,
        await firm.seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', "
            "'client_upload', 'uploaded') RETURNING id",
            firm.tenant_id,
            audit.engagement_id,
            evidence_item,
            fingerprint,
            f"tenants/{firm.tenant_id}/sha256/{fingerprint}",
        ),
    )
    await firm.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) VALUES ($1, $2, $3, $4, 'human', "
        "'seed')",
        firm.tenant_id,
        audit.engagement_id,
        uploaded,
        version,
    )
    inbox_file = await firm.seed.value(
        "INSERT INTO inbox_files (tenant_id, engagement_id, file_name, media_type, size_bytes, "
        "fingerprint, storage_key, storage_version_id, uploaded_by, uploaded_by_staff, status, "
        "assigned_item_id, assigned_version_id, decided_by, decided_at) VALUES ($1, $2, "
        "'cert.pdf', 'application/pdf', 10, $3, $4, 'v1', $5, false, 'assigned', $6, $7, $8, "
        "clock_timestamp()) RETURNING id",
        firm.tenant_id,
        audit.engagement_id,
        fingerprint,
        f"tenants/{firm.tenant_id}/sha256/{fingerprint}",
        dana.user_id,
        uploaded,
        version,
        firm.staff.user_id,
    )
    run = await firm.seed.value(
        "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
        "inbox_file_id, initiator_user_id, task_scope, status, finished_at) VALUES ($1, "
        "'evidence.matcher', 1, $2, $3, $4, ARRAY['evidence.read'], 'completed', now()) "
        "RETURNING id",
        firm.tenant_id,
        audit.engagement_id,
        inbox_file,
        firm.partner.user_id,
    )
    match = await firm.seed.value(
        "INSERT INTO inbox_match_runs (tenant_id, engagement_id, inbox_file_id, agent_run_id, "
        "prompt_ref, none_fit) VALUES ($1, $2, $3, $4, 'evidence.inbox_match@v2', false) "
        "RETURNING id",
        firm.tenant_id,
        audit.engagement_id,
        inbox_file,
        run,
    )
    await firm.seed.run(
        "INSERT INTO inbox_match_proposals (tenant_id, match_id, rank, request_item_id, "
        "confidence, rationale, citations, shown) VALUES ($1, $2, 1, $3, 0.94, 'Trust report', "
        "'[]'::jsonb, true)",
        firm.tenant_id,
        match,
        uploaded,
    )
    return Pbc(audit, binder, dana, requested, uploaded, received, delegated, version)


async def _binder_rows(firm: Firm, who: Person, binder: uuid.UUID) -> dict[str, dict[str, object]]:
    response = await firm.call("GET", f"/v1/binders/{binder}/requests", who)
    assert response.status_code == 200, response.text
    return {str(r["id"]): r for r in response.json()["items"]}


async def test_ac25_the_firm_reads_owed_by_latest_upload_match_and_linked(firm: Firm) -> None:
    pbc = await _pbc(firm)
    rows = await _binder_rows(firm, firm.partner, pbc.binder)
    asked = rows[str(pbc.requested)]
    assert asked["owed_by"] == {"kind": "client_contact", "display": "Dana Kowalski"}
    delegated = rows[str(pbc.delegated)]
    assert cast(dict[str, object], delegated["owed_by"])["kind"] == "third_party"
    assert "Sam Ortiz" in str(cast(dict[str, object], delegated["owed_by"])["display"])
    assert rows[str(pbc.received)]["owed_by"] is None  # received: owed by no one
    uploaded = rows[str(pbc.uploaded)]
    latest = cast(dict[str, object], uploaded["latest_upload"])
    assert latest["evidence_version_id"] == str(pbc.version)
    assert latest["path_label"] == "Harborline Certification PY2025.pdf"
    assert latest["uploader_kind"] == "client"
    assert uploaded["match_confidence"] == 94
    assert uploaded["linked_count"] == 1
    assert asked["latest_upload"] is None and asked["match_confidence"] is None


async def test_ac25_a_client_principals_rows_never_carry_the_firm_only_facts(firm: Firm) -> None:
    pbc = await _pbc(firm)
    response = await firm.call("GET", f"/v1/binders/{pbc.binder}/requests", pbc.dana)
    assert response.status_code == 200, response.text
    assert response.json()["items"]
    for row in response.json()["items"]:
        for hidden in ("owed_by", "latest_upload", "match_confidence"):
            assert row.get(hidden) is None, (hidden, row)
    assert "Harborline Certification" not in response.text
    assert (
        await firm.call("GET", f"/v1/audits/{pbc.audit.work_item_id}/source-documents", pbc.dana)
    ).status_code == 403


async def test_ac26_source_documents_group_foot_and_order_missing_first(firm: Firm) -> None:
    pbc = await _pbc(firm)
    path = f"/v1/audits/{pbc.audit.work_item_id}/source-documents"
    response = await firm.call("GET", path, firm.partner)
    assert response.status_code == 200, response.text
    body = response.json()
    groups = cast(list[dict[str, object]], body["groups"])
    assert [g["label"] for g in groups] == ["Plan documents", "Cash"]
    assert [(g["received"], g["total"]) for g in groups] == [(1, 3), (0, 1)]  # N excludes N/A
    assert (body["received"], body["total"]) == (1, 4)
    assert body["total"] == sum(int(cast(int, g["total"])) for g in groups)
    assert (body["needs_review"], body["requested"]) == (1, 2)
    titles = [r["title"] for r in cast(list[dict[str, object]], groups[0]["rows"])]
    assert titles == ["Certified trust report", "IRS opinion letter", "Summary plan description"]
    assert all(
        r["status"] != "draft" for g in groups for r in cast(list[dict[str, object]], g["rows"])
    )
    narrowed = (await firm.call("GET", f"{path}?q=opinion", firm.partner)).json()
    shown = [r for g in narrowed["groups"] for r in g["rows"]]
    assert [r["title"] for r in shown] == ["IRS opinion letter"]
    assert (narrowed["received"], narrowed["total"]) == (1, 4)  # q narrows rows, never totals


def _rows_of(page: Mapping[str, object], audit: Audit) -> list[dict[str, object]]:
    items = cast(list[dict[str, object]], page["items"])
    return [r for r in items if r["work_item_id"] == str(audit.work_item_id)]


async def test_ac27_pbc_counts_follow_visibility_and_need_a_published_binder(
    firm: Firm, net: Net
) -> None:
    pbc = await _pbc(firm)
    page = await firm.page(firm.staff)
    [row] = _rows_of(page, pbc.audit)
    assert row["pbc"] == {"received": 1, "total": 4}
    await firm.seed.run(
        "UPDATE request_lists SET status = 'draft', published_at = NULL, published_by = NULL "
        "WHERE id = $1",
        pbc.binder,
    )
    page = await firm.page(firm.staff)
    [row] = _rows_of(page, pbc.audit)
    assert row["pbc"] is None
    await firm.wall(firm.staff, pbc.audit)
    walled = await firm.index(firm.staff)
    assert str(pbc.audit.work_item_id) not in walled.text
    assert (
        await firm.call("GET", f"/v1/audits/{pbc.audit.work_item_id}/source-documents", firm.staff)
    ).status_code == 404
