# ac-test-author: ayushkbhatia
"""A-09-T06 (TASK-8056; SPEC-658 AC-0.3, AC-0.5; DEC-5041): AY's consumer tests for N's C9 v2.1
and C8 v1.1 stubs. Every operation declares one action with 404 and 501; every field is
classified; no client principal holds a consolidation or elimination action; and the Harlow & Pike
fixtures foot (they fail the moment a seed total stops footing).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import unclassified_fields
from abacus.modules.assurance import group_contract as gc
from abacus.modules.assurance import group_fixtures as fx
from abacus.modules.identity.authz import _matrix

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
C = "/v1/audits/{work_item_id}/consolidations/{consolidation_id}"
E = "/v1/consolidations/{consolidation_id}/eliminations"
P = "/v1/proposed-entries/{entry_id}/elimination"
ROUTES: dict[tuple[str, str], str] = {
    ("post", "/v1/audits/{work_item_id}/consolidations"): "consolidation.edit",
    ("get", C): "consolidation.read",
    ("patch", C): "consolidation.edit",
    ("delete", C): "consolidation.edit",
    ("put", f"{C}/structure"): "consolidation.edit",
    ("post", f"{C}/structure/proposal"): "consolidation.edit",
    ("post", f"{C}/entities/{{entity_id}}/trial-balances"): "consolidation.edit",
    ("post", f"{C}/trial-balances/{{tb_id}}/not-needed"): "consolidation.edit",
    ("post", f"{C}/bulk-upload"): "consolidation.edit",
    ("post", f"{C}/pull-all"): "consolidation.edit",
    ("post", f"{C}/finalize"): "consolidation.finalize",
    ("post", f"{C}/lock"): "consolidation.lock",
    ("post", f"{C}/reopen"): "consolidation.lock",
    ("get", f"{C}/tb"): "consolidation.read",
    ("get", f"{C}/export.xlsx"): "consolidation.export",
    ("get", E): "elimination.read",
    ("post", E): "elimination.edit",
    ("patch", P): "elimination.edit",
    ("post", f"{P}/approve"): "elimination.approve",
    ("post", f"{E}/approve"): "elimination.approve",
    ("post", f"{P}/post"): "elimination.post",
    ("post", f"{P}/reject"): "elimination.approve",
    ("post", f"{E}/propose"): "elimination.propose_run",
}
CLIENT_ROLES = ("client_admin", "client_contributor", "third_party", "client_service")


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_action_and_404_and_501(method: str, path: str) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, operation["responses"]))


def test_every_field_is_classified() -> None:
    models = [
        v
        for v in vars(gc).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == gc.__name__
    ]
    assert len(models) > 30
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


def test_no_client_holds_a_consolidation_or_elimination_action() -> None:
    for action, cells in _matrix.ACTIONS.items():
        if action.split(".", 1)[0] in ("consolidation", "elimination"):
            assert all(cells.get(r, "deny") == "deny" for r in CLIENT_ROLES), action
            assert cells.get("agent", "deny") in ("deny", "task_scope"), action


def test_ac0_3_level_1_foots_50_760_000_and_every_column_nets_to_zero() -> None:
    consolidated = fx.consolidated(1)
    assert fx.total_assets(consolidated) == Decimal(50_760_000)
    assert fx.total_assets(fx.eliminations_column()) == Decimal(-48_640_000)
    assert fx.net_income(consolidated) == Decimal(3_500_000)
    assert sum(consolidated.values()) == 0
    for entity in fx.ENTITIES:
        assert sum(fx.entity_column(entity).values()) == 0, entity
    assert consolidated["Intercompany receivable"] == consolidated["Intercompany payable"] == 0


def test_ac0_3_eliminations_total_67_840_000_dr_eq_cr() -> None:
    assert fx.eliminations_total() == (Decimal(67_840_000), Decimal(67_840_000))
    for code, _level, _desc, lines in fx.ELIMINATIONS:
        assert sum(d for _c, d, _cr in lines) == sum(cr for _c, _d, cr in lines), code


def test_level_2_and_the_interim_debits_foot() -> None:
    level2 = fx.consolidated(2)
    assert fx.total_assets(level2) == Decimal(39_760_000)
    assert fx.net_income(level2) == Decimal(4_760_000)
    debits = [fx.interim_debits(e) for e in fx.ENTITIES]
    assert debits == [30_760_000, 20_000_000, 86_000_000, 42_400_000, 8_700_000]
    assert sum(debits) == Decimal(187_860_000)
    assert sum(fx.ACCOUNTS_BY_ENTITY.values()) == 244
    assert sum(fx.MAPPING_SPLIT.values()) == 238
