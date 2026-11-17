"""C12 v1 consumer tests (T-06-T06; SPEC-702 AC-27 to AC-31; DEC-5515) for both shapes: AUD-38
(audit_release, Granite Peak FY2026) and CLS-12 (close_lock, Copperleaf, C-02). The suite fails if
any account choice lacks a source, if a close_lock payload omits its locked-close reference, if the
fixtures stop footing, or if an operation loses its action or its 501. The fixture half is
`apps/web/src/fixtures/contracts/c12-tb-handoff.contract.test.ts`."""

from __future__ import annotations

import json
import uuid
from typing import cast

import pytest
from pydantic import ValidationError

from abacus.api.export_openapi import document
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.ledger.tb_handoff_contract import (
    TbHandoffLandingOut,
    TbHandoffPreviewOut,
    TbHandoffReviewAccountOut,
)
from abacus_tools.synthetic.scenarios.brightwater_hale import tb_handoff_slice as seed

Json = dict[str, object]
PATHS = cast(dict[str, dict[str, Json]], json.loads(document())["paths"])
E = "/v1/engagements/{engagement_id}"
OPERATIONS = {
    ("get", f"{E}/tax-handoff/targets"): "tb_handoff.preview",
    ("get", f"{E}/tax-handoff/preview"): "tb_handoff.preview",
    ("post", f"{E}/tax-handoffs"): "tb_handoff.create",
    ("get", "/v1/tb-handoffs/{handoff_id}"): "tb_handoff.read",
    ("get", "/v1/tb-handoffs/{handoff_id}/mappings"): "tb_handoff.read",
    ("get", "/v1/tax-returns/{return_id}/handoff"): "tax_return.read",
}


def test_aud38_the_preview_foots_128_accounts_and_2_350_000() -> None:
    preview = seed.granite_peak_preview(chosen=True)
    counts = preview.counts
    assert counts.mapped + counts.suggested + counts.review == counts.total == 128
    income = preview.book_income
    assert income.pretax - income.income_tax_expense == income.net_income
    assert str(income.net_income) == "2350000.00"
    opening, additions, depreciation = seed.PPE
    assert opening + additions - depreciation == 6_380_000
    assert len(preview.review_accounts) == counts.review


def test_aud38_b_needs_review_until_every_review_account_is_chosen() -> None:
    first = seed.granite_peak_preview(chosen=False)
    assert first.status == "needs_review"
    assert all(a.choice is None for a in first.review_accounts)
    ready = seed.granite_peak_preview(chosen=True)
    assert ready.status == "ready" and all(a.choice == "send_blank" for a in ready.review_accounts)
    assert seed.granite_peak_not_available().status == "not_available"


def test_every_account_choice_names_its_source() -> None:
    for account in seed.granite_peak_preview(chosen=True).review_accounts:
        assert account.source in ("tb_mapper", "firm_mapping", "person")
    with pytest.raises(ValidationError):
        TbHandoffReviewAccountOut.model_validate(
            {"account_ref": "2255", "account_name": "x", "balance": "1.00", "choice": "send_blank"}
        )


def test_a_close_lock_payload_names_its_locked_close() -> None:
    landing = seed.copperleaf_close_lock_landing()
    assert landing.source_kind == "close_lock" and landing.locked_close_id is not None
    with pytest.raises(ValidationError):
        TbHandoffLandingOut.model_validate({"source_kind": "close_lock"})
    preview = seed.granite_peak_preview(chosen=True).model_dump()
    with pytest.raises(ValidationError):
        TbHandoffPreviewOut.model_validate({**preview, "source_kind": "close_lock"})
    with pytest.raises(ValidationError):  # and only a close_lock names one
        TbHandoffPreviewOut.model_validate({**preview, "locked_close_id": str(uuid.uuid4())})


@pytest.mark.parametrize(("op", "action"), sorted(OPERATIONS.items()), ids=str)
def test_every_operation_is_declared_with_its_action_and_501(
    op: tuple[str, str], action: str
) -> None:
    method, path = op
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == action
    assert "501" in cast(Json, operation["responses"])


def test_only_a_live_partner_or_manager_hands_off_from_a_released_source() -> None:
    rule = RULES["tb_handoff.create"]
    assert rule.tb_handoff_source_released and rule.same_client
    assert {r for r, d in rule.decisions.items() if d != "deny"} == {
        "engagement_partner",
        "manager",
    }
    assert rule.decisions.get("agent") == "deny" and rule.decisions.get("system") == "deny"
