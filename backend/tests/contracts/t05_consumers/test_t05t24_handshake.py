"""T-05-T24 (TASK-7408; T-05 §8 handshake step 1; DEC-4407): T-05's consumer view of the three
red-service providers it reads, against their stubs.

- **C8** (A-06's `adjustments`; T-05-T25 extends it): the entry and adjusted-TB fields TXP-02
  reads, the `tje` kind with "TJE-n" numbering, and (pending T-05-T25) the `atb`, `tje` and `ttb`
  layers and the line's `account_scope` (`book` or `tax_only`, so 4510-T exists only in tax).
- **C9** (`ledger`; T-05-T26 extends it): the mapping set and row fields the workbook reads, and
  (pending T-05-T26) `taxonomy_kind` (`fs_line`, `tax_form_line`), the C21 reference set version
  and each row's `form_line_key`.
- **C6 v2** (P-10's runtime): `register_run_step` and the workbook run's start answer, and
  (pending T-05-T32) the ten registered run-step kinds of the workbook run's plan provider.

What a provider does not carry yet is pinned as a strict expected failure: it runs red now and,
once the provider lands, XPASS fails the suite until the mark is removed, so the handshake turns
green only when the implementation does (the row's acceptance; never a skip).
"""

from __future__ import annotations

import json
from typing import Final, cast, get_args

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.modules.adjustments import contract as c8
from abacus.modules.adjustments.contract import EntryKind, Layer
from abacus.modules.agents.api import register_run_step
from abacus.modules.assurance import tb_mapping_contract as c9
from abacus.modules.tax import workbook_contract as wb

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
PENDING_T25: Final = "T-05-T25 (C8 tax layers) has not landed"
PENDING_T26: Final = "T-05-T26 (C9 tax form-line taxonomy) has not landed"
PENDING_T32: Final = "T-05-T32 (the workbook run's step handlers) has not landed"
RUN_STEPS: Final = (
    "import_trial_balance",
    "map_lines",
    "depreciation_register",
    "bonus_eligibility",
    "contributions_distributions",
    "interim_closing_706d",
    "capital_m2",
    "apportionment_ptet",
    "federal_k1s",
    "state_k1s_k3s",
)


def _props(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields)


# --- C8 ------------------------------------------------------------------------------------------


def test_c8_entries_carry_what_txp02s_drawer_reads() -> None:
    assert {
        "id",
        "ref",
        "kind",
        "description",
        "amount",
        "status",
        "lines",
        "approval_label",
        "version",
    } <= _props(c8.EntryOut)
    assert {"account_code", "account_name", "debit", "credit"} <= _props(c8.LineOut)
    assert {"layer", "lines", "pending_entries"} <= _props(c8.AdjustedTbOut)
    assert {"account_code", "account_name", "unadjusted", "aje", "rje", "final"} <= _props(
        c8.AdjustedLineOut
    )


def test_c8_has_the_tje_kind_and_its_numbering() -> None:
    from abacus.modules.adjustments.entries import _PREFIX  # pyright: ignore[reportPrivateUsage]

    assert "tje" in get_args(EntryKind)
    assert _PREFIX["tje"] == "TJE"


@pytest.mark.xfail(reason=PENDING_T25, strict=True)
def test_c8_the_adjusted_tb_has_the_tax_layers() -> None:
    assert {"atb", "tje", "ttb"} <= set(get_args(Layer))
    assert {"atb", "tje", "ttb"} <= _props(c8.AdjustedLineOut)


@pytest.mark.xfail(reason=PENDING_T25, strict=True)
def test_c8_a_line_names_its_account_scope() -> None:
    assert "account_scope" in _props(c8.LineOut)
    scope = c8.LineOut.model_fields["account_scope"].annotation
    assert "tax_only" in str(scope)


# --- C9 ------------------------------------------------------------------------------------------


def test_c9_the_mapping_set_and_rows_carry_what_the_workbook_reads() -> None:
    assert {"summary", "rows", "subtotals", "allowed_actions"} <= _props(c9.MappingSetOut)
    assert {"account_code", "account_name", "state", "method", "confidence"} <= _props(
        c9.AccountMappingOut
    )


@pytest.mark.xfail(reason=PENDING_T26, strict=True)
def test_c9_a_mapping_set_names_its_taxonomy_and_reference_set() -> None:
    props = _props(c9.MappingSetSummaryOut)
    assert {"taxonomy_kind", "reference_set_version_id"} <= props
    kinds = str(c9.MappingSetSummaryOut.model_fields["taxonomy_kind"].annotation)
    assert "tax_form_line" in kinds and "fs_line" in kinds


@pytest.mark.xfail(reason=PENDING_T26, strict=True)
def test_c9_a_row_maps_to_a_form_line_key() -> None:
    assert "form_line_key" in _props(c9.AccountMappingOut)


# --- C6 v2 ---------------------------------------------------------------------------------------


def test_c6_v2_the_run_step_slot_and_the_runs_start_answer() -> None:
    assert callable(register_run_step)
    with pytest.raises(ValueError, match="snake_case"):
        register_run_step("Not Snake", lambda *_: None)  # type: ignore[arg-type]
    assert {"run_id", "run_no"} <= _props(wb.WorkbookRunAcceptedOut)
    start = PATHS["/v1/tax-returns/{return_id}/workbook-runs"]["post"]
    assert "202" in cast(Json, start["responses"])


@pytest.mark.xfail(reason=PENDING_T32, strict=True)
def test_c6_v2_the_workbook_runs_ten_steps_are_registered() -> None:
    from abacus.modules.agents.engagement_run import run_step_handler

    missing = [k for k in RUN_STEPS if run_step_handler(f"run_step.{k}") is None]
    assert missing == []
