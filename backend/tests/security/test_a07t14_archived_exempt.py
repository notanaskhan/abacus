"""A-07-T14 (TASK-5118; A-07 F8; ADR P-43): `archived_exempt` and the route table.

Row acceptance: "The generated route-table test lists every mutating route, all answer 409
archived on a locked work item, and only the declared exempt actions pass." The trigger answers 409
(`test_a07t13_archived_guard.py`); here every mutating route's action is checked against an
archived resource and the matrix's exempt list, and the API's mapping of the SQLSTATE is checked.
"""

from __future__ import annotations

import json
from typing import cast

import pytest
from starlette.requests import Request

from abacus.api.app import _db_error  # pyright: ignore[reportPrivateUsage]  # the handler itself
from abacus.api.export_openapi import document
from abacus.modules.identity.authz.matrix import ARCHIVED_EXEMPT_KINDS, RULES

EXEMPT = {
    "archive.verify": "verify",
    "archive_addition.create": "archive_addition",
    "archive_addition.approve": "archive_addition",
    "legal_hold.place": "legal_hold",
    "legal_hold.lift": "legal_hold",
    "export.create": "export",
}
MUTATING = {"post", "put", "patch", "delete"}


def _mutating_actions() -> set[str]:
    paths = cast(dict[str, dict[str, dict[str, object]]], json.loads(document())["paths"])
    found: set[str] = set()
    for item in paths.values():
        for method, operation in item.items():
            action = operation.get("x-abacus-action")
            if method in MUTATING and isinstance(action, str):
                found.add(action)
    return found & set(RULES)  # `own` and the like are the route's own rule, not a matrix action


def test_only_the_declared_actions_are_exempt() -> None:
    declared = {a: r.archived_exempt for a, r in RULES.items() if r.archived_exempt}
    assert declared == EXEMPT
    assert set(declared.values()) == set(ARCHIVED_EXEMPT_KINDS)


def test_every_mutating_route_is_refused_on_an_archived_resource() -> None:
    """`authorise` refuses an archived resource unless the action only reads or is exempt, so the
    list of what still passes is exactly these."""
    mutating = _mutating_actions()
    assert len(mutating) > 100
    passes = {a for a in mutating if RULES[a].archived_exempt is not None}
    assert passes <= set(EXEMPT)
    refused = {a for a in mutating if not RULES[a].reads and RULES[a].archived_exempt is None}
    assert "proposed_entry.send_to_client" in refused
    assert "archive_addition.create" not in refused


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


async def test_the_sqlstate_answers_409_archived() -> None:
    class Orig:
        sqlstate = "AB409"

    class Raised(Exception):
        orig = Orig()

    response = await _db_error(_request(), Raised())
    assert response.status_code == 409
    assert json.loads(bytes(response.body))["detail"] == "archived"


async def test_any_other_database_error_stays_a_500() -> None:
    class Orig:
        sqlstate = "23505"

    class Raised(Exception):
        orig = Orig()

    with pytest.raises(Raised):
        await _db_error(_request(), Raised())
