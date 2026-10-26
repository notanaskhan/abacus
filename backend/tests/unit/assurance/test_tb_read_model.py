"""A-02-T10 (TASK-1336; DEC-440) without a database: the view by layer refuses a layer that does
not balance (`require_balanced`, AC-17) before anything else is read, and the area rules are read
from the engagement's own methodology version on every call, with no cache."""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from abacus.kernel._statuses import TrialBalanceLayerStatus
from abacus.kernel.db import TenantContext
from abacus.modules.assurance import tb_read_model
from abacus.modules.identity.api import AuthContext
from abacus.modules.ledger.api import LayerUnbalanced, TbLine

D = Decimal


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )


def _ref(version: uuid.UUID | None) -> SimpleNamespace:
    return SimpleNamespace(
        methodology_version_id=version, client_entity_id=uuid.uuid4(), resource=lambda: "eng"
    )


async def test_ac17_an_unbalanced_layer_is_refused_before_the_view_is_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lines = [
        TbLine("1000", "Cash", None, D("100.00"), D("0.00"), D("100.00"), None, None, None),
        TbLine("2000", "AP", None, D("0.00"), D("90.00"), D("-90.00"), None, None, None),
    ]

    async def gate(_ctx: AuthContext, _eid: uuid.UUID) -> object:
        return _ref(None)

    async def view(*_args: object) -> object:
        return SimpleNamespace(lines=lines)

    async def never(*_args: object) -> object:
        raise AssertionError("nothing is read after the balance check fails")

    monkeypatch.setattr(tb_read_model, "_gate", gate)
    monkeypatch.setattr(tb_read_model, "trial_balance_view", view)
    monkeypatch.setattr(tb_read_model, "checks_for", never)
    monkeypatch.setattr(tb_read_model, "engagement_team", never)
    with pytest.raises(LayerUnbalanced) as refused:
        await tb_read_model.layer_view(
            _ctx(), uuid.uuid4(), uuid.uuid4(), TrialBalanceLayerStatus.UNADJUSTED, None
        )
    assert refused.value.facts == {"layer": "unadjusted", "difference": "10.00"}


async def test_area_rules_are_read_each_call_from_the_engagements_own_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = uuid.uuid4()
    reads: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def detail(tenant: TenantContext, version_id: uuid.UUID) -> object:
        reads.append((tenant.tenant_id, version_id))
        return SimpleNamespace(
            summary=SimpleNamespace(version_id=version_id),
            areas=(SimpleNamespace(code="CASH", name="Cash"),),
            rules=(SimpleNamespace(area_code="CASH", account_from="1000", account_to="1099"),),
        )

    monkeypatch.setattr(tb_read_model, "version_detail", detail)
    ctx = _ctx()
    first = await tb_read_model.area_rules(ctx, _ref(version))  # type: ignore[arg-type]  # a stand-in EngagementRef
    second = await tb_read_model.area_rules(ctx, _ref(version))  # type: ignore[arg-type]  # a stand-in EngagementRef
    assert first == second and first[0].area == "Cash"
    assert reads == [(ctx.tenant_id, version)] * 2  # no cache: read in the caller's tenant
    assert await tb_read_model.area_rules(ctx, _ref(None)) == ()  # type: ignore[arg-type]  # a stand-in EngagementRef


def test_the_module_keeps_no_rule_cache() -> None:
    """Nothing module-level may hold rules between calls (the #417 review's binding)."""
    held = [
        name
        for name, value in vars(tb_read_model).items()
        if isinstance(value, dict | list | set) and not name.startswith("__")
    ]
    assert held == []
