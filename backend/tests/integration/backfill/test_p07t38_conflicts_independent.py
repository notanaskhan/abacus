# ac-test-author: ayushkbhatia
"""SPEC-332 AC-23 to AC-26 for P-07-T36 (P-07-T38): conflict checks over clients, entities,
contacts, relationships and counterparties, matches on walled clients redacted for the walled
reader (INV-3), clearance by a manager or partner with a reason (human-only, audited), and
screening results recorded by a person. "The Harborline hit is cleared by Samuel Ito with a
reason, and a match on a walled client shows no name to the walled user."

Read from SPEC-332 §5 Story 7, P-07 §3.3 Story 3.1, §4.2 M6, §4.3 and §4.4, the CLI-06 screen
contract (h: "Harborline Trust Company" → "Counterparty · custodian for Calloway Family Trust —
review" with "Clear as not adverse…" for a manager), `docs/contracts/acceptance-independence.md`,
the organisations matrix, `error-codes.yaml` and the human-only register. HTTP through
`create_app()` behind `engagements.acceptance_v2`; the live-human layer through
`organisations.api`, the database layer as raw SQL.

Spec drift followed here (TASK-1257): the matrix's manager cells on `conflict.run`,
`conflict.clear` and `screening.record` (P-07 §4.3, CLI-06) land with T36 as a derived firm-level
manager grant (DEC-326 deferred them), so Samuel, a manager-level member with no firm role, runs
and clears. A firm admin runs checks and records screening but does not clear (§4.3).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final, cast

import asyncpg
import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import ActorKind
from abacus.modules.identity.api import RULES, AuthContext, Forbidden

from .support import Net, Person, Seeder

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
CHECKS: Final = "/v1/conflict-checks"


@dataclass(frozen=True)
class Intake:
    """Grace Holloway's Thornbury estate intake. Samuel Ito (manager level) is walled from
    Ashford Holdings; Daniel Reyes is a partner; Kira Ross staff. Calloway Family Trust has
    Harborline Trust Company as its custodian; Fenwick LLC owns part of Okafor Partners."""

    net: Net
    seed: Seeder
    tenant: uuid.UUID
    grace: Person
    samuel: Person
    daniel: Person
    kira: Person
    marker: str
    estate_entity: uuid.UUID
    ashford: uuid.UUID
    calloway: uuid.UUID
    meridian: uuid.UUID
    fenwick: uuid.UUID
    okafor: uuid.UUID
    harborline: uuid.UUID

    def name(self, base: str) -> str:
        return f"{base} {self.marker}"

    async def call(
        self, method: str, path: str, who: Person, body: Mapping[str, object] | None = None
    ) -> httpx.Response:
        return await self.net.call(method, path, who, body=body)

    async def run(self, who: Person, *names: str) -> httpx.Response:
        return await self.call(
            "POST",
            CHECKS,
            who,
            {
                "subject": {"kind": "client_entity", "id": str(self.estate_entity)},
                "names": list(names),
            },
        )

    async def audit(self, action: str) -> list[tuple[str, str]]:
        rows = await self.seed.rows(
            "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 AND action = $2 "
            "ORDER BY seq",
            self.tenant,
            action,
        )
        return [(str(r["actor_kind"]), str(r["actor_id"])) for r in rows]


def _json(response: httpx.Response, status: int = 200) -> Json:
    assert response.status_code == status, response.text
    return cast(Json, response.json())


def _results(check: Json) -> list[Json]:
    return cast(list[Json], check["results"])


async def _client(seed: Seeder, tenant: uuid.UUID, name: str) -> tuple[uuid.UUID, uuid.UUID]:
    client = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id", tenant, name
        ),
    )
    entity = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            tenant,
            client,
            name,
        ),
    )
    return client, entity


async def _level(seed: Seeder, tenant: uuid.UUID, who: Person, level: str) -> None:
    await seed.run(
        "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        who.user_id,
        level,
    )


@pytest.fixture
async def intake(net: Net) -> Intake:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'engagements.acceptance_v2', 'true', 'test-seed', 'P-07-T38')",
        tenant,
    )
    grace = await seed.person(tenant, "firm_admin")
    samuel = await seed.person(tenant)
    await _level(seed, tenant, samuel, "manager")
    daniel = await seed.person(tenant)
    await _level(seed, tenant, daniel, "partner")
    kira = await seed.person(tenant)
    await _level(seed, tenant, kira, "staff")
    marker = uuid.uuid4().hex[:6]

    def n(base: str) -> str:
        return f"{base} {marker}"

    _, estate = await _client(seed, tenant, n("Estate of Walter Thornbury"))
    ashford, _ = await _client(seed, tenant, n("Ashford Holdings"))
    calloway, calloway_entity = await _client(seed, tenant, n("Calloway Family Trust"))
    meridian, _ = await _client(seed, tenant, n("Meridian Tool and Die"))
    fenwick, fenwick_entity = await _client(seed, tenant, n("Fenwick LLC"))
    okafor, okafor_entity = await _client(seed, tenant, n("Okafor Partners"))
    harborline = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, organisation_name, "
            "contact_kind, party_kind) VALUES ($1, $2, $3, $3, 'third_party', 'organisation') "
            "RETURNING id",
            tenant,
            calloway,
            n("Harborline Trust Company"),
        ),
    )
    await seed.run(
        "INSERT INTO contact_roles (tenant_id, contact_id, scope_kind, scope_id, role) "
        "VALUES ($1, $2, 'client_entity', $3, 'custodian')",
        tenant,
        harborline,
        calloway_entity,
    )
    await seed.run(
        "INSERT INTO entity_relationships (tenant_id, from_entity_id, to_entity_id, kind, "
        "percent, effective_from, created_by) VALUES ($1, $2, $3, 'owner_of', 40, $4, $5)",
        tenant,
        fenwick_entity,
        okafor_entity,
        date(2020, 1, 1),
        grace.user_id,
    )
    walled = await net.call(
        "POST",
        "/v1/walls",
        grace,
        body={"user_id": str(samuel.user_id), "client_id": str(ashford)},
    )
    assert walled.status_code == 201, walled.text
    return Intake(
        net,
        seed,
        tenant,
        grace,
        samuel,
        daniel,
        kira,
        marker,
        estate,
        ashford,
        calloway,
        meridian,
        fenwick,
        okafor,
        harborline,
    )


# ================================================================================================
# AC-23: the search
# ================================================================================================


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1259: P-07-T36 not built; conflict routes answer 501 (main at #409)",
)
async def test_ac23_the_check_finds_clients_counterparties_and_relationships(
    intake: Intake,
) -> None:
    check = _json(
        await intake.run(
            intake.grace,
            intake.name("Harborline Trust Company"),
            intake.name("Meridian Tool and Die"),
            intake.name("Fenwick LLC"),
            intake.name("Nobody We Know Whatsoever"),
        ),
        201,
    )
    assert check["outcome"] == "hits"
    assert check["names_count"] == 4
    assert check["run_by"] == str(intake.grace.user_id)
    assert check["subject"] == {"kind": "client_entity", "id": str(intake.estate_entity)}
    found = {(r["matched_client_id"], r["match_kind"]) for r in _results(check)}
    assert (str(intake.calloway), "counterparty") in found
    assert (str(intake.meridian), "exact") in found
    assert (str(intake.fenwick), "exact") in found
    assert (str(intake.okafor), "relationship") in found
    harborline = next(r for r in _results(check) if r["match_kind"] == "counterparty")
    assert harborline["redacted"] is False
    assert harborline["assessment"] == "counterparty_review"
    assert harborline["matched_ref_type"] == "contact"
    assert harborline["matched_ref_id"] == str(intake.harborline)
    assert intake.name("Harborline Trust Company") == harborline["matched_name"]
    assert await intake.audit("conflict_check.run") == [("human", str(intake.grace.user_id))]
    # The names are sealed at rest.
    row = await intake.seed.rows(
        "SELECT * FROM conflict_checks WHERE id = $1", uuid.UUID(cast(str, check["id"]))
    )
    assert "Harborline" not in str(dict(row[0]))
    # Read back, the check is the same.
    again = _json(await intake.call("GET", f"{CHECKS}/{check['id']}", intake.daniel))
    assert {r["id"] for r in _results(again)} == {r["id"] for r in _results(check)}


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1259: P-07-T36 not built; conflict routes answer 501 (main at #409)",
)
async def test_ac23_a_near_spelling_is_a_trigram_match_and_no_match_is_clear(
    intake: Intake,
) -> None:
    check = _json(await intake.run(intake.grace, intake.name("Meridian Tool and Dye")), 201)
    kinds = {(r["matched_client_id"], r["match_kind"]) for r in _results(check)}
    assert (str(intake.meridian), "trigram") in kinds
    score = next(r for r in _results(check) if r["matched_client_id"] == str(intake.meridian))
    assert 0 < cast(float, score["score"]) < 1
    clear = _json(await intake.run(intake.grace, "Zebulon Quartermaine Xylophones"), 201)
    assert clear["outcome"] == "clear"
    assert clear["results"] == []


async def test_ac23_at_most_fifty_names(intake: Intake) -> None:
    response = await intake.run(intake.grace, *(f"Name {i}" for i in range(51)))
    assert response.status_code == 422, response.text


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1259: P-07-T36 not built; conflict routes answer 501 (main at #409)",
)
async def test_ac23_who_runs_a_check(intake: Intake) -> None:
    for who in (intake.grace, intake.samuel, intake.daniel):
        _json(await intake.run(who, intake.name("Meridian Tool and Die")), 201)
    refused = await intake.run(intake.kira, intake.name("Meridian Tool and Die"))
    assert refused.status_code == 403, refused.text


# ================================================================================================
# AC-24: redaction for the walled reader (INV-3)
# ================================================================================================


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1259: P-07-T36 not built; conflict routes answer 501 (main at #409)",
)
async def test_ac24_a_match_on_a_walled_client_shows_samuel_no_name(intake: Intake) -> None:
    response = await intake.run(
        intake.samuel, intake.name("Ashford Holdings"), intake.name("Meridian Tool and Die")
    )
    check = _json(response, 201)
    redacted = [r for r in _results(check) if r["redacted"] is True]
    assert len(redacted) == 1
    row = redacted[0]
    assert row["match_kind"] in ("exact", "trigram")
    assert row["assessment"] == "pending"
    for field in ("matched_client_id", "matched_name", "matched_ref_type", "matched_ref_id"):
        assert row.get(field) is None, field
    assert row.get("score") is None
    assert row.get("allowed_actions") in (None, [])
    assert "Ashford" not in response.text
    assert str(intake.ashford) not in response.text
    assert not [k for k in check if "wall" in k or "hidden" in k]
    # The unwalled colleague sees the same row in full.
    full = _json(await intake.call("GET", f"{CHECKS}/{check['id']}", intake.daniel))
    named = next(r for r in _results(full) if r["id"] == row["id"])
    assert named["redacted"] is False
    assert named["matched_client_id"] == str(intake.ashford)
    assert intake.name("Ashford Holdings") == named["matched_name"]
    # Samuel's read of a check someone else ran is redacted the same way.
    by_daniel = _json(await intake.run(intake.daniel, intake.name("Ashford Holdings")), 201)
    seen = await intake.call("GET", f"{CHECKS}/{by_daniel['id']}", intake.samuel)
    assert seen.status_code == 200, seen.text
    assert "Ashford" not in seen.text
    assert all(r["redacted"] is True for r in _results(cast(Json, seen.json())))
    # Samuel cannot clear what he cannot see: 404, as for an unknown result.
    refused = await intake.call(
        "POST",
        f"{CHECKS}/{check['id']}/results/{row['id']}/clear",
        intake.samuel,
        {"assessment": "not_adverse", "reason": "Unrelated business"},
    )
    assert refused.status_code == 404, refused.text
    unknown = await intake.call(
        "POST",
        f"{CHECKS}/{check['id']}/results/{uuid.uuid4()}/clear",
        intake.samuel,
        {"assessment": "not_adverse", "reason": "Unrelated business"},
    )
    assert unknown.status_code == 404
    assert refused.json() == unknown.json()


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1259: P-07-T36 not built; conflict routes answer 501 (main at #409)",
)
async def test_ac24_another_firm_never_reads_a_check(intake: Intake) -> None:
    check = _json(await intake.run(intake.grace, intake.name("Meridian Tool and Die")), 201)
    other = await intake.seed.firm()
    stranger = await intake.seed.person(other, "firm_admin")
    response = await intake.net.call("GET", f"{CHECKS}/{check['id']}", stranger)
    assert response.status_code == 404, response.text


# ================================================================================================
# AC-25: clearance
# ================================================================================================


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1259: P-07-T36 not built; conflict routes answer 501 (main at #409)",
)
async def test_ac25_samuel_clears_the_harborline_hit_with_a_reason(intake: Intake) -> None:
    check = _json(await intake.run(intake.grace, intake.name("Harborline Trust Company")), 201)
    hit = next(r for r in _results(check) if r["match_kind"] == "counterparty")
    path = f"{CHECKS}/{check['id']}/results/{hit['id']}/clear"
    reason = "Custodian only: no adverse interest in the Thornbury estate"
    # No reason, no clearance.
    blank = await intake.call("POST", path, intake.samuel, {"assessment": "not_adverse"})
    assert blank.status_code == 422, blank.text
    # A firm admin runs checks but does not clear them; staff neither.
    for who in (intake.grace, intake.kira):
        refused = await intake.call(
            "POST", path, who, {"assessment": "not_adverse", "reason": reason}
        )
        assert refused.status_code == 403, refused.text
    cleared = _json(
        await intake.call(
            "POST", path, intake.samuel, {"assessment": "not_adverse", "reason": reason}
        )
    )
    assert cleared["assessment"] == "not_adverse"
    assert cleared["cleared_by"] == str(intake.samuel.user_id)
    assert cleared["cleared_at"] is not None
    assert await intake.audit("conflict.cleared") == [("human", str(intake.samuel.user_id))]
    again = _json(await intake.call("GET", f"{CHECKS}/{check['id']}", intake.daniel))
    assert next(r for r in _results(again) if r["id"] == hit["id"])["assessment"] == (
        "not_adverse"
    )
    # The reason is sealed; the clearance never changes.
    rows = await intake.seed.rows(
        "SELECT * FROM conflict_result_events WHERE tenant_id = $1", intake.tenant
    )
    assert len(rows) == 1
    assert "Custodian only" not in str(dict(rows[0]))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await intake.seed.run(
            "UPDATE conflict_result_events SET assessment = 'conflict' WHERE tenant_id = $1",
            intake.tenant,
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await intake.seed.run(
            "DELETE FROM conflict_result_events WHERE tenant_id = $1", intake.tenant
        )


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1259: P-07-T36 not built; conflict routes answer 501 (main at #409)",
)
async def test_ac25_a_partner_may_record_a_conflict(intake: Intake) -> None:
    check = _json(await intake.run(intake.daniel, intake.name("Fenwick LLC")), 201)
    hit = next(r for r in _results(check) if r["match_kind"] == "exact")
    done = _json(
        await intake.call(
            "POST",
            f"{CHECKS}/{check['id']}/results/{hit['id']}/clear",
            intake.daniel,
            {"assessment": "conflict", "reason": "Fenwick is adverse in the estate dispute"},
        )
    )
    assert done["assessment"] == "conflict"


async def test_ac25_the_matrix_denies_the_agent_and_the_system_every_conflict_action() -> None:
    for action in ("conflict.run", "conflict.clear", "screening.record"):
        decisions = RULES[action].decisions
        assert decisions.get("agent") == "deny", action
        assert decisions.get("system") == "deny", action
        assert not {r for r, d in decisions.items() if r.startswith("client_") and d != "deny"}


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1259: P-07-T36 not built; conflict routes answer 501 (main at #409)",
)
async def test_ac25_the_service_and_the_database_refuse_a_non_human_clearance(
    intake: Intake,
) -> None:
    from abacus.modules.organisations import api as organisations_api

    # P-07 §4.1's public clearance function, looked up by name so this suite type-checks before
    # T36 adds it.
    function = "clear_conflict_result"
    clear = cast(Callable[..., Awaitable[object]], getattr(organisations_api, function))
    check = _json(await intake.run(intake.grace, intake.name("Harborline Trust Company")), 201)
    hit = next(r for r in _results(check) if r["match_kind"] == "counterparty")
    fresh = datetime.now(UTC) - timedelta(minutes=1)
    for kind in ("agent", "system"):
        ctx = AuthContext(
            TenantContext(intake.tenant, cast(ActorKind, kind), str(intake.samuel.user_id)),
            intake.samuel.user_id,
            uuid.uuid4(),
            None,
            fresh,
        )
        with pytest.raises(Forbidden):
            await clear(
                ctx,
                uuid.UUID(cast(str, check["id"])),
                uuid.UUID(cast(str, hit["id"])),
                assessment="not_adverse",
                reason="An agent never clears a conflict.",
            )
    for kind in ("agent", "policy"):
        with pytest.raises(asyncpg.CheckViolationError):
            await intake.seed.run(
                "INSERT INTO conflict_result_events (tenant_id, result_id, assessment, "
                "reason_sealed, cleared_by, actor_kind) VALUES ($1, $2, 'not_adverse', "
                "'\\x00'::bytea, $3, $4)",
                intake.tenant,
                uuid.UUID(cast(str, hit["id"])),
                intake.samuel.user_id,
                kind,
            )
    assert await intake.audit("conflict.cleared") == []


# ================================================================================================
# AC-26: screening recorded by a person
# ================================================================================================


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1259: P-07-T36 not built; conflict routes answer 501 (main at #409)",
)
async def test_ac26_grace_records_a_screening_result_by_hand(intake: Intake) -> None:
    body: Json = {
        "subject": {"kind": "client_entity", "id": str(intake.estate_entity)},
        "screening_list": "ofac_sdn",
        "result": "no_match",
        "note": "Searched the SDN list for all four names on Sep 8",
    }
    recorded = _json(await intake.call("POST", "/v1/screening-records", intake.grace, body), 201)
    assert recorded["recorded_by"] == str(intake.grace.user_id)
    assert recorded["screening_list"] == "ofac_sdn"
    assert recorded["result"] == "no_match"
    assert recorded["recorded_at"] is not None
    assert await intake.audit("screening.recorded") == [("human", str(intake.grace.user_id))]
    refused = await intake.call("POST", "/v1/screening-records", intake.kira, body)
    assert refused.status_code == 403, refused.text
    _json(await intake.call("POST", "/v1/screening-records", intake.samuel, body), 201)
    rows = await intake.seed.rows(
        "SELECT * FROM screening_records WHERE tenant_id = $1", intake.tenant
    )
    assert len(rows) == 2
    assert "SDN list" not in str(dict(rows[0]))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await intake.seed.run(
            "UPDATE screening_records SET result = 'match' WHERE tenant_id = $1", intake.tenant
        )
