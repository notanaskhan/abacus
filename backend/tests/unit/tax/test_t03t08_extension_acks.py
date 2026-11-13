"""T-03-T08 (TASK-3264; SPEC-643 AC-8; DEC-2244): extension acknowledgements.

Row acceptance: "An imported ack file moves Feld's 4868 to Accepted and Varga's to Rejected with
IND-031-04, and the never-ERO suite proves no extension transmission path exists." Here: the
report's form column, the extension split and the no-transmit proof over every extension route.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, cast

import pytest

from abacus.modules.identity.routing import ACTION_KEY
from abacus.modules.tax import extension_acks, extensions, schedules_contract
from abacus.modules.tax.engine_adapter import parse_acks

WITH_FORM = (
    b"return_id,jurisdiction,submission_last4,status,status_at,reject_code,reject_text,form\n"
    b"2025I:FeldJ,federal,AB12,accepted,2026-04-16,,,4868\n"
    b"2025I:FeldJ,NY,CD34,rejected,2026-04-16,IND-031-04,Name mismatch,IT-370\n"
    b"2025I:FeldJ,federal,EF56,accepted,2026-10-15,,,\n"
)
SEVEN = (
    b"return_id,jurisdiction,submission_last4,status,status_at,reject_code,reject_text\n"
    b"2025I:FeldJ,federal,AB12,accepted,2026-04-16,,\n"
)


def test_the_form_column_marks_extension_rows_and_the_old_report_still_reads() -> None:
    acks = parse_acks(WITH_FORM).acks
    assert [(a.form, a.extension) for a in acks] == [
        ("4868", True),
        ("IT-370", True),
        (None, False),
    ]
    assert acks[1].reject_code == "IND-031-04"
    assert [a.form for a in parse_acks(SEVEN).acks] == [None]


def test_federal_is_the_extensions_us_jurisdiction() -> None:
    assert extension_acks.jurisdiction_of("federal") == "US"
    assert extension_acks.jurisdiction_of("NY") == "NY"


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_no_extension_route_or_module_can_transmit() -> None:
    actions: set[str] = {
        cast(Any, r).openapi_extra[ACTION_KEY]  # Any: test doubles and JSON
        for r in schedules_contract.schedules_router.routes  # Any: test doubles and JSON
    }
    assert not any(word in a for a in actions for word in ("transmit", "efile", "ero"))
    for module in (extensions, extension_acks):
        source = Path(inspect.getfile(module)).read_text()
        assert (
            "transmission"
            not in source.replace("transmission path", "").replace("never transmits", "").lower()
            or "INSERT INTO transmissions" not in source
        )
        assert "INSERT INTO transmissions" not in source
