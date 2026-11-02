"""A-05-T21 (TASK-3023; A-05 §3 F4; DEC-2070): mode `ebp_attribute` and the census-to-HR checks.

Row acceptance: "Row 22's hire-date difference is marked Needs human with a computed no-effect
note, and no model input contains an unmasked SSN or DOB." The comparison is code's; the mode's
inputs carry keys and codes only, and are refused before any run if an SSN pattern or a
participant's date of birth slips in.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

import abacus.modules.assurance.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers
from abacus.modules.agents.api import ModeDocument, ModeInputs, ModePage
from abacus.modules.agents.section_sources import mode_mapping
from abacus.modules.assurance import ebp_attribute
from abacus.modules.assurance.ebp_attribute import (
    Check,
    UnmaskedModelInput,
    assert_masked,
    check_facts,
    hire_check,
)

DOB = date(1990, 6, 14)


def test_ac_row_22_hire_date_difference_is_needs_human_with_a_no_effect_note() -> None:
    # Census Mar 3, HR Mar 17: hire + 3 months gives Jun 3 / Jun 17, both enter Jul 1.
    check = hire_check("NW-1022", DOB, date(2021, 3, 3), date(2021, 3, 17))
    assert (check.result, check.note) == (
        "needs_human",
        "No effect on entry: both dates give the same entry date",
    )


def test_a_difference_that_moves_entry_is_needs_human_without_the_note() -> None:
    check = hire_check("NW-1008", DOB, date(2021, 3, 3), date(2021, 4, 3))
    assert (check.result, check.note) == ("needs_human", None)


def test_the_same_hire_date_matches() -> None:
    assert hire_check("NW-1001", DOB, date(2021, 3, 3), date(2021, 3, 3)).result == "match"


def test_ac_facts_carry_keys_and_codes_never_a_dob_or_ssn() -> None:
    checks = [
        Check("NW-1022", "hire_date", "needs_human", "No effect on entry: both dates give the "
              "same entry date"),
        Check("NW-1030", "ssn", "needs_human"),
        Check("NW-1001", "name", "match"),
    ]  # fmt: skip
    facts = dict(check_facts(checks))
    assert facts["attribute_checks_needing_a_person"] == {"t": "decimal", "v": "2"}
    assert facts["needs_human_NW-1030"] == {"t": "text", "v": "ssn"}
    assert "needs_human_NW-1001" not in facts
    assert_masked(ModeInputs(facts=tuple(facts.items())), [DOB])


@pytest.mark.parametrize("leak", ["SSN 900-45-6789", "ssn 900456789", "born 1990-06-14"])
def test_ac_an_input_with_an_ssn_or_a_dob_is_refused_before_any_run(leak: str) -> None:
    inputs = ModeInputs(
        documents=(ModeDocument(uuid.uuid4(), "HR record", (ModePage(1, f"Name: A. {leak}"),)),)
    )
    with pytest.raises(UnmaskedModelInput):
        assert_masked(inputs, [DOB])


def test_masked_tokens_pass() -> None:
    inputs = ModeInputs(
        documents=(
            ModeDocument(
                uuid.uuid4(), "HR record", (ModePage(1, "SSN •••-••-2207, DOB ••/••/••••"),)
            ),
        )
    )
    assert_masked(inputs, [DOB])


def test_the_mode_is_registered_with_its_mapping() -> None:
    assert mode_mapping(ebp_attribute.MODE) is ebp_attribute.attribute_inputs
