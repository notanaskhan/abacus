"""T-05-T26 (TASK-7518; T-05 §4.2 M5, F3; C9): the tax form-line taxonomy. Code suggests keys from
the prior year, then the firm's range rules, then its description rules, only from the version's
mappable keys; an approved mapper proposal is applied for the tax reviewer only; the contract
carries the taxonomy, the reference set version and each row's key.

Row acceptance: "Ridgeline maps 28 of 28 accounts after Samuel approves the one judgment, and an
agent cannot approve it."
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import tb_mapping_contract as c9
from abacus.modules.identity.api import RULES
from abacus.modules.ledger import tax_form_mapping as tfm
from abacus.modules.tax import entity_mapping

KEYS = frozenset({"L1a", "L9a", "L14", "K 18a", "L-1", "L-15"})


def test_prior_year_wins_then_range_then_description() -> None:
    accounts = [
        ("4000", "Rental income"),
        ("6100", "Repairs and maintenance"),
        ("7300", "Property tax"),
        ("4510-T", "Nondeductible expenses"),
        ("9999", "Suspense"),
    ]
    found = tfm.suggest_form_lines(
        accounts,
        keys=KEYS,
        prior={"4000": "L1a", "4510-T": "K 18a", "7300": "RETIRED"},
        ranges=[tfm.RangeRule("6000", "6999", "L9a"), tfm.RangeRule("7000", "7999", "L14")],
        descriptions=[tfm.DescriptionRule("property tax", "L-15")],
    )
    assert [(s.account_code, s.form_line_key, s.method, s.confidence) for s in found] == [
        ("4000", "L1a", "prior_year", "high"),
        ("6100", "L9a", "range", "medium"),
        ("7300", "L14", "range", "medium"),  # a retired prior key falls through
        ("4510-T", "K 18a", "prior_year", "high"),
        ("9999", None, None, None),
    ]


def test_a_rule_naming_a_key_outside_the_version_is_never_used() -> None:
    found = tfm.suggest_form_lines(
        [("6100", "Repairs")],
        keys=KEYS,
        prior={},
        ranges=[tfm.RangeRule("6000", "6999", "NOT A KEY")],
        descriptions=[tfm.DescriptionRule("repairs", "L9a")],
    )
    assert (found[0].form_line_key, found[0].method) == ("L9a", "description")


def test_unmapped_counts_what_has_no_key() -> None:
    codes = [f"{n}" for n in range(1000, 1028)]
    rows = {c: "L1a" for c in codes[:27]}
    assert tfm.unmapped_form_lines(codes, rows) == 1
    rows[codes[27]] = "L9a"  # Samuel approves the one judgment
    assert tfm.unmapped_form_lines(codes, rows) == 0


def test_a_key_outside_the_version_is_refused() -> None:
    async def run() -> None:
        await tfm.record_form_line(
            SimpleNamespace(),  # type: ignore[arg-type] -- refused before any write
            tenant_id=uuid.uuid4(),
            mapping_set_id=uuid.uuid4(),
            engagement_id=uuid.uuid4(),
            account_code="6100",
            form_line_key="L99",
            keys=KEYS,
            edited_by=uuid.uuid4(),
        )

    with pytest.raises(tfm.FormLineKeyUnknown) as refused:
        asyncio.run(run())
    assert refused.value.code == "form_line_key_unknown"


def test_only_the_tax_reviewer_approves_a_mapping() -> None:
    rule = RULES["tax_mapping.approve"]
    assert set(rule.function_in) == {"detail_reviewer", "manager_reviewer", "signer"}
    for principal in ("agent", "system", "client_admin", "client_contributor"):
        assert rule.decisions.get(principal) != "allow", principal


@pytest.mark.parametrize(
    ("key", "code"), [("account:4510-T", "4510-T"), ("account: ", None), ("line:L1a", None)]
)
def test_rows_name_their_account(key: str, code: str | None) -> None:
    assert entity_mapping.account_of(key) == code


def _row(code: str, key: str, target: uuid.UUID) -> Any:  # noqa: ANN401 -- a proposal row stand-in
    return SimpleNamespace(
        field_ref={"field_key": f"account:{code}", "target_id": str(target)},
        after={"t": "text", "v": key},
    )


def test_an_approval_without_the_reviewer_function_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = uuid.uuid4()

    @asynccontextmanager
    async def session(_tenant: object):  # noqa: ANN202
        yield SimpleNamespace()

    async def rows(_s: object, _p: object) -> tuple[uuid.UUID, list[Any]]:
        return uuid.uuid4(), [_row("6100", "L9a", target)]

    async def approver(_s: object, _p: object) -> uuid.UUID:
        return uuid.uuid4()

    async def resource(_tenant: object, _engagement: object) -> Any:  # noqa: ANN401
        return SimpleNamespace(work_item_id=None)

    async def preparer_only(*_: object) -> bool:
        return False

    @asynccontextmanager
    async def no_write(_tenant: object):  # noqa: ANN202
        raise AssertionError("nothing is written")
        yield

    monkeypatch.setattr(entity_mapping, "tenant_session", session)
    monkeypatch.setattr(entity_mapping, "approved_proposal_rows", rows)
    monkeypatch.setattr(entity_mapping, "proposal_approver", approver)
    monkeypatch.setattr(entity_mapping, "engagement_resource", resource)
    monkeypatch.setattr(entity_mapping, "replace", lambda r, **_: r)
    monkeypatch.setattr(entity_mapping, "member_could", preparer_only)
    monkeypatch.setattr(entity_mapping, "uow", no_write)
    tenant = TenantContext(uuid.uuid4(), "system", "proposal:x")
    with pytest.raises(entity_mapping.MappingLevelNotPermitted) as refused:
        asyncio.run(entity_mapping.apply_account_mapping_proposal(tenant, uuid.uuid4()))
    assert refused.value.code == "level_not_permitted"


def test_the_contract_carries_the_taxonomy() -> None:
    assert {"taxonomy_kind", "reference_set_version_id"} <= set(
        c9.MappingSetSummaryOut.model_fields
    )
    assert "form_line_key" in c9.AccountMappingOut.model_fields
    assert c9.MappingSetSummaryOut.model_fields["taxonomy_kind"].default == "fs_line"
