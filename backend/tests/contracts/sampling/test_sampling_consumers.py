"""AUD-11's consumer view of the sampling API stub (A-03-T22; TASK-2507; SPEC-580 AC-18).

Chapter 01 §1.3.2 steps 1 and 3: the consumer pins what it reads. The designed Northwind facts
(AUD-11 a: 25 of 412, seed 0x5E2A91, the first five names, 22 at 90 % / 10 % / 0 %, the W-3 tie
13,813,400.00 + 746,600.00 = 14,560,000.00, Version 1 off 182,300.00) and Granite Peak's (AUD-11
f: 24 / 1,102 / 786, 40 items, 3,698,700.00, seed 0x7C31B4) fit the stub's models; the fields
AUD-11 reads exist with their types; amounts travel as decimal strings; the actions AUD-11 drives
are human only. A breaking change to these shapes fails here. The fixture half is
`apps/web/src/fixtures/contracts/sampling-mapping.contract.test.ts`.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.sampling import contract_fixtures as fx
from abacus.modules.sampling.contract import SampleItemOut, SampleSetOut

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
# The fields AUD-11 reads, per schema. Removing or renaming one is a breaking change.
READS: dict[str, set[str]] = {
    "SampleSetOut": {
        "id",
        "title",
        "version_no",
        "status",
        "population",
        "parameters",
        "strata",
        "items_total",
        "items_amount",
        "versions",
        "content_hash",
        "allowed_actions",
    },
    "ParametersOut": {
        "method",
        "rmm",
        "tolerable_rate",
        "expected_rate",
        "confidence",
        "computed_size",
        "statistical_crosscheck_size",
        "override_size",
        "final_size",
        "seed_hex",
        "sampler_version",
        "citations",
    },
    "SampleSetVersionOut": {
        "version_no",
        "status",
        "population_label",
        "record_count",
        "tie_result",
        "tie_difference",
        "seed_hex",
        "override_pending",
        "prepared",
        "approved",
    },
    "SampleItemOut": {"position", "record_key", "name", "hire_date", "selection_reason"},
    "StratumOut": {"position", "min_amount", "max_amount", "test_rule", "population_count"},
}
HUMAN_ONLY = (
    "population.create",
    "sample_set.create",
    "sample_set.approve",
    "sample_set.export",
    "sample_set.generate_requests",
)


@pytest.mark.parametrize("schema", sorted(READS))
def test_ac18_the_fields_aud11_reads_exist(schema: str) -> None:
    properties = cast(Json, SCHEMAS[schema]["properties"])
    assert READS[schema] <= set(properties), schema


def test_ac18_northwind_version_2_fits_and_foots() -> None:
    found = fx.sample_set(fx.PARTICIPANTS, None)
    assert found is not None
    sample = SampleSetOut.model_validate(found)
    assert (sample.population.record_count, sample.items_total) == (412, 25)
    assert sample.parameters.seed_hex == "0x5E2A91"
    assert sample.parameters.statistical_crosscheck_size == 22
    w3 = sample.population.ties[1]
    assert sum(c.amount for c in w3.comparisons) == sample.population.amount_total
    assert [(v.version_no, v.status, v.tie_difference) for v in sample.versions] == [
        (2, "approved", Decimal("0.00")),
        (1, "superseded", Decimal("-182300.00")),
    ]
    assert json.loads(sample.model_dump_json())["population"]["amount_total"] == "14560000.00"


def test_ac18_the_first_five_participants_are_the_designed_ones() -> None:
    rows = fx.items(fx.PARTICIPANTS, 2, None)
    assert rows is not None
    items = [SampleItemOut.model_validate(r) for r in rows]
    assert [i.name for i in items[:5]] == [
        "Alicia Brennan",
        "Tomás Ibarra",
        "Priyanka Desai",
        "Gordon Whitfield",
        "Mei Tanaka",
    ]
    assert [i.position for i in items] == list(range(1, 26))


def test_ac18_granite_peak_strata_foot() -> None:
    found = fx.sample_set(fx.GL_SAMPLE, None)
    assert found is not None
    sample = SampleSetOut.model_validate(found)
    counts = [s.population_count for s in sample.strata]
    assert counts == [24, 1102, 786] and sum(counts) == sample.population.record_count == 1912
    assert sum(s.selected_count for s in sample.strata) == sample.items_total == 40
    assert sample.items_amount == Decimal("3698700.00")
    assert sample.parameters.seed_hex == "0x7C31B4"


@pytest.mark.parametrize("action", HUMAN_ONLY)
def test_ac18_the_actions_aud11_drives_are_human_only(action: str) -> None:
    decisions = RULES[action].decisions
    assert decisions.get("agent") == "deny"
    assert decisions.get("system", "deny") == "deny"
