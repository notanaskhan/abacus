"""P-07-T36 (TASK-1259; DEC-373) beyond the independent suite: an ended relationship is not a
match, a subject on a walled client answers 404 to the run, a redacted row has exactly the
contract's keys with nulls, and the results never change."""

from __future__ import annotations

import uuid
from datetime import date
from typing import cast

import asyncpg
import pytest

from .support import Net, Person

pytestmark = pytest.mark.asyncio
Json = dict[str, object]


async def _client(net: Net, tenant: uuid.UUID, name: str) -> tuple[uuid.UUID, uuid.UUID]:
    client = cast(
        uuid.UUID,
        await net.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id", tenant, name
        ),
    )
    entity = cast(
        uuid.UUID,
        await net.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            tenant,
            client,
            name,
        ),
    )
    return client, entity


async def _firm(net: Net) -> tuple[uuid.UUID, Person, Person]:
    tenant = await net.seed.firm()
    await net.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'engagements.acceptance_v2', 'true', 'test-seed', 'TASK-1259')",
        tenant,
    )
    admin = await net.seed.person(tenant, "firm_admin")
    manager = await net.seed.person(tenant)
    await net.seed.run(
        "UPDATE memberships SET level = 'manager' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        manager.user_id,
    )
    return tenant, admin, manager


async def _run(net: Net, who: Person, subject: tuple[str, uuid.UUID], *names: str) -> Json:
    response = await net.call(
        "POST",
        "/v1/conflict-checks",
        who,
        body={"subject": {"kind": subject[0], "id": str(subject[1])}, "names": list(names)},
    )
    assert response.status_code == 201, response.text
    return cast(Json, response.json())


async def test_an_ended_relationship_is_not_a_match(net: Net) -> None:
    tenant, admin, _ = await _firm(net)
    _, subject = await _client(net, tenant, "Subject Estate")
    _, upper = await _client(net, tenant, "Larkspur Holdings")
    lower, lower_entity = await _client(net, tenant, "Quill Ventures")
    await net.seed.run(
        "INSERT INTO entity_relationships (tenant_id, from_entity_id, to_entity_id, kind, "
        "effective_from, effective_to, created_by) VALUES ($1, $2, $3, 'owner_of', $4, $5, $6)",
        tenant,
        upper,
        lower_entity,
        date(2015, 1, 1),
        date(2019, 12, 31),
        admin.user_id,
    )
    check = await _run(net, admin, ("client_entity", subject), "Larkspur Holdings")
    kinds = {(r["matched_client_id"], r["match_kind"]) for r in cast(list[Json], check["results"])}
    assert (str(lower), "relationship") not in kinds


async def test_a_walled_subject_answers_404_and_a_redacted_row_is_only_the_contracts_keys(
    net: Net,
) -> None:
    tenant, admin, manager = await _firm(net)
    walled, walled_entity = await _client(net, tenant, "Brambleton Group")
    _, subject = await _client(net, tenant, "Open Subject")
    response = await net.call(
        "POST",
        "/v1/walls",
        admin,
        body={"user_id": str(manager.user_id), "client_id": str(walled)},
    )
    assert response.status_code == 201, response.text
    refused = await net.call(
        "POST",
        "/v1/conflict-checks",
        manager,
        body={"subject": {"kind": "client_entity", "id": str(walled_entity)}, "names": ["x"]},
    )
    assert refused.status_code == 404, refused.text
    check = await _run(net, manager, ("client_entity", subject), "Brambleton Group")
    row = cast(list[Json], check["results"])[0]
    assert row["redacted"] is True
    assert {k for k, v in row.items() if v not in (None, [])} == {
        "id",
        "redacted",
        "match_kind",
        "assessment",
    }
    assert check["outcome"] == "hits"
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await net.seed.run("UPDATE conflict_results SET score = 1 WHERE tenant_id = $1", tenant)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await net.seed.run("DELETE FROM conflict_checks WHERE tenant_id = $1", tenant)
