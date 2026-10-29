# ac-test-author: ayushkbhatia
"""P-07-T14: independent acceptance tests (ADR-078) for P-07-T15 (engagements index, record and the
interim recorded letter) and P-07-T16 (the type catalogue, wizard drafts and create).

Written from the plan and the contract, not from the code: SPEC-321 Story 4 (AC-16 to AC-19);
P-07 Stories 6.1 to 6.3; `docs/contracts/engagements-v2.md` §2 to §7; `docs/screens/ENG-01.md`;
DEC-224 and DEC-225 (the recorded readings of the G1 date rule, "Letter │ Not signed" and a
draft's G1). The row: "tiles foot to the total, Letter not signed excludes prospects, G1 blocks
Next and create, duplicate 409 with confirm, cardinality by type, single_audit 422
unknown_engagement_type with no catalogue entry, drafts own-scope, agent and system refused on
engagement.create, letter date after the G1 decision".

HTTP through `create_app()` against the migrated Postgres, with fake-identity tokens. Seeding runs
as the superuser, fresh firm per test; nothing reads a module's internals. Where the code does not
meet the plan, the test is a strict xfail naming the escaped defect (never weakened).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import cast

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
    engagement_resource,
)
from abacus.modules.identity.context import (
    _ISSUER,  # pyright: ignore[reportPrivateUsage] -- a test-only agent principal
)

from .support import Net, Person, Seeder

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
TILES = ("prospect", "accepted", "contracted", "active", "on_hold", "delivered", "archived")
# docs/contracts/engagements-v2.md §3: the 18 catalogue codes, by family.
TAX = (
    "form_1040",
    "form_1041",
    "form_1065",
    "form_1120s",
    "form_1120",
    "form_990",
    "forms_706_709",
    "notice_response",
)
AUDIT = (
    "ebp_audit",
    "fs_audit",
    "review",
    "compilation",
    "preparation",
    "agreed_upon_procedures",
    "soc1",
    "soc2",
)
CAS = ("cas_monthly_close", "advisory")
FY_START, FY_END = date(2025, 1, 1), date(2025, 12, 31)


# ================================================================================================
# Seeding
# ================================================================================================


@dataclass(frozen=True)
class Firm:
    seed: Seeder
    net: Net
    tenant: uuid.UUID
    admin: Person  # Margaret: the firm admin reads every engagement's metadata

    async def person(self, *, firm_role: str | None = None, level: str | None = None) -> Person:
        who = await self.seed.person(self.tenant, firm_role)
        if level is not None:
            await self.seed.run(
                "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
                self.tenant,
                who.user_id,
                level,
            )
        return who

    async def client(self, name: str) -> tuple[uuid.UUID, uuid.UUID]:
        client = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO clients (tenant_id, name, kind) VALUES ($1, $2, 'business') "
                "RETURNING id",
                self.tenant,
                f"{name} {uuid.uuid4().hex[:6]}",
            ),
        )
        entity = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
                "RETURNING id",
                self.tenant,
                client,
                f"{name} entity",
            ),
        )
        return client, entity

    async def engagement(
        self,
        client: tuple[uuid.UUID, uuid.UUID],
        *,
        status: str,
        type_: str = "fs_audit",
        name: str | None = None,
        end: date = FY_END,
    ) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, type, "
                "fiscal_period_start, fiscal_period_end, status, created_by) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id",
                self.tenant,
                client[0],
                client[1],
                name or f"{type_} {status} {uuid.uuid4().hex[:6]}",
                type_,
                date(end.year, 1, 1),
                end,
                status,
                self.admin.user_id,
            ),
        )

    async def accept(self, engagement: uuid.UUID, decided_at: datetime) -> None:
        """G1: the engagement's acceptance decision (SPEC-025), decided at `decided_at`."""
        await self.seed.run(
            "INSERT INTO engagement_acceptance (tenant_id, engagement_id, kind, decision, "
            "decided_by, documented_at, independence_concluded_by, independence_concluded_at, "
            "independence_documented_at, created_at) VALUES ($1, $2, 'new_client', 'accepted', "
            "'test-seed', 'Seeded', 'test-seed', $3, 'Seeded', $3)",
            self.tenant,
            engagement,
            decided_at,
        )

    async def signed_letter(self, engagement: uuid.UUID) -> None:
        await self.seed.run(
            "INSERT INTO engagement_letters (tenant_id, engagement_id, status, letter_date, "
            "recorded_by) VALUES ($1, $2, 'signed', '2025-02-01', 'test-seed')",
            self.tenant,
            engagement,
        )

    async def member(self, engagement: uuid.UUID, who: Person, role: str) -> None:
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant,
            engagement,
            who.user_id,
            role,
        )
        await self.seed.run(
            "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
            "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
            "clock_timestamp()) ON CONFLICT DO NOTHING",
            self.tenant,
            engagement,
            who.user_id,
        )

    async def entitle(self, module: str) -> None:
        await self.seed.run(
            "INSERT INTO tenant_entitlements (tenant_id, module, enabled, seats, "
            "agent_minutes_allowance, valid_from, set_by) "
            "VALUES ($1, $2, true, 12, 600, DATE '2026-01-01', 'operator:probe')",
            self.tenant,
            module,
        )

    async def signed_copy(self, engagement: uuid.UUID) -> uuid.UUID:
        """An evidence version on the engagement: the signed copy, stored write-once first."""
        item = await self.seed.value(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, 'Signed engagement letter', 'system', 'seed') "
            "RETURNING id",
            self.tenant,
            engagement,
        )
        fingerprint = uuid.uuid4().hex * 2
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
                "version_no, fingerprint, storage_key, storage_version_id, size_bytes, "
                "media_type, source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, "
                "'application/pdf', 'upload', 'uploaded') RETURNING id",
                self.tenant,
                engagement,
                item,
                fingerprint,
                f"tenants/{self.tenant}/sha256/{fingerprint}",
            ),
        )

    async def call(
        self,
        method: str,
        path: str,
        who: Person | None = None,
        *,
        body: Json | None = None,
        key: str | None = None,
    ) -> httpx.Response:
        headers = self.net.headers(who or self.admin)
        if key is not None:
            headers["Idempotency-Key"] = key
        return await self.net.http.request(method, path, json=body, headers=headers)

    async def actions(self) -> list[str]:
        return await self.seed.actions(self.tenant)


async def _firm(net: Net) -> Firm:
    tenant = await net.seed.firm()
    admin = await net.seed.person(tenant, "firm_admin")
    return Firm(net.seed, net, tenant, admin)


def _json(response: httpx.Response, status: int = 200) -> Json:
    assert response.status_code == status, response.text
    return cast(Json, response.json())


def _refusal(response: httpx.Response, status: int, detail: str) -> Json:
    assert response.status_code == status, response.text
    body = cast(Json, response.json())
    assert body["detail"] == detail, body
    return cast(Json, body.get("facts") or {})


def _ids(page: Json) -> set[str]:
    return {str(cast(Json, row)["id"]) for row in cast(list[object], page["items"])}


def _tile_sum(page: Json) -> int:
    counts = cast(dict[str, int], page["counts"])
    return sum(counts.get(t, 0) for t in TILES)


def _segment_sum(page: Json) -> int:
    facets = cast(dict[str, list[Json]], page["facets"])
    return sum(int(cast(int, f["n"])) for f in facets["service_line"])


# ================================================================================================
# ENG-01: the index (Story 6.1; AC-16)
# ================================================================================================


async def _index_firm(net: Net) -> tuple[Firm, dict[str, list[uuid.UUID]]]:
    """Engagements in every status but archived over the four service lines; every engagement
    past the letter has a signed letter, as at E0 ("no Active audit … lacks a signed letter")."""
    firm = await _firm(net)
    northwind, ridgeline, copperleaf, feld = (
        await firm.client("Northwind"),
        await firm.client("Ridgeline"),
        await firm.client("Copperleaf"),
        await firm.client("Feld"),
    )
    plan: Sequence[tuple[tuple[uuid.UUID, uuid.UUID], str, str]] = (
        (feld, "tax_compliance", "prospect"),
        (northwind, "ebp_audit", "accepted"),
        (copperleaf, "cas_monthly_close", "accepted"),
        (ridgeline, "advisory", "accepted"),
        (northwind, "fs_audit", "contracted"),
        (northwind, "review", "active"),
        (feld, "tax_compliance", "active"),
        (copperleaf, "cas_monthly_close", "active"),
        (copperleaf, "cas_monthly_close", "on_hold"),
        (feld, "tax_compliance", "delivered"),
        (northwind, "fs_audit", "declined"),
    )
    made: dict[str, list[uuid.UUID]] = {}
    for client, type_, status in plan:
        engagement = await firm.engagement(client, status=status, type_=type_)
        made.setdefault(status, []).append(engagement)
        if status not in ("prospect", "accepted", "declined"):
            await firm.signed_letter(engagement)
    return firm, made


async def test_ac16_the_seven_tiles_and_the_segments_foot_to_the_total(net: Net) -> None:
    firm, made = await _index_firm(net)
    page = _json(await firm.call("GET", "/v1/engagements/index"))
    # Declined is never a tile and never a row (contract §3, §4).
    assert cast(dict[str, int], page["counts"]).get("declined", 0) == 0
    assert not (_ids(page) & {str(e) for e in made["declined"]})
    shown = sum(len(v) for k, v in made.items() if k != "declined")
    assert page["total"] == shown
    assert _tile_sum(page) == page["total"]
    assert _segment_sum(page) == page["total"]
    counts = cast(dict[str, int], page["counts"])
    assert {t: counts.get(t, 0) for t in TILES} == {t: len(made.get(t, [])) for t in TILES}
    segments = {
        str(f["value"]): f["n"]
        for f in cast(dict[str, list[Json]], page["facets"])["service_line"]
    }
    assert {k: v for k, v in segments.items() if v} == {
        "audit": 3,
        "tax": 3,
        "cas": 3,
        "advisory": 1,
    }


async def test_ac16_the_default_view_leaves_archived_engagements_to_the_period_that_includes_them(
    net: Net,
) -> None:
    """DEC-343 (ED-027, decided 2026-10-25): "Period │ Current" is every status but archived and
    declined (DEC-224), so ENG-01 a's Archived tile is 0 and the archived engagement is neither a
    row nor in the total; "Prior" and "All" count it under Archived."""
    firm, made = await _index_firm(net)
    archived = await firm.engagement(await firm.client("Halvorsen"), status="archived")
    await firm.signed_letter(archived)
    shown = sum(len(v) for k, v in made.items() if k != "declined")

    page = _json(await firm.call("GET", "/v1/engagements/index"))
    assert cast(dict[str, int], page["counts"]).get("archived", 0) == 0
    assert str(archived) not in _ids(page)
    assert page["total"] == shown
    assert _tile_sum(page) == page["total"]
    assert _segment_sum(page) == page["total"]

    prior = _json(await firm.call("GET", "/v1/engagements/index?period=prior"))
    assert cast(dict[str, int], prior["counts"]).get("archived", 0) == 1
    assert _ids(prior) == {str(archived)}
    assert prior["total"] == 1
    assert _tile_sum(prior) == prior["total"]
    assert _segment_sum(prior) == prior["total"]

    every = _json(await firm.call("GET", "/v1/engagements/index?period=all"))
    assert cast(dict[str, int], every["counts"]).get("archived", 0) == 1
    assert str(archived) in _ids(every)


async def test_ac16_a_tile_filters_the_rows_and_the_tiles_still_count_without_it(
    net: Net,
) -> None:
    firm, made = await _index_firm(net)
    whole = _json(await firm.call("GET", "/v1/engagements/index"))
    page = _json(await firm.call("GET", "/v1/engagements/index?tile=active"))
    assert _ids(page) == {str(e) for e in made["active"]}
    assert page["total"] == len(made["active"])
    assert page["counts"] == whole["counts"]  # counts minus the selected tile
    assert _tile_sum(page) == whole["total"]


async def test_ac16_a_segment_recounts_the_tiles_to_its_own_total(net: Net) -> None:
    """ENG-01 c: Segment Advisory, one row; the tiles recount to Accepted 1, all others 0."""
    firm, _ = await _index_firm(net)
    page = _json(await firm.call("GET", "/v1/engagements/index?service_line=advisory"))
    assert page["total"] == 1
    counts = cast(dict[str, int], page["counts"])
    assert {t: counts.get(t, 0) for t in TILES} == {t: int(t == "accepted") for t in TILES}
    assert _tile_sum(page) == page["total"]


async def test_ac16_letter_not_signed_lists_accepted_engagements_and_never_the_prospect(
    net: Net,
) -> None:
    """ENG-01 b and Story 6.1: "Letter │ Not signed" with the Accepted tile shows only Accepted
    engagements without a recorded letter; the Thornbury Prospect is never a row."""
    firm, made = await _index_firm(net)
    for query in ("letter=not_signed", "letter=not_signed&tile=accepted"):
        page = _json(await firm.call("GET", f"/v1/engagements/index?{query}"))
        assert _ids(page) == {str(e) for e in made["accepted"]}, query
        assert not (_ids(page) & {str(e) for e in made["prospect"]})
        for row in cast(list[Json], page["items"]):
            assert row["status"] == "accepted"
            assert cast(Json, row["letter"])["status"] == "not_signed"
    summary = cast(Json, _json(await firm.call("GET", "/v1/engagements/index"))["summary"])
    assert summary["prospect"] == 1
    assert summary["awaiting_letter"] == len(made["accepted"])  # = the Accepted tile


async def test_ac16_a_walled_engagement_is_absent_from_rows_tiles_segments_and_totals(
    net: Net,
) -> None:
    firm, made = await _index_firm(net)
    ashford = await firm.client("Ashford")
    walled = await firm.engagement(ashford, status="active", type_="fs_audit")
    await firm.signed_letter(walled)
    lena = await firm.person(firm_role="firm_admin")
    before = _json(await firm.call("GET", "/v1/engagements/index", lena))
    assert str(walled) in _ids(before)
    wall = await firm.call(
        "POST",
        "/v1/walls",
        body={"user_id": str(lena.user_id), "client_id": str(ashford[0])},
    )
    assert wall.status_code == 201, wall.text

    after = _json(await firm.call("GET", "/v1/engagements/index", lena))
    assert str(walled) not in _ids(after)
    assert after["total"] == cast(int, before["total"]) - 1
    assert _tile_sum(after) == after["total"]
    assert _segment_sum(after) == after["total"]
    assert cast(dict[str, int], after["counts"])["active"] == len(made["active"])
    assert "hidden_by_wall" not in after  # DEC-43: no hidden count anywhere
    # Her own search for it finds nothing, and a guessed record is not found (INV-3).
    search = _json(await firm.call("GET", "/v1/engagements/index?q=Ashford", lena))
    assert search["total"] == 0
    for path in (f"/v1/engagements/{walled}/record", f"/v1/engagements/{walled}/gates"):
        _refusal(await firm.call("GET", path, lena), 404, "not found")


async def test_ac16_the_index_is_a_firm_surface_a_client_principal_is_not_found(
    net: Net,
) -> None:
    firm, made = await _index_firm(net)
    engagement = made["active"][0]
    contact = await firm.person()
    await firm.seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant,
        contact.user_id,
    )
    await firm.seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'owner', 'engagement', $3)",
        firm.tenant,
        contact.user_id,
        engagement,
    )
    for path in (
        "/v1/engagements/index",
        f"/v1/engagements/{engagement}/record",
        f"/v1/engagements/{engagement}/gates",
    ):
        assert (await firm.call("GET", path, contact)).status_code == 404, path


async def test_ac13_the_v2_routes_answer_for_a_firm_with_no_flag_row(net: Net) -> None:
    """`engagements.v2` retired with P-07-T59 (DEC-905): every route answers without a flag."""
    firm = await _firm(net)
    engagement = await firm.engagement(await firm.client("Northwind"), status="active")
    for method, path in (
        ("GET", "/v1/engagements/index"),
        ("GET", f"/v1/engagements/{engagement}/record"),
        ("GET", f"/v1/engagements/{engagement}/gates"),
        ("GET", "/v1/engagement-types"),
    ):
        assert (await firm.call(method, path)).status_code == 200, path


# ================================================================================================
# ENG-02: the record and the interim recorded letter (Story 6.2; AC-17)
# ================================================================================================


async def _accepted(firm: Firm, decided_at: datetime) -> tuple[uuid.UUID, Person]:
    """Bluestem: Accepted, its G1 decision at `decided_at`, no letter; Priya is its partner."""
    engagement = await firm.engagement(await firm.client("Bluestem"), status="accepted")
    await firm.accept(engagement, decided_at)
    priya = await firm.person(level="partner")
    await firm.member(engagement, priya, "engagement_partner")
    return engagement, priya


def _signed(on: date, copy: uuid.UUID, signer: uuid.UUID) -> Json:
    return {
        "mode": "signed",
        "client_signed_on": on.isoformat(),
        "firm_signed_on": on.isoformat(),
        "firm_signer_user_id": str(signer),
        "signed_copy_version_id": str(copy),
    }


async def test_ac17_a_letter_dated_before_the_g1_decision_answers_409(net: Net) -> None:
    firm = await _firm(net)
    decided = datetime.now(UTC).replace(microsecond=0) - timedelta(days=10)
    engagement, priya = await _accepted(firm, decided)
    copy = await firm.signed_copy(engagement)
    before = decided.date() - timedelta(days=1)
    facts = _refusal(
        await firm.call(
            "PUT",
            f"/v1/engagements/{engagement}/letter/record",
            priya,
            body=_signed(before, copy, priya.user_id),
        ),
        409,
        "letter_before_acceptance",
    )
    assert facts["engagement_id"] == str(engagement)
    # Nothing moved and nothing was recorded.
    record = _json(await firm.call("GET", f"/v1/engagements/{engagement}/record", priya))
    assert record["status"] == "accepted"
    assert cast(Json, record["letter"])["status"] == "not_signed"
    assert "letter.recorded" not in await firm.actions()


async def test_ac17_one_party_dated_before_the_decision_is_refused_too(net: Net) -> None:
    firm = await _firm(net)
    decided = datetime.now(UTC).replace(microsecond=0) - timedelta(days=10)
    engagement, priya = await _accepted(firm, decided)
    body = _signed(
        decided.date() + timedelta(days=1), await firm.signed_copy(engagement), priya.user_id
    )
    body["firm_signed_on"] = (decided.date() - timedelta(days=3)).isoformat()
    _refusal(
        await firm.call("PUT", f"/v1/engagements/{engagement}/letter/record", priya, body=body),
        409,
        "letter_before_acceptance",
    )


async def test_ac17_a_letter_after_the_decision_meets_g3_and_contracts_the_engagement(
    net: Net,
) -> None:
    firm = await _firm(net)
    decided = datetime.now(UTC).replace(microsecond=0) - timedelta(days=10)
    engagement, priya = await _accepted(firm, decided)
    copy = await firm.signed_copy(engagement)
    after = decided.date() + timedelta(days=2)
    out = _json(
        await firm.call(
            "PUT",
            f"/v1/engagements/{engagement}/letter/record",
            priya,
            body=_signed(after, copy, priya.user_id),
        )
    )
    assert out["status"] == "signed"
    assert out["engagement_status"] == "contracted"  # "Letter signed"
    assert out["client_signed_on"] == out["firm_signed_on"] == after.isoformat()
    assert out["signed_copy_version_id"] == str(copy)
    assert out["acceptance_decided_at"] is not None
    assert datetime.fromisoformat(str(out["acceptance_decided_at"])) == decided
    record = _json(await firm.call("GET", f"/v1/engagements/{engagement}/record", priya))
    assert record["status"] == "contracted"
    letter = cast(Json, record["letter"])
    assert letter["status"] == "signed"
    assert letter["signed_on"] == after.isoformat()
    gates = {str(g["gate"]): g for g in cast(list[Json], record["gates"])}
    assert gates["G1"]["met"] is True
    assert gates["G3"]["met"] is True
    assert (await firm.actions()).count("letter.recorded") == 1
    # The index stops listing it under "Letter │ Not signed".
    page = _json(await firm.call("GET", "/v1/engagements/index?letter=not_signed"))
    assert str(engagement) not in _ids(page)


async def test_ac17_with_g1_unmet_a_recorded_letter_answers_409_gate_unmet(net: Net) -> None:
    firm = await _firm(net)
    engagement = await firm.engagement(await firm.client("Granite Peak"), status="prospect")
    priya = await firm.person(level="partner")
    await firm.member(engagement, priya, "engagement_partner")
    copy = await firm.signed_copy(engagement)
    response = await firm.call(
        "PUT",
        f"/v1/engagements/{engagement}/letter/record",
        priya,
        body=_signed(date.today() - timedelta(days=1), copy, priya.user_id),
    )
    # Contract §6: 409 `gate_unmet` naming G1 (the matrix's `gates_met(G1)` would refuse the
    # same person with 403 instead; either way nothing is recorded).
    facts = _refusal(response, 409, "gate_unmet")
    assert facts["gate"] == "G1"
    assert "letter.recorded" not in await firm.actions()


async def test_ac17_an_archived_engagement_answers_409_and_its_record_is_read_only(
    net: Net,
) -> None:
    firm = await _firm(net)
    decided = datetime.now(UTC).replace(microsecond=0) - timedelta(days=30)
    engagement = await firm.engagement(await firm.client("Halvorsen"), status="archived")
    await firm.accept(engagement, decided)
    priya = await firm.person(level="partner")
    await firm.member(engagement, priya, "engagement_partner")
    record = _json(await firm.call("GET", f"/v1/engagements/{engagement}/record", priya))
    assert record["read_only_reason"] == "archived"
    assert "letter.record" not in cast(list[str], record["allowed_actions"])
    response = await firm.call(
        "PUT",
        f"/v1/engagements/{engagement}/letter/record",
        priya,
        body=_signed(
            decided.date() + timedelta(days=1), await firm.signed_copy(engagement), priya.user_id
        ),
    )
    _refusal(response, 409, "engagement_archived")


async def test_ac17_the_not_required_exception_fails_closed_while_its_setting_is_unregistered(
    net: Net,
) -> None:
    """DEC-224: "Not required this year" needs `allow_letter_exceptions`, not registered yet."""
    firm = await _firm(net)
    decided = datetime.now(UTC).replace(microsecond=0) - timedelta(days=10)
    engagement, priya = await _accepted(firm, decided)
    response = await firm.call(
        "PUT",
        f"/v1/engagements/{engagement}/letter/record",
        priya,
        body={"mode": "not_required_this_year", "not_required_reason": "Covered by the MSA"},
    )
    _refusal(response, 409, "letter_exceptions_off")
    record = _json(await firm.call("GET", f"/v1/engagements/{engagement}/record", priya))
    assert record["status"] == "accepted"


async def test_ac17_a_senior_cannot_record_the_letter(net: Net) -> None:
    firm = await _firm(net)
    decided = datetime.now(UTC).replace(microsecond=0) - timedelta(days=10)
    engagement, priya = await _accepted(firm, decided)
    senior = await firm.person(level="senior")
    await firm.member(engagement, senior, "senior")
    response = await firm.call(
        "PUT",
        f"/v1/engagements/{engagement}/letter/record",
        senior,
        body=_signed(
            decided.date() + timedelta(days=1), await firm.signed_copy(engagement), priya.user_id
        ),
    )
    assert response.status_code == 403, response.text


# ================================================================================================
# ENG-03: the catalogue (Story 6.3; AC-18)
# ================================================================================================


async def _hannah(firm: Firm) -> Person:
    """A partner by level: DEC-38's partner holds `engagement.create` (the derived
    `firm_partner`, DEC-225)."""
    return await firm.person(level="partner")


async def test_ac18_the_catalogue_holds_the_18_types_and_never_single_audit(net: Net) -> None:
    firm = await _firm(net)
    hannah = await _hannah(firm)
    items = cast(
        list[Json], _json(await firm.call("GET", "/v1/engagement-types", hannah))["items"]
    )
    codes = [str(i["code"]) for i in items]
    assert sorted(codes) == sorted((*TAX, *AUDIT, *CAS))
    assert len(codes) == len(set(codes)) == 18
    assert "single_audit" not in codes
    assert not any("single" in c for c in codes)
    families = {str(i["code"]): str(i["family"]) for i in items}
    assert {c for c, f in families.items() if f == "tax"} == set(TAX)
    assert {c for c, f in families.items() if f == "audit_assurance"} == set(AUDIT)
    assert {c for c, f in families.items() if f == "cas_advisory"} == set(CAS)
    for item in items:
        assert str(item["label"]).strip()
        assert "single" not in str(item["label"]).lower()


async def test_ac18_soc_cards_need_the_attest_entitlement(net: Net) -> None:
    firm = await _firm(net)
    hannah = await _hannah(firm)

    async def soc() -> dict[str, tuple[object, object]]:
        items = cast(
            list[Json], _json(await firm.call("GET", "/v1/engagement-types", hannah))["items"]
        )
        return {
            str(i["code"]): (i["availability"], i["entitlement"])
            for i in items
            if i["code"] in ("soc1", "soc2")
        }

    assert await soc() == {
        "soc1": ("needs_entitlement", "attest"),
        "soc2": ("needs_entitlement", "attest"),
    }
    await firm.entitle("attest")
    assert await soc() == {"soc1": ("available", "attest"), "soc2": ("available", "attest")}


async def test_ac18_only_fs_audit_allows_the_group_toggle(net: Net) -> None:
    firm = await _firm(net)
    await firm.entitle("group_audit")
    items = cast(
        list[Json],
        _json(await firm.call("GET", "/v1/engagement-types", await _hannah(firm)))["items"],
    )
    assert {str(i["code"]) for i in items if i["group_audit_allowed"]} == {"fs_audit"}


async def test_ac18_a_draft_naming_single_audit_or_an_unknown_code_answers_422(net: Net) -> None:
    firm = await _firm(net)
    hannah = await _hannah(firm)
    client, entity = await firm.client("Fairhaven")
    for code in ("single_audit", "made_up_type", "tax_compliance"):
        response = await firm.call(
            "POST",
            "/v1/engagement-drafts",
            hannah,
            body={"client_id": str(client), "client_entity_id": str(entity), "type_code": code},
        )
        _refusal(response, 422, "unknown_engagement_type")
    # And through an autosave of a draft that started without a type.
    draft = _json(
        await firm.call("POST", "/v1/engagement-drafts", hannah, body={"client_id": str(client)}),
        201,
    )
    response = await firm.call(
        "PATCH",
        f"/v1/engagement-drafts/{draft['id']}",
        hannah,
        body={"seen_version": draft["version"], "type_code": "single_audit"},
    )
    _refusal(response, 422, "unknown_engagement_type")
    assert not await firm.seed.value(
        "SELECT count(*) FROM engagements WHERE tenant_id = $1", firm.tenant
    )


# ================================================================================================
# ENG-03: drafts, G1, duplicates, cardinality and create (Story 6.3; AC-19)
# ================================================================================================


@dataclass(frozen=True)
class Wizard:
    firm: Firm
    hannah: Person
    partner: Person
    client: tuple[uuid.UUID, uuid.UUID]
    engagement: uuid.UUID | None  # the accepted (or prospect) engagement G1 reads


async def _wizard(
    net: Net, *, type_: str = "ebp_audit", status: str | None = "accepted", accepted: bool = True
) -> Wizard:
    """Fairhaven's engagement waiting to be completed (DEC-225's G1 source) with its partner."""
    firm = await _firm(net)
    hannah = await _hannah(firm)
    client = await firm.client("Fairhaven")
    partner = await firm.person(level="partner")
    engagement = None
    if status is not None:
        engagement = await firm.engagement(client, status=status, type_=type_)
        await firm.member(engagement, partner, "engagement_partner")
        if accepted:
            await firm.accept(engagement, datetime.now(UTC) - timedelta(days=3))
    return Wizard(firm, hannah, partner, client, engagement)


def _payload(w: Wizard, *, extra_team: Sequence[tuple[Person, str]] = ()) -> Json:
    return {
        "name": "Fairhaven 401(k) PY2025 EBP Audit",
        "period_label": "PY2025",
        "standards_code": "aicpa_gaas",
        "fiscal_period_start": FY_START.isoformat(),
        "fiscal_period_end": FY_END.isoformat(),
        "team": [
            {"user_id": str(w.partner.user_id), "role": "engagement_partner"},
            *({"user_id": str(p.user_id), "role": role} for p, role in extra_team),
        ],
    }


async def _draft(
    w: Wizard, type_code: str = "ebp_audit", payload: Json | None = None, **fields: object
) -> Json:
    body: Json = {
        "client_id": str(w.client[0]),
        "client_entity_id": str(w.client[1]),
        "type_code": type_code,
        "payload": payload or fields or _payload(w),
    }
    return _json(await w.firm.call("POST", "/v1/engagement-drafts", w.hannah, body=body), 201)


async def _create(
    w: Wizard, draft: Json, *, key: str | None = None, confirm: bool = False
) -> httpx.Response:
    return await w.firm.call(
        "POST",
        f"/v1/engagement-drafts/{draft['id']}/create",
        w.hannah,
        body={"confirm_duplicate": confirm},
        key=key or f"create-{uuid.uuid4().hex}",
    )


async def test_ac19_hannah_creates_the_fairhaven_ebp_audit_from_a_draft_in_one_unit_of_work(
    net: Net,
) -> None:
    w = await _wizard(net)
    staff = await w.firm.person(level="senior")
    draft = await _draft(w, payload=_payload(w, extra_team=[(staff, "senior")]))
    assert draft["created_by"] == str(w.hannah.user_id)
    for step in ("client_type", "standards_methodology", "period_deadlines", "team_independence"):
        check = _json(
            await w.firm.call(
                "POST",
                f"/v1/engagement-drafts/{draft['id']}/validate",
                w.hannah,
                body={"step": step},
            )
        )
        assert check["valid"] is True, check
    before = await w.firm.actions()
    made = _json(await _create(w, draft), 201)
    assert made["engagement_id"] == str(w.engagement)  # "resuming the draft completes" it
    assert made["engagement_status"] == "accepted"
    assert made["independence_requested_user_ids"] == [str(staff.user_id)]
    created = (await w.firm.actions())[len(before) :]
    assert created.count("engagement.created") == 1
    kinds = await w.firm.seed.rows(
        "SELECT kind FROM work_items WHERE tenant_id = $1 AND engagement_id = $2",
        w.firm.tenant,
        w.engagement,
    )
    assert [r["kind"] for r in kinds] == ["assurance"]  # one assurance item for an audit
    assert {str(i) for i in cast(list[str], made["work_item_ids"])} == {
        str(i)
        for i in [
            r["id"]
            for r in await w.firm.seed.rows(
                "SELECT id FROM work_items WHERE engagement_id = $1", w.engagement
            )
        ]
    }
    # The team member is staffed and asked to confirm independence.
    status = await w.firm.seed.value(
        "SELECT status FROM independence_confirmations WHERE engagement_id = $1 AND user_id = $2",
        w.engagement,
        staff.user_id,
    )
    assert status is not None and status != "confirmed"
    assert (
        await w.firm.seed.value("SELECT period_label FROM engagements WHERE id = $1", w.engagement)
        == "PY2025"
    )


async def test_ac19_g1_blocks_step_one_and_create_until_the_acceptance_is_decided(
    net: Net,
) -> None:
    """Granite Peak: no acceptance decision for this service and period; step 1 is invalid and
    create answers 409 `gate_unmet` (G1) until one is recorded, then the same draft passes."""
    w = await _wizard(net, status="prospect", accepted=False)
    draft = await _draft(w)
    gates = {str(g["gate"]): g for g in cast(list[Json], draft["gates"])}
    assert gates["G1"]["met"] is False
    check = _json(
        await w.firm.call(
            "POST",
            f"/v1/engagement-drafts/{draft['id']}/validate",
            w.hannah,
            body={"step": "client_type"},
        )
    )
    assert check["valid"] is False
    assert {str(g["gate"]): g["met"] for g in cast(list[Json], check["gates"])}["G1"] is False
    facts = _refusal(await _create(w, draft), 409, "gate_unmet")
    assert facts["gate"] == "G1"
    assert "engagement.created" not in await w.firm.actions()

    # The acceptance is decided (CLI-07; here SPEC-025's record) and the prospect is accepted.
    assert w.engagement is not None
    await w.firm.seed.run("UPDATE engagements SET status = 'accepted' WHERE id = $1", w.engagement)
    await w.firm.accept(w.engagement, datetime.now(UTC) - timedelta(minutes=5))
    check = _json(
        await w.firm.call(
            "POST",
            f"/v1/engagement-drafts/{draft['id']}/validate",
            w.hannah,
            body={"step": "client_type"},
        )
    )
    assert check["valid"] is True, check
    made = _json(await _create(w, draft), 201)
    assert made["engagement_id"] == str(w.engagement)


async def test_ac19_a_client_with_no_engagement_at_all_cannot_pass_step_one(net: Net) -> None:
    w = await _wizard(net, status=None)
    draft = await _draft(w)
    check = _json(
        await w.firm.call(
            "POST",
            f"/v1/engagement-drafts/{draft['id']}/validate",
            w.hannah,
            body={"step": "client_type"},
        )
    )
    assert check["valid"] is False
    _refusal(await _create(w, draft), 409, "gate_unmet")


async def test_ac19_a_duplicate_answers_409_until_confirm_duplicate(net: Net) -> None:
    """ "TY2025 Form 1040 already exists": 409 `possible_duplicate` naming it, then 201 with
    `confirm_duplicate`."""
    w = await _wizard(net, type_="tax_compliance")
    assert w.engagement is not None
    existing = await w.firm.engagement(w.client, status="active", type_="tax_compliance")
    draft = await _draft(
        w,
        "form_1040",
        name="Morgan & Kai Ferris TY2025 Form 1040",
        period_label="TY2025",
        fiscal_period_start=FY_START.isoformat(),
        fiscal_period_end=FY_END.isoformat(),
        team=[{"user_id": str(w.partner.user_id), "role": "engagement_partner"}],
    )
    facts = _refusal(await _create(w, draft), 409, "possible_duplicate")
    assert facts["engagement_id"] == str(existing)
    assert "engagement.created" not in await w.firm.actions()
    made = _json(await _create(w, draft, confirm=True), 201)
    assert made["engagement_id"] == str(w.engagement)


@pytest.mark.parametrize(
    ("type_code", "engagement_type", "kind", "count"),
    [
        ("form_1040", "tax_compliance", "tax_return", 1),
        ("forms_706_709", "tax_compliance", "tax_return", 2),
        ("fs_audit", "fs_audit", "assurance", 1),
        ("review", "review", "assurance", 1),
        ("cas_monthly_close", "cas_monthly_close", "close", 1),
        ("advisory", "advisory", "advisory_project", 1),
    ],
)
async def test_ac19_create_makes_the_work_items_by_type_cardinality(
    net: Net, type_code: str, engagement_type: str, kind: str, count: int
) -> None:
    """Chapter 03 §3.1 (DEC-225): one assurance item; one return per tax form, Forms 706/709
    two; the period's first close; one advisory project."""
    w = await _wizard(net, type_=engagement_type)
    draft = await _draft(
        w,
        type_code,
        name=f"Fairhaven {type_code}",
        standards_code="aicpa_gaas",
        fiscal_period_start=FY_START.isoformat(),
        fiscal_period_end=FY_END.isoformat(),
        team=[{"user_id": str(w.partner.user_id), "role": "engagement_partner"}],
    )
    made = _json(await _create(w, draft), 201)
    rows = await w.firm.seed.rows(
        "SELECT kind FROM work_items WHERE engagement_id = $1", w.engagement
    )
    assert [r["kind"] for r in rows] == [kind] * count
    assert len(cast(list[str], made["work_item_ids"])) == count


async def test_ac19_create_requires_an_idempotency_key_and_replays_it(net: Net) -> None:
    w = await _wizard(net)
    draft = await _draft(w)
    missing = await w.firm.call(
        "POST",
        f"/v1/engagement-drafts/{draft['id']}/create",
        w.hannah,
        body={"confirm_duplicate": False},
    )
    assert missing.status_code in (400, 422), missing.text
    assert "engagement.created" not in await w.firm.actions()
    key = f"fairhaven-create-{uuid.uuid4().hex}"
    first = _json(await _create(w, draft, key=key), 201)
    again = _json(await _create(w, draft, key=key), 201)
    assert again == first
    assert (await w.firm.actions()).count("engagement.created") == 1
    # A created draft answers its first result again, under a new key too (DEC-225).
    other = _json(await _create(w, draft), 201)
    assert other["engagement_id"] == first["engagement_id"]
    assert (await w.firm.actions()).count("engagement.created") == 1
    assert (
        await w.firm.seed.value(
            "SELECT count(*) FROM work_items WHERE engagement_id = $1", w.engagement
        )
        == 1
    )


async def test_ac19_create_refuses_a_draft_with_an_incomplete_step(net: Net) -> None:
    w = await _wizard(net)
    draft = await _draft(w, name="Fairhaven", fiscal_period_end=FY_END.isoformat())
    facts = _refusal(await _create(w, draft), 422, "draft_incomplete")
    assert facts["draft_id"] == draft["id"]
    assert facts["step"] in ("standards_methodology", "period_deadlines", "team_independence")


async def test_ac19_drafts_are_their_owners_only(net: Net) -> None:
    w = await _wizard(net)
    draft = await _draft(w)
    other = await _hannah(w.firm)  # another partner, who may create engagements herself
    admin = w.firm.admin  # even the firm admin
    for who in (other, admin):
        calls: tuple[tuple[str, str, Json | None], ...] = (
            ("GET", f"/v1/engagement-drafts/{draft['id']}", None),
            (
                "PATCH",
                f"/v1/engagement-drafts/{draft['id']}",
                {"seen_version": draft["version"], "step": "period_deadlines"},
            ),
            ("POST", f"/v1/engagement-drafts/{draft['id']}/validate", {"step": "client_type"}),
            ("DELETE", f"/v1/engagement-drafts/{draft['id']}", None),
        )
        for method, path, body in calls:
            _refusal(await w.firm.call(method, path, who, body=body), 404, "not found")
        response = await w.firm.call(
            "POST",
            f"/v1/engagement-drafts/{draft['id']}/create",
            who,
            body={"confirm_duplicate": False},
            key=f"k-{uuid.uuid4().hex}",
        )
        assert response.status_code == 404, response.text
    # The owner still has it, unchanged.
    mine = _json(await w.firm.call("GET", f"/v1/engagement-drafts/{draft['id']}", w.hannah))
    assert mine["version"] == draft["version"]
    assert "engagement.created" not in await w.firm.actions()


async def test_ac19_an_autosave_with_an_old_seen_version_answers_409(net: Net) -> None:
    w = await _wizard(net)
    draft = await _draft(w)
    saved = _json(
        await w.firm.call(
            "PATCH",
            f"/v1/engagement-drafts/{draft['id']}",
            w.hannah,
            body={"seen_version": draft["version"], "step": "standards_methodology"},
        )
    )
    assert cast(int, saved["version"]) > cast(int, draft["version"])
    facts = _refusal(
        await w.firm.call(
            "PATCH",
            f"/v1/engagement-drafts/{draft['id']}",
            w.hannah,
            body={"seen_version": draft["version"], "step": "period_deadlines"},
        ),
        409,
        "stale_version",
    )
    assert facts["draft_id"] == draft["id"]


async def test_ac19_a_draft_naming_another_clients_entity_answers_422(net: Net) -> None:
    w = await _wizard(net)
    _, foreign_entity = await w.firm.client("Lakeshore")
    response = await w.firm.call(
        "POST",
        "/v1/engagement-drafts",
        w.hannah,
        body={
            "client_id": str(w.client[0]),
            "client_entity_id": str(foreign_entity),
            "type_code": "ebp_audit",
        },
    )
    facts = _refusal(response, 422, "entity_outside_client")
    assert facts["client_entity_id"] == str(foreign_entity)


async def test_ac19_a_staff_member_without_engagement_create_is_refused(net: Net) -> None:
    w = await _wizard(net)
    senior = await w.firm.person(level="senior")
    calls: tuple[tuple[str, str, Json | None], ...] = (
        ("GET", "/v1/engagement-types", None),
        ("POST", "/v1/engagement-drafts", {"client_id": str(w.client[0])}),
    )
    for method, path, body in calls:
        response = await w.firm.call(method, path, senior, body=body)
        assert response.status_code == 403, (path, response.text)


# ================================================================================================
# Human-only: agent and system principals (contract §5; AC-12; I-AGENT-NEVER)
# ================================================================================================


async def test_ac12_agent_and_system_are_refused_engagement_create_letter_and_intake(
    net: Net,
) -> None:
    w = await _wizard(net)
    assert w.engagement is not None
    person = AuthContext(
        TenantContext(w.firm.tenant, "human", str(w.partner.user_id)),
        w.partner.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC) - timedelta(minutes=1),
    )
    resource = await engagement_resource(person.tenant, w.engagement)
    await authorise(person, "letter.record", resource)  # the partner herself may
    actions = ("engagement.create", "letter.record", "client.intake")
    run = uuid.uuid4()
    agent = AgentContext(
        tenant=TenantContext(w.firm.tenant, "agent", f"agent:probe:{run}", w.partner.user_id),
        agent_id="probe",
        agent_run_id=run,
        engagement_id=w.engagement,
        task_scope=frozenset(actions),
        initiator=person,
        issued_by=_ISSUER,
    )
    for action in actions:
        for target in (resource, Resource.firm(w.firm.tenant)):
            with pytest.raises(Forbidden):
                await authorise(agent, action, target)
    # The matrix itself denies both principals and grants no client role (contract §5).
    for action in actions:
        decisions = RULES[action].decisions
        for principal in ("agent", "system"):
            assert decisions.get(principal, "deny") == "deny", (action, decisions)
        assert not {
            r
            for r, d in decisions.items()
            if r.startswith("client_") and r != "client_service" and d != "deny"
        }
