"""A-01-T08, T09 rules that need no database (SPEC-330 AC-20, AC-22, AC-23; DEC-311, DEC-312)."""

from __future__ import annotations

from datetime import date

import pytest

from abacus.modules.assurance import api as assurance_api
from abacus.modules.assurance import index, providers, sections

assert assurance_api.ROUTERS  # registers A-01's rows, tags and segments

E0 = date(2026, 9, 14)


@pytest.mark.parametrize(
    ("due", "tone"),
    [
        (None, None),
        (date(2026, 9, 13), "past_due"),
        (date(2026, 9, 18), "within_7_days"),  # AUD-01: Sep 18 red
        (date(2026, 9, 21), "within_30_days"),  # seven days left is amber (DEC-263)
        (date(2026, 10, 14), "within_30_days"),
        (date(2026, 10, 15), "later"),
    ],
)
def test_ac20_report_due_tone(due: date | None, tone: str | None) -> None:
    assert index.due_tone(due, E0) == tone


def test_ac23_texts_are_built_by_code() -> None:
    assert providers.initials("Margaret Okonkwo") == "MO"
    assert index.initials("Hannah Leclerc") == "HL"
    assert f"Letter sent {providers.month_day(date(2026, 9, 8))}" == "Letter sent Sep 8"


def test_ac23_a01_registers_its_overview_rows_in_order_and_three_metadata_tags() -> None:
    overview = [s for s in sections.registered_sections() if s.band == "overview"]
    assert [(s.key, s.label, s.route, s.link) for s in overview] == [
        ("client", "Client", "CLI-02", "live"),
        ("methodology", "Methodology", "KNW-03", "planned"),
        ("standards_set", "Standards set", "KNW-04", "planned"),
        ("source_documents", "Source Documents", "AUD-03", "planned"),
        ("team", "Team", "ENG-05", "planned"),
        ("activity", "Activity", "AUD-29", "planned"),
    ]
    metadata = {t.name for t in sections.registered_index_tags(metadata_only=True)}
    assert {"letter_sent", "eqr", "no_report"} <= metadata


def test_ac22_a_taken_section_key_refuses_a_different_title() -> None:
    with pytest.raises(ValueError, match="already registered"):
        sections.register_audit_section(
            "client", "overview", 0, "CLI-02", providers.client_row, title="Customer", link="live"
        )
    # The same registration again (a reloaded module) replaces itself.
    sections.register_audit_section(
        "client", "overview", 0, "CLI-02", providers.client_row, title="Client", link="live"
    )


async def test_ac23_no_run_provider_means_no_run() -> None:
    from uuid import uuid4

    from abacus.kernel.db import TenantContext

    tenant = TenantContext(uuid4(), "human", str(uuid4()))
    assert await sections.run_summaries(tenant, [uuid4()]) == {}
