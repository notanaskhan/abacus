"""A-03-T16 (TASK-2715; A-03 §5.4; DEC-1659, DEC-1766): the scenario's A-03 populations, built by
inverse construction, draw the design for its seeds with the frozen 2.3 sampler.

Census v2 (412) and seed 0x5E2A91 give AUD-11 a's 25 participants in order; the disbursements
(1,912, $38,640,200.00) and seed 0x7C31B4 give AUD-11 f's 24 + 16 = 40 payments, $3,698,700.00;
census v1 (409) is short of the register by $182,300.00; the distributions are 64.
"""

from __future__ import annotations

import io
from decimal import Decimal

from openpyxl import load_workbook

from abacus.modules.sampling.compute import canonical, sampler
from abacus_tools.synthetic.scenarios.brightwater_hale import sampling_content as content


def test_ac_census_v2_and_its_seed_draw_the_designed_participants_in_order() -> None:
    rows = content.census()
    assert len(rows) == 412
    assert sum((r.compensation for r in rows), Decimal(0)) == Decimal("14560000.00")
    draw = sampler("2.3").select(
        canonical(content.census_records(rows)),
        "attribute_statistical",
        seed=content.SEEDS["northwind-participants-v2"],
        size=25,
    )
    by_key = {r.row_key: (r.name, r.census_id) for r in rows}
    assert [by_key[i.record_key] for i in draw.items] == list(content.PARTICIPANTS)


def test_ac_census_v1_is_409_rows_short_of_the_register() -> None:
    rows = content.census_v1()
    assert len(rows) == 409
    total = sum((r.compensation for r in rows), Decimal(0))
    assert Decimal("14560000.00") - total == Decimal("182300.00")


def test_ac_the_disbursements_and_their_seed_draw_24_plus_16_payments() -> None:
    records = content.disbursements()
    population = canonical(records)
    assert len(population.records) == 1912
    assert population.total == Decimal("38640200.00")
    draw = sampler("2.3").select(
        population,
        "threshold_random_stratified",
        seed=content.SEEDS["granite-peak-disbursements-v1"],
        strata=content.GL_STRATA,
    )
    amount = {r.key: r.amount for r in records}
    assert [amount[i.record_key] for i in draw.items] == [Decimal(a) for *_, a in content.SURL]
    assert [(s.population_count, s.selected_count) for s in draw.strata] == [
        (24, 24),
        (1102, 16),
        (786, 0),
    ]
    drawn = sum((amount[i.record_key] or Decimal(0) for i in draw.items), Decimal(0))
    assert drawn == Decimal("3698700.00")


def test_the_census_file_is_one_sheet_with_its_header_and_rows() -> None:
    book = load_workbook(io.BytesIO(content.census_xlsx(content.census())), read_only=True)
    rows = list(book["Census"].iter_rows(values_only=True))
    assert rows[0] == content.HEADER
    assert len(rows) == 413
    assert len(content.distributions()) == 64
    assert len(content.SEEDS) == 4
