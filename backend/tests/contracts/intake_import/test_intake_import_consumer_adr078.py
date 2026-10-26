"""P-07-T45, independent (TASK-1350): CLI-06's consumer contract for the intake and import
routes, read from `docs/contracts/intake-import.md` §2, §3, §6 and §8 and the CLI-06 g artboard,
against the OpenAPI document the generated client is built from.

"The suite asserts the CLI-06g tallies 204, 8 and 0 and the masked TIN shape in import rows."

The consumer relies on: the import's counts carrying the g tallies (212 rows, 204 matched, 8 to
review, 0 new); a row's TIN only ever the masked shape (kind, presence, last four), and null-ed
for an offshore reader; no schema anywhere in the section carrying a plain TIN; the commit and
the run declaring `Idempotency-Key`; the commit answering a Prospect engagement.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Final, cast

import pytest
from pydantic import ValidationError

from abacus.api.export_openapi import document
from abacus.modules.engagements.intake_contract import (
    ClientImportOut,
    ClientImportRowOut,
    ClientImportRowsOut,
    IntakeCommittedOut,
)
from abacus.modules.identity.offshore import mask_tins
from abacus.modules.organisations.contract import MaskedTinOut

Json = dict[str, object]
DOC: Final = cast(Json, json.loads(document()))
PATHS: Final = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS: Final = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
DRAFTS: Final = "/v1/client-intake-drafts"
IMPORTS: Final = "/v1/client-imports"
SECTION: Final = (
    ("post", "/v1/clients/dedupe"),
    ("post", DRAFTS),
    ("get", f"{DRAFTS}/{{draft_id}}"),
    ("patch", f"{DRAFTS}/{{draft_id}}"),
    ("delete", f"{DRAFTS}/{{draft_id}}"),
    ("post", f"{DRAFTS}/{{draft_id}}/validate"),
    ("post", f"{DRAFTS}/{{draft_id}}/commit"),
    ("post", IMPORTS),
    ("get", f"{IMPORTS}/{{import_id}}"),
    ("get", f"{IMPORTS}/{{import_id}}/rows"),
    ("put", f"{IMPORTS}/{{import_id}}/rows/{{row_id}}/decision"),
    ("post", f"{IMPORTS}/{{import_id}}/run"),
)
# A field that could carry a whole taxpayer id, by name.
PLAIN_TIN: Final = re.compile(r"^(tin|ein|ssn|itin|tax_id|taxpayer_id)(_(value|plain|full))?$")


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _schemas_of(name: str, seen: set[str] | None = None) -> set[str]:
    """Every component schema reachable from one."""
    seen = set() if seen is None else seen
    if name in seen:
        return seen
    seen.add(name)
    for ref in re.findall(r'"\$ref": "([^"]+)"', json.dumps(SCHEMAS[name])):
        _schemas_of(_ref_name(ref), seen)
    return seen


def _section_schemas() -> set[str]:
    found: set[str] = set()
    for method, path in SECTION:
        for ref in re.findall(r'"\$ref": "([^"]+)"', json.dumps(PATHS[path][method])):
            found |= _schemas_of(_ref_name(ref))
    return found


def test_every_route_the_consumer_calls_exists() -> None:
    missing = [(m, p) for m, p in SECTION if m not in PATHS.get(p, {})]
    assert missing == []


@pytest.mark.parametrize("path", [f"{DRAFTS}/{{draft_id}}/commit", f"{IMPORTS}/{{import_id}}/run"])
def test_commit_and_run_declare_the_idempotency_key(path: str) -> None:
    params = cast(list[Json], PATHS[path]["post"].get("parameters", []))
    keys = [p for p in params if str(p["name"]).lower() == "idempotency-key"]
    assert len(keys) == 1, params
    assert keys[0]["in"] == "header"


def test_cli06g_tallies_round_trip_through_the_import() -> None:
    """CLI-06 g: "204 matched · 8 to review · 0 new" of 212 rows."""
    wire = {
        "id": str(uuid.uuid4()),
        "source": "cch_axcess_tax_export",
        "stage": "reviewing",
        "file_name": "Brightwater_Hale_clients.csv",
        "counts": {"rows": 212, "matched": 204, "to_review": 8, "new": 0},
        "started_by": str(uuid.uuid4()),
        "started_at": datetime.now(UTC).isoformat(),
    }
    parsed = ClientImportOut.model_validate(wire)
    assert (parsed.counts.matched, parsed.counts.to_review, parsed.counts.new) == (204, 8, 0)
    assert parsed.counts.rows == 212
    again = json.loads(parsed.model_dump_json())
    assert again["counts"] == {
        "rows": 212,
        "matched": 204,
        "to_review": 8,
        "new": 0,
        "skipped": 0,
        "imported": 0,
        "failed": 0,
    }
    counts = cast(Json, SCHEMAS["ClientImportCountsOut"]["properties"])
    assert {"rows", "matched", "to_review", "new"} <= set(
        cast(list[str], SCHEMAS["ClientImportCountsOut"].get("required", []))
    )
    assert all(cast(Json, counts[k])["type"] == "integer" for k in counts)


def test_a_rows_tin_is_the_masked_shape_by_reference() -> None:
    tin = cast(Json, cast(Json, SCHEMAS["ClientImportRowOut"]["properties"])["tin"])
    refs = re.findall(r'"\$ref": "([^"]+)"', json.dumps(tin))
    assert [_ref_name(r) for r in refs] == ["MaskedTinOut"]
    masked = cast(Json, SCHEMAS["MaskedTinOut"]["properties"])
    assert set(masked) == {"kind", "presence", "last4"}
    last4 = json.dumps(masked["last4"])
    assert "^[0-9]{4}$" in last4


@pytest.mark.parametrize("digits", ["123456789", "12-3456789", "912-34-5678", "287", "02870"])
def test_a_row_never_carries_more_than_four_digits(digits: str) -> None:
    with pytest.raises(ValidationError):
        MaskedTinOut.model_validate({"kind": "ein", "presence": "on_file", "last4": digits})


def test_no_schema_in_the_section_carries_a_plain_tin() -> None:
    offenders: list[str] = []
    for name in sorted(_section_schemas()):
        for field, spec in cast(Json, SCHEMAS[name].get("properties", {})).items():
            refs = re.findall(r'"\$ref": "([^"]+)"', json.dumps(spec))
            if PLAIN_TIN.match(field) and [_ref_name(r) for r in refs] != ["MaskedTinOut"]:
                offenders.append(f"{name}.{field}")
    assert offenders == []


def _row(last4: str | None = "0287") -> ClientImportRowOut:
    return ClientImportRowOut.model_validate(
        {
            "id": str(uuid.uuid4()),
            "row_no": 7,
            "display_name": "Thornbury Family Trust",
            "entity_type": "trust",
            "tin": {"kind": "ein", "presence": "on_file", "last4": last4},
            "score": 0.84,
        }
    )


def test_an_offshore_reader_gets_the_row_tin_masked_further() -> None:
    row = _row()
    assert row.tin is not None and row.tin.last4 == "0287"
    masked = mask_tins(row)
    assert masked.tin is None or masked.tin.last4 is None
    assert "0287" not in masked.model_dump_json()
    page = ClientImportRowsOut(items=[row, _row("2208")], total=2)
    masked_page = mask_tins(page)
    assert "0287" not in masked_page.model_dump_json()
    assert "2208" not in masked_page.model_dump_json()
    # Everything else the consumer shows is untouched.
    assert [r.display_name for r in masked_page.items] == ["Thornbury Family Trust"] * 2


def test_the_commit_answers_a_prospect_engagement() -> None:
    status = cast(Json, SCHEMAS["IntakeCommittedOut"]["properties"])["engagement_status"]
    refs = re.findall(r'"\$ref": "([^"]+)"', json.dumps(status))
    assert [_ref_name(r) for r in refs] == ["EngagementStatus"]
    assert "prospect" in cast(list[str], SCHEMAS["EngagementStatus"]["enum"])
    answer = IntakeCommittedOut.model_validate(
        {
            "draft_id": str(uuid.uuid4()),
            "client_id": str(uuid.uuid4()),
            "client_entity_id": str(uuid.uuid4()),
            "engagement_ids": [str(uuid.uuid4())],
            "engagement_status": "prospect",
            "work_item_ids": [str(uuid.uuid4()) for _ in range(3)],
        }
    )
    assert answer.engagement_status == "prospect"
    assert len(answer.work_item_ids) == 3


@pytest.mark.parametrize(
    ("method", "path", "codes"),
    [
        ("post", f"{DRAFTS}/{{draft_id}}/commit", {"403", "404", "409", "422"}),
        ("post", f"{IMPORTS}/{{import_id}}/run", {"403", "404", "422"}),
        ("put", f"{IMPORTS}/{{import_id}}/rows/{{row_id}}/decision", {"403", "404", "422"}),
    ],
)
def test_the_error_statuses_of_section_6_are_declared(
    method: str, path: str, codes: set[str]
) -> None:
    declared = set(cast(Json, PATHS[path][method]["responses"]))
    assert codes <= declared, (path, sorted(declared))


def test_the_rows_list_is_the_envelope() -> None:
    rows = cast(Json, SCHEMAS["ClientImportRowsOut"]["properties"])
    assert {"items", "next_cursor", "total"} <= set(rows)
    params = {
        cast(str, p["name"])
        for p in cast(list[Json], PATHS[f"{IMPORTS}/{{import_id}}/rows"]["get"]["parameters"])
    }
    assert {"cursor", "limit", "review"} <= params
