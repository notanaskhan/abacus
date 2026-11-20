"""T-06-T37 (TASK-8828; T-06 F7; TAX-11; SPEC-702 AC-33; DEC-5830): the form-preview diagnostics
blocker of final approval (red).

Row acceptance: "With a blocking diagnostic open the POST answers 409 blocking_diagnostics, and the
eligibility read lists the reason TAX-11 shows on the disabled button."
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.tax import approval
from abacus.modules.tax import form_preview_blockers as fp
from abacus.modules.tax.entity_depth_errors import BlockingDiagnostics

V = dict[str, dict[str, object]]


def _d(v: str) -> dict[str, object]:
    return {"t": "decimal", "v": v}


def _book() -> V:
    """Sheet 03 (L1 assets 7,466,200; L17 liabilities -600,000) and sheet 05 (Item L)."""
    return {
        "03!A2": {"t": "text", "v": "L1"}, "03!C2": _d("7466200"),
        "03!A3": {"t": "text", "v": "L17"}, "03!C3": _d("-600000"),
        "03!A4": {"t": "text", "v": "8825 Rents"}, "03!C4": _d("-900000"),
        "05!A2": {"t": "text", "v": "Meera Shah"}, "05!F2": _d("3433100"),
        "05!A3": {"t": "text", "v": "Owen Calder"}, "05!F3": _d("3433100"),
    }  # fmt: skip


def test_line_21_is_assets_less_liabilities() -> None:
    assert fp.schedule_l_line_21(_book()) == Decimal("6866200")
    assert fp.item_l_total(_book()) == Decimal("6866200")
    assert fp.item_l_off(_book()) == Decimal(0)


def test_off_by_the_m2_difference() -> None:
    v = _book()
    v["05!F3"] = _d("3439300")  # +6,200
    assert fp.item_l_off(v) == Decimal("6200")


def test_nothing_to_compare_is_silent() -> None:
    assert fp.item_l_off({}) is None
    assert fp.item_l_off({"05!A2": {"t": "text", "v": "A"}, "05!F2": _d("1")}) is None


class _Session:
    def __init__(self, ids: list[uuid.UUID]) -> None:
        self.ids = ids

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, stmt: object, params: object) -> list[SimpleNamespace]:
        assert "severity = 'error'" in str(stmt)
        return [SimpleNamespace(id=i) for i in self.ids]


def _patch(monkeypatch: pytest.MonkeyPatch, *, errors: int, values: V, cards: int) -> None:
    from abacus.modules.review import api as review_api
    from abacus.modules.tax import entity_schedules

    ids = [uuid.uuid4() for _ in range(errors)]

    async def wb(*_a: object) -> V:
        return values

    async def awaiting(*_a: object) -> list[SimpleNamespace]:
        return [SimpleNamespace(card_id=uuid.uuid4()) for _ in range(cards)]

    monkeypatch.setattr(fp, "tenant_session", lambda _t: _Session(ids))  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType] -- a monkeypatched double
    monkeypatch.setattr(entity_schedules, "workbook_values", wb)
    monkeypatch.setattr(review_api, "awaiting_cards", awaiting)


def _kinds(monkeypatch: pytest.MonkeyPatch, **kw: object) -> list[str]:
    _patch(monkeypatch, **kw)  # type: ignore[arg-type] -- the test's keyword set
    tenant = TenantContext(uuid.uuid4(), "human", "t")
    return [b.kind for b in asyncio.run(fp.form_preview_blockers(tenant, uuid.uuid4()))]


def test_ac_each_diagnostic_blocks_with_words(monkeypatch: pytest.MonkeyPatch) -> None:
    v = _book()
    v["05!F3"] = _d("3439300")
    kinds = _kinds(monkeypatch, errors=2, values=v, cards=1)
    assert kinds == [fp.ENGINE_ERROR, fp.ENGINE_ERROR, fp.ITEM_L_OFF, fp.STATEMENT_754]
    for kind in {*kinds, fp.KIND}:
        assert approval.blocker_words(kind) != "A check blocks final approval."


def test_ac_clear_return_adds_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _kinds(monkeypatch, errors=0, values=_book(), cards=0) == []


def _approve(monkeypatch: pytest.MonkeyPatch, blockers: list[approval.Blocker]) -> None:
    signer = uuid.uuid4()
    checkpoint = uuid.uuid4()
    found = approval.Eligibility(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), signer, checkpoint, "abc", blockers
    )

    async def eligibility(*_a: object) -> approval.Eligibility:
        return found

    async def resource(*_a: object) -> object:
        return object()

    async def authorise(*_a: object) -> None:
        return None

    monkeypatch.setattr(approval, "eligibility", eligibility)
    monkeypatch.setattr(approval, "_resource", resource)
    monkeypatch.setattr(approval, "authorise", authorise)
    ctx = SimpleNamespace(
        client=False, is_support=False, user_id=signer,
        tenant=TenantContext(uuid.uuid4(), "human", "u"),
    )  # fmt: skip
    asyncio.run(approval.approve(ctx, found.return_id, checkpoint, "sha256:abc"))  # type: ignore[arg-type] -- a context double


def test_ac_post_answers_409_blocking_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(BlockingDiagnostics) as caught:
        _approve(monkeypatch, [approval.Blocker("draft_k1"), approval.Blocker(fp.ENGINE_ERROR)])
    assert caught.value.code == "blocking_diagnostics"


def test_other_blockers_keep_final_approval_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(approval.FinalApprovalBlocked):
        _approve(monkeypatch, [approval.Blocker("draft_k1")])


def test_failed_provider_answers_blocking_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(BlockingDiagnostics):
        _approve(monkeypatch, [approval.Blocker(fp.KIND)])


def test_ac_provider_registered() -> None:

    assert fp.KIND in approval._PROVIDERS  # pyright: ignore[reportPrivateUsage] -- the registry is the thing tested
