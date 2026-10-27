"""P-07-T45 (TASK-1327): CLI-06's consumer contract for the intake and import family, v1
(`docs/contracts/intake-import.md`; DEC-374, DEC-430). What the CLI-06 screens (P-07-T49 single
intake, P-07-T54 bulk import) read from the OpenAPI document and the models:

- g's tallies: an import of 212 rows reads "204 matched · 8 to review · 0 new", and after the
  run "210 records imported · 2 skipped · 0 new clients";
- an import row's TIN is organisations' masked shape by reference (kind, presence, last four,
  Restricted) and nothing more, and an offshore reader gets it null;
- b's dedupe card, the wizard's draft and validation, and the commit's answer (Prospect only);
- the error statuses each route declares (§6).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import ValidationError

from abacus.api.export_openapi import document
from abacus.modules.engagements.intake_contract import (
    ClientImportOut,
    ClientImportRowOut,
    ClientImportRowsOut,
    ClientIntakeDraftPayload,
    DedupeOut,
    IntakeCommittedOut,
    IntakeServiceIn,
)
from abacus.modules.identity.api import mask_tins

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
MASKED = "#/components/schemas/MaskedTinOut"
DRAFTS = "/v1/client-intake-drafts"
IMPORTS = "/v1/client-imports"
NOW = datetime(2026, 9, 8, 14, 4, tzinfo=UTC)  # CLI-06 g's clock


def _props(schema: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[schema].get("properties", {}))


def _refs(prop: Json) -> set[str]:
    found = {cast(str, prop["$ref"])} if "$ref" in prop else set[str]()
    for option in cast(list[Json], prop.get("anyOf", [])):
        found |= _refs(option)
    return found


def _import(**counts: int) -> ClientImportOut:
    return ClientImportOut.model_validate(
        {
            "id": str(uuid.uuid4()),
            "source": "cch_axcess_tax_export",
            "stage": "reviewing",
            "file_name": "Brightwater Hale clients.csv",
            "counts": counts,
            "started_by": str(uuid.uuid4()),
            "started_at": NOW.isoformat(),
        }
    )


# --- CLI-06 g: the tallies ----------------------------------------------------------------------


def test_g_reads_204_matched_8_to_review_and_0_new_of_212() -> None:
    page = _import(rows=212, matched=204, to_review=8, new=0)
    counts = page.counts
    assert (counts.rows, counts.matched, counts.to_review, counts.new) == (212, 204, 8, 0)
    assert counts.matched + counts.to_review + counts.new == counts.rows
    # Before the run nothing is imported, skipped or failed.
    assert (counts.imported, counts.skipped, counts.failed) == (0, 0, 0)
    wire = cast(Json, json.loads(page.model_dump_json()))["counts"]
    assert wire == {
        "rows": 212,
        "matched": 204,
        "to_review": 8,
        "new": 0,
        "skipped": 0,
        "imported": 0,
        "failed": 0,
    }


def test_g_after_the_run_reads_210_imported_2_skipped_0_new() -> None:
    done = _import(rows=212, matched=204, to_review=8, new=0, imported=210, skipped=2)
    assert (done.counts.imported, done.counts.skipped, done.counts.new) == (210, 2, 0)
    assert done.counts.imported + done.counts.skipped == done.counts.rows


def test_the_counts_schema_names_every_tally_as_an_integer() -> None:
    counts = _props("ClientImportCountsOut")
    for name in ("rows", "matched", "to_review", "new", "skipped", "imported", "failed"):
        assert counts[name]["type"] == "integer", name
    assert set(cast(list[str], SCHEMAS["ClientImportCountsOut"]["required"])) == {
        "rows",
        "matched",
        "to_review",
        "new",
    }
    # The import's stage is a code, not a registry status (DEC-374): no `status` field.
    assert "status" not in _props("ClientImportOut")
    assert set(cast(list[str], _props("ClientImportOut")["stage"]["enum"])) == {
        "uploaded",
        "mapped",
        "reviewing",
        "importing",
        "done",
        "failed",
    }


# --- the masked TIN shape in import rows --------------------------------------------------------


def test_a_rows_tin_is_the_masked_shape_by_reference_and_restricted() -> None:
    tin = _props("ClientImportRowOut")["tin"]
    assert _refs(tin) == {MASKED}
    assert tin["cls"] == "restricted"
    masked = _props("MaskedTinOut")
    assert set(masked) == {"kind", "presence", "last4"}
    assert set(cast(list[str], masked["kind"]["enum"])) == {"ssn", "ein", "itin"}
    assert {"type": "string", "pattern": "^[0-9]{4}$"} in cast(
        list[Json], masked["last4"]["anyOf"]
    )


def _row(tin: object) -> ClientImportRowOut:
    return ClientImportRowOut.model_validate(
        {
            "id": str(uuid.uuid4()),
            "row_no": 7,
            "display_name": "Calloway Family Trust",
            "entity_type": "trust",
            "tin": tin,
            "best_match_client_id": str(uuid.uuid4()),
            "best_match_name": "Calloway Family Trust",
            "score": 0.86,
        }
    )


def test_a_row_carries_kind_presence_and_four_digits_never_nine() -> None:
    row = _row({"kind": "ein", "presence": "on_file", "last4": "0287"})
    assert row.tin is not None and row.tin.last4 == "0287"
    for plain in ("912-70-0287", "912700287", {"kind": "ein", "last4": "912700287"}):
        with pytest.raises(ValidationError):
            _row(plain)


def test_an_offshore_reader_gets_no_tin_in_rows() -> None:
    """AC9.4: the row routes pass through `mask_tins_for`; its mask nulls the row's TIN."""
    page = ClientImportRowsOut(
        items=[_row({"kind": "ein", "presence": "on_file", "last4": "0287"})], total=1
    )
    masked = mask_tins(page)
    assert masked.items[0].tin is None
    assert "0287" not in masked.model_dump_json()


# --- single intake: dedupe, the draft, the commit -----------------------------------------------


def test_b_reads_a_96_percent_match_on_walter_thornbury() -> None:
    card = DedupeOut.model_validate(
        {
            "candidates": [
                {
                    "client_id": str(uuid.uuid4()),
                    "display_name": "Walter Thornbury",
                    "score": 0.96,
                    "basis": "name",
                }
            ]
        }
    )
    assert f"{card.candidates[0].score:.0%} match" == "96% match"
    assert set(_props("DedupeCandidateOut")) >= {"client_id", "display_name", "score", "basis"}
    assert not {p for p in _props("DedupeIn") if "tin" in p or "ein" in p}


def test_e_services_name_the_forms_they_create() -> None:
    """The estate's 706 alone from Forms 706 / 709; Form 56 is a line item (DEC-430)."""
    payload = ClientIntakeDraftPayload.model_validate(
        {
            "entity": {
                "mode": "existing_client",
                "client_id": str(uuid.uuid4()),
                "entity_name": "Estate of Walter Thornbury",
                "entity_type": "estate",
                "date_of_death": "2026-03-14",
            },
            "services": [
                {"type_code": "forms_706_709", "forms": ["706"]},
                {"type_code": "form_1041"},
                {"type_code": "form_1040"},
                {"type_code": "form_56"},
            ],
        }
    )
    assert payload.services[0].forms == ["706"]
    assert IntakeServiceIn(type_code="form_1041").forms is None
    assert "forms" in _props("IntakeServiceIn")
    # The draft names no TIN anywhere.
    for schema in ("ClientIntakeDraftPayload", "IntakeEntityIn", "IntakeContactIn"):
        assert not {p for p in _props(schema) if p in ("tin", "ssn", "ein", "itin")}


def test_f_the_commit_answers_prospect_engagements_and_identifiers() -> None:
    out = IntakeCommittedOut.model_validate(
        {
            "draft_id": str(uuid.uuid4()),
            "client_id": str(uuid.uuid4()),
            "client_entity_id": str(uuid.uuid4()),
            "engagement_ids": [str(uuid.uuid4())],
            "engagement_status": "prospect",
            "work_item_ids": [str(uuid.uuid4()) for _ in range(3)],
            "conflict_check_id": str(uuid.uuid4()),
            "acceptance_record_id": str(uuid.uuid4()),
        }
    )
    assert out.engagement_status == "prospect"
    assert len(out.work_item_ids) == 3
    assert {"start_acceptance"} == set(_props("IntakeCommitIn"))


# --- §6: the statuses each route declares --------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "statuses"),
    [
        ("post", "/v1/clients/dedupe", {"200", "403", "404", "422"}),
        ("post", DRAFTS, {"201", "403", "404", "422"}),
        ("patch", f"{DRAFTS}/{{draft_id}}", {"200", "403", "404", "409", "422"}),
        ("post", f"{DRAFTS}/{{draft_id}}/validate", {"200", "403", "404", "422"}),
        ("post", f"{DRAFTS}/{{draft_id}}/commit", {"201", "403", "404", "409", "422"}),
        # P-07-T52 (TASK-1503): the import routes are live; their stub 501 is retired.
        ("get", f"{IMPORTS}/{{import_id}}", {"200", "403", "404"}),
        ("get", f"{IMPORTS}/{{import_id}}/rows", {"200", "403", "404", "422"}),
        (
            "put",
            f"{IMPORTS}/{{import_id}}/rows/{{row_id}}/decision",
            {"200", "403", "404", "409", "422"},
        ),
        ("post", f"{IMPORTS}/{{import_id}}/run", {"202", "403", "404", "409", "422"}),
    ],
)
def test_each_route_declares_the_statuses_cli06_handles(
    method: str, path: str, statuses: set[str]
) -> None:
    assert statuses <= set(cast(Json, PATHS[path][method]["responses"]))
