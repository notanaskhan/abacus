"""T-08-T20 (TASK-8915; SPEC-710 AC-12, AC-15, AC-20; FD-1; HOME-03; DEC-5917; amber): the
filing-deadline providers.

Row acceptance: "HOME-01 and HOME-03 show the same dates for Daniel Reyes, and the Thornbury 706
reads Nov 2, 2026 with Form 4768 to May 3, 2027." Here: every one of the read model's eleven
source kinds has its owner's provider registered once the API is imported; the 706's dates come
from the estate due chip (date of death Feb 2, 2026) with the 4768 shown; the 65-day window,
Form 8971 and Form 5500 dates are code's; the recompute's hash moves only with a fact's inputs;
and HOME-01's pane reads the same `filing_deadlines` rows HOME-03 does (the integration test
proves the dates on the migrated database).
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import replace
from datetime import date
from uuid import uuid4

from abacus.modules.assurance.deadline_sources import form_5500_due
from abacus.modules.platform.api import FilingDeadlineFact
from abacus.modules.platform.filing_deadline_sources import SOURCE_KINDS
from abacus.modules.practice import deadlines_service as svc
from abacus.modules.practice import home
from abacus.modules.tax import deadline_sources as tax_sources
from abacus.modules.tax.estate_service import due_chip


def test_every_source_kind_has_its_owners_provider() -> None:
    import abacus.api as composition_root  # the composition root imports every module's api
    from abacus.modules.platform.api import filing_deadline_source, filing_deadline_source_kinds

    assert composition_root
    assert set(filing_deadline_source_kinds()) == SOURCE_KINDS
    owners = {k: filing_deadline_source(k).__module__ for k in SOURCE_KINDS}
    assert owners["tax_return"] == "abacus.modules.tax.deadline_sources"
    assert owners["close"] == "abacus.modules.closes.deadline_sources"
    assert owners["notice_response"] == "abacus.modules.notices.deadline_sources"
    assert (
        owners["form_5500"]
        == owners["assurance_report"]
        == ("abacus.modules.assurance.deadline_sources")
    )


def test_the_thornbury_706_reads_nov_2_with_form_4768_to_may_3() -> None:
    chip = asyncio.run(due_chip(2026, date(2026, 2, 2)))
    assert (chip.due_on, chip.extension_to) == (date(2026, 11, 2), date(2027, 5, 3))
    assert tax_sources.EXTENSION_FORM["706"] == "4768"
    assert tax_sources.EXTENSION_FORM["990"] == "8868"
    assert chip.form_8971_due_on == date(2026, 12, 2)  # Form 8971: the 706 due + 30 days


def test_statutory_windows_by_code() -> None:
    assert tax_sources.sixty_five_day_end(2025) == date(2026, 3, 6)
    assert tax_sources.sixty_five_day_end(2027) == date(2028, 3, 5)  # 2028 is a leap year
    assert form_5500_due(date(2025, 12, 31)) == (date(2026, 7, 31), date(2026, 10, 15))
    # Plan year ending Jun 30, 2026: due Jan 31, 2027 (a Sunday, rolled to Monday Feb 1); the
    # 5558 date Apr 15, 2027 (a Thursday).
    assert form_5500_due(date(2026, 6, 30)) == (date(2027, 2, 1), date(2027, 4, 15))


def _fact() -> FilingDeadlineFact:
    return FilingDeadlineFact(
        source_kind="tax_return", source_ref=str(uuid4()), filing_label="Form 706 · 2026",
        client_id=uuid4(), office_id=None, service_line="tax",
        original_due_on=date(2026, 11, 2), due_on=date(2026, 11, 2), stage_code="in_progress",
        extension_form="4768", extended_due_on=date(2027, 5, 3),
    )  # fmt: skip


def test_the_recompute_hash_moves_only_with_the_inputs() -> None:
    fact = _fact()
    assert svc.inputs_hash(fact) == svc.inputs_hash(replace(fact))
    assert svc.inputs_hash(fact) != svc.inputs_hash(replace(fact, due_on=date(2027, 5, 3)))
    assert svc.inputs_hash(fact) != svc.inputs_hash(replace(fact, done=True))
    assert svc.inputs_hash(fact) != svc.inputs_hash(replace(fact, owner_user_ids=(uuid4(),)))


def test_the_recompute_asks_every_registered_kind_not_tax_directly() -> None:
    source = inspect.getsource(svc.recompute)
    assert "filing_deadline_source_kinds()" in source
    assert "return_deadlines" not in inspect.getsource(svc)


def test_home_01_reads_the_filing_deadlines_rows() -> None:
    source = inspect.getsource(home)
    assert "deadline_rows(" in source and "person=ctx.user_id" in source
    assert "PRACTICE_FILING_DEADLINES" in source
    row = home.DeadlineRow(
        uuid4(), date(2026, 11, 2), "Estate of Margaret Thornbury", "Form 706 · 2026",
        "in_progress", home.risk_of(date(2026, 11, 2), date(2026, 10, 30)), "tax_return",
    )  # fmt: skip
    assert row.risk == "due_soon"
