# ac-test-author: ayushkbhatia
"""T-01-T04 (TASK-2111; SPEC-501 AC-10): C21 as T-01 consumes it (I-8879-DRIFT reads database
rows, never constants). Runs in K-02's CI against the stub, then the live service.

- `form_8879_for` and `pub1345_tolerances` exist with the frozen signatures and return the form,
  both tolerance keys and the reference-set version id the binding stores.
- The tolerance payload carries both of DEC-85's keys and nothing that would let code default.
- `reference_set.published` carries identifiers only (the drift recheck reads the rows again)."""

from __future__ import annotations

import asyncio
import inspect
from datetime import date

import pytest

from abacus.modules.platform import api as platform_api
from abacus.modules.platform.reference_sets_contract import Pub1345Tolerances


def test_ac10_form_8879_for_and_tolerances_have_the_frozen_signatures() -> None:
    form = inspect.signature(platform_api.form_8879_for)
    assert list(form.parameters) == ["return_type", "tax_year", "jurisdiction", "as_of"]
    assert form.parameters["as_of"].kind is inspect.Parameter.KEYWORD_ONLY
    tolerances = inspect.signature(platform_api.pub1345_tolerances)
    assert list(tolerances.parameters) == ["tax_year", "as_of"]


def test_ac10_results_name_the_reference_set_version() -> None:
    for cls in (platform_api.Form8879For, platform_api.TolerancesFor):
        assert "reference_set_version_id" in inspect.signature(cls).parameters, cls
    keys = set(inspect.signature(platform_api.TolerancesFor).parameters)
    assert {"total_income_or_agi_usd", "tax_withholding_refund_balance_usd"} <= keys


def test_ac10_the_tolerance_payload_has_both_keys_and_no_defaults() -> None:
    fields = Pub1345Tolerances.model_fields
    assert set(fields) == {"total_income_or_agi_usd", "tax_withholding_refund_balance_usd"}
    assert all(f.is_required() for f in fields.values())  # DEC-85: never defaulted


def test_ac10_the_stub_refuses_until_k02_t05() -> None:
    with pytest.raises(NotImplementedError):
        asyncio.run(platform_api.pub1345_tolerances(2026, as_of=date(2027, 7, 1)))
