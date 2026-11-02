# ac-test-author: ayushkbhatia
"""A-04-T17 (TASK-2905; ADR-078): independent acceptance tests for A-04-T12's materiality
service: the decide is human-only at the matrix, the service and the database; a rationale and a
fresh second factor are required; a new proposal supersedes the decided version only through the
partner's next decision; nothing reaches a client principal.

Written from A-04 §3.3 and §3.9, not from the builder's tests; the fixture is A-04-T12's (the
firm imports its materiality policy through K-02).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Final, cast

import pytest
import yaml

from .tb_support import Books, Json
from .test_a04t12_materiality_service import (
    _decide,  # pyright: ignore[reportPrivateUsage] -- A-04-T12's helpers
    _keyed,  # pyright: ignore[reportPrivateUsage] -- a sibling suite\'s helper
    _path,  # pyright: ignore[reportPrivateUsage] -- a sibling suite\'s helper
    _propose,  # pyright: ignore[reportPrivateUsage] -- a sibling suite\'s helper
)
from .test_a04t12_materiality_service import world as materiality_world

pytestmark = pytest.mark.asyncio

world = materiality_world
REPO: Final = Path(__file__).resolve().parents[4]


def test_the_matrix_denies_decide_to_the_agent_and_the_system() -> None:
    matrix = yaml.safe_load(
        (REPO / "docs/architecture/permission-matrix/review.yaml").read_text(encoding="utf-8")
    )
    rows = cast(dict[str, dict[str, str]], matrix["actions"])
    decide = rows["decision.decide"]
    assert (decide["agent"], decide["system"]) == ("deny", "deny")
    assert decide["reserved_role"] == "required" and decide["mfa_recent"] == "required"


async def test_the_database_refuses_a_decision_not_made_by_a_person(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, tb_id = world
    proposed = await _propose(books_, tb_id)
    card = uuid.UUID(cast(str, proposed["decision_card_id"]))
    # The CHECK (0094) admits only a person, and only the session's own person.
    for kind in ("agent", "system", "support"):
        with pytest.raises(Exception) as refused:
            await books_.seed.run(
                "INSERT INTO decisions (tenant_id, card_id, option_key, rationale_sealed, "
                "factors, seen_card_version, decided_by, actor_kind, actor_id) "
                "VALUES ($1, $2, 'rate_1_5', '\\x00', '[]', 1, $3, $4, $5)",
                books_.tenant_id,
                card,
                books_.partner.user_id,
                kind,
                str(books_.partner.user_id),
            )
        assert refused.value is not None, kind


async def test_a_decide_without_a_fresh_second_factor_is_refused(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, tb_id = world
    proposed = await _propose(books_, tb_id)
    found = await books_.call(
        "POST",
        f"/v1/decision-cards/{proposed['decision_card_id']}/decide",
        books_.partner,
        _decide(),
        mfa=False,
    )
    assert (found.status_code, found.json()["detail"]) == (403, "mfa_required")


async def test_a_blank_rationale_is_refused(world: tuple[Books, uuid.UUID]) -> None:
    books_, tb_id = world
    proposed = await _propose(books_, tb_id)
    found = await books_.call(
        "POST",
        f"/v1/decision-cards/{proposed['decision_card_id']}/decide",
        books_.partner,
        _decide(rationale="   "),
    )
    assert (found.status_code, found.json()["detail"]) == (422, "rationale_required")


async def test_a_new_proposal_after_a_decision_is_v3_and_v2_stands_until_decided(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, tb_id = world
    first = await _propose(books_, tb_id)
    decided = await books_.call(
        "POST",
        f"/v1/decision-cards/{first['decision_card_id']}/decide",
        books_.partner,
        _decide(),
    )
    assert decided.status_code == 200, decided.text
    again = await books_.call(
        "POST",
        _path(books_, "/proposals"),
        books_.manager,
        {"tb_snapshot_id": str(tb_id), "benchmark_key": "net_assets", "rate_pct": "2.0"},
        headers=_keyed(),
    )
    assert again.status_code == 201, again.text
    keys = [o["key"] for o in cast(list[Json], again.json()["options"])]
    assert keys == ["rate_1_0", "rate_1_5", "rate_2_0"]
    record = cast(Json, (await books_.call("GET", _path(books_, "/current"), books_.staff)).json())
    versions = cast(list[Json], record["versions"])
    assert [(v["version_no"], v["status"]) for v in versions] == [
        (1, "proposed"),
        (2, "decided"),
        (3, "proposed"),
    ]
    assert record["pending_card_id"] == again.json()["decision_card_id"]


async def test_a_rate_outside_the_firm_range_is_never_proposed(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, tb_id = world
    found = await books_.call(
        "POST",
        _path(books_, "/proposals"),
        books_.manager,
        {"tb_snapshot_id": str(tb_id), "benchmark_key": "net_assets", "rate_pct": "2.5"},
        headers=_keyed(),
    )
    assert (found.status_code, found.json()["detail"]) == (409, "outside_policy")
    count = await books_.seed.value(
        "SELECT count(*) FROM decision_cards WHERE tenant_id = $1", books_.tenant_id
    )
    assert count == 0


async def test_staff_may_read_but_not_propose(world: tuple[Books, uuid.UUID]) -> None:
    books_, tb_id = world
    found = await books_.call(
        "POST",
        _path(books_, "/proposals"),
        books_.staff,
        {"tb_snapshot_id": str(tb_id), "benchmark_key": "net_assets"},
        headers=_keyed(),
    )
    assert found.status_code == 403
    read = await books_.call("GET", _path(books_, "/current"), books_.staff)
    assert read.status_code == 200
