"""A-03-T07 (TASK-2611; A-03 §3 F2; SPEC-580; DEC-1660) over HTTP against Postgres: a population
from an uploaded census and its completeness ties.

The evidence read and the isolated parse are replaced by the census rows (the parser is P-03's
and tested there); everything else is real: the matrix, the flag, the engagement, the insert-only
tables, the audit and the citation check.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal
from typing import Any, cast

import pytest

from abacus.modules.evidence.api import ExtractedTable, Extraction
from abacus.modules.sampling import populations

from .support import Net, Person, Seeder, Site
from .tb_support import work_item

Json = dict[str, Any]  # Any: JSON bodies
HEADER = ("Participant ID", "Name", "Hire date", "Compensation", "SSN")
MAP = {
    "record_key": "Participant ID",
    "name": "Name",
    "date": "Hire date",
    "amount": "Compensation",
}


def _census(count: int, total: Decimal) -> tuple[tuple[str, ...], ...]:
    each = (total / count).quantize(Decimal("1"))
    rows: list[tuple[str, ...]] = [HEADER]
    for n in range(count):
        amount = each if n < count - 1 else total - each * (count - 1)
        rows.append(
            (f"NW-{2000 + n}", f"Participant {n}", "2020-01-06", str(amount), "000-00-0000")
        )
    return tuple(rows)


@pytest.fixture
def sheet(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, tuple[tuple[str, ...], ...]]]:
    """The census the next upload parses (P-03's read and isolated parse stand aside)."""
    current: dict[str, tuple[tuple[str, ...], ...]] = {
        "rows": _census(412, Decimal("14560000.00"))
    }

    async def read_version(ctx: object, version_id: uuid.UUID) -> bytes:
        return b"census"

    def extract_isolated(content: bytes, media_type: str) -> Extraction:
        return Extraction("extracted", tables=(ExtractedTable("Census", None, current["rows"]),))

    monkeypatch.setattr(populations, "read_version", read_version)
    monkeypatch.setattr(populations, "extract_isolated", extract_isolated)
    yield current


async def _setup(seed: Seeder) -> tuple[Site, Person, uuid.UUID]:
    tenant = await seed.firm()
    marcus = await seed.person(tenant)
    site = await seed.site(tenant, marcus.user_id, "census")
    await seed.member(site, marcus, "senior")
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'sampling.sample_sets', 'true', 'a03', 'TASK-2611')",
        tenant,
    )
    return site, marcus, await work_item(seed, site, marcus.user_id)


def _body(site: Site, column_map: dict[str, str] | None = None) -> Json:
    return {
        "source": {
            "kind": "upload",
            "evidence_version_id": str(site.version_id),
            "column_map": column_map or MAP,
        },
        "sampling_unit": "participant (census record)",
        "deviation_definition": "any attribute not agreed to source",
    }


async def test_ac1_census_v2_yields_412_records_and_two_ties(
    net: Net, seed: Seeder, sheet: dict[str, Any]
) -> None:
    site, marcus, item = await _setup(seed)
    made = await net.call("POST", f"/v1/work-items/{item}/populations", marcus, body=_body(site))
    assert made.status_code == 201, made.text
    population = cast(Json, made.json())
    assert population["record_count"] == 412
    assert Decimal(population["amount_total"]) == Decimal("14560000.00")
    assert population["record_unit"] == "participants"
    assert len(population["sha256"]) == 64
    pid = population["id"]
    stored = await seed.value(
        "SELECT count(*) FROM sample_population_records WHERE population_id = $1", uuid.UUID(pid)
    )
    assert stored == 412
    for label, comparisons in (
        ("PayGrid YTD register", [("PayGrid YTD register", "14560000.00")]),
        ("W-3 Box 1 + Box 12 D", [("W-3 Box 1", "13813400.00"), ("W-3 Box 12 D", "746600.00")]),
    ):
        tie = await net.call(
            "POST",
            f"/v1/populations/{pid}/ties",
            marcus,
            body={
                "label": label,
                "comparisons": [{"label": c, "amount": a} for c, a in comparisons],
            },
        )
        assert tie.status_code == 201, tie.text
        assert tie.json()["result"] == "tie"
    read = await net.call("GET", f"/v1/populations/{pid}", marcus)
    assert read.status_code == 200, read.text
    assert [(t["position"], t["result"]) for t in read.json()["ties"]] == [(1, "tie"), (2, "tie")]
    actions = await seed.actions(site.tenant_id)
    assert actions.count("population.created") == 1
    assert actions.count("population.tie_recorded") == 2


async def test_ac2_census_v1_computes_off_182300(
    net: Net, seed: Seeder, sheet: dict[str, Any]
) -> None:
    site, marcus, item = await _setup(seed)
    sheet["rows"] = _census(409, Decimal("14377700.00"))
    made = await net.call("POST", f"/v1/work-items/{item}/populations", marcus, body=_body(site))
    assert made.status_code == 201, made.text
    tie = await net.call(
        "POST",
        f"/v1/populations/{made.json()['id']}/ties",
        marcus,
        body={
            "label": "PayGrid YTD register",
            "comparisons": [{"label": "PayGrid YTD register", "amount": "14560000.00"}],
        },
    )
    assert tie.status_code == 201, tie.text
    assert tie.json()["result"] == "off"
    assert Decimal(tie.json()["difference"]) == Decimal("-182300.00")


async def test_ac4_an_ssn_column_is_refused_422_restricted_column(
    net: Net, seed: Seeder, sheet: dict[str, Any]
) -> None:
    site, marcus, item = await _setup(seed)
    body = _body(site, {**MAP, "name": "SSN"})
    refused = await net.call("POST", f"/v1/work-items/{item}/populations", marcus, body=body)
    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"] == "restricted_column"
    count = await seed.value(
        "SELECT count(*) FROM sample_populations WHERE tenant_id = $1", site.tenant_id
    )
    assert count == 0


async def test_ac2_an_unverified_citation_is_refused_and_nothing_is_saved(
    net: Net, seed: Seeder, sheet: dict[str, Any]
) -> None:
    site, marcus, item = await _setup(seed)
    made = await net.call("POST", f"/v1/work-items/{item}/populations", marcus, body=_body(site))
    pid = made.json()["id"]
    refused = await net.call(
        "POST",
        f"/v1/populations/{pid}/ties",
        marcus,
        body={
            "label": "PayGrid YTD register",
            "comparisons": [
                {
                    "label": "PayGrid YTD register",
                    "amount": "14560000.00",
                    "citation_id": str(uuid.uuid4()),
                }
            ],
        },
    )
    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"] == "citation_unverified"
    count = await seed.value(
        "SELECT count(*) FROM completeness_ties WHERE population_id = $1", uuid.UUID(pid)
    )
    assert count == 0


async def test_another_engagements_evidence_is_not_found(
    net: Net, seed: Seeder, sheet: dict[str, Any]
) -> None:
    site, marcus, item = await _setup(seed)
    other = await seed.site(site.tenant_id, marcus.user_id, "elsewhere")
    body = _body(other)
    refused = await net.call("POST", f"/v1/work-items/{item}/populations", marcus, body=body)
    assert refused.status_code == 404, refused.text


async def test_a_person_off_the_engagement_never_reads_the_population(
    net: Net, seed: Seeder, sheet: dict[str, Any]
) -> None:
    site, marcus, item = await _setup(seed)
    made = await net.call("POST", f"/v1/work-items/{item}/populations", marcus, body=_body(site))
    stranger = await seed.person(site.tenant_id)
    read = await net.call("GET", f"/v1/populations/{made.json()['id']}", stranger)
    assert read.status_code in (403, 404), read.text
