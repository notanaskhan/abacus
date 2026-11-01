"""Brightwater Hale fixtures for the sampling contract stub (A-03-T02; AUD-11 a, f; SPEC-580).

Synthetic tenant data only, from the AUD-11 handoff (Northwind Robotics 401(k) Plan PY2025 and
Granite Peak FY2026 · BH-FS-430). They answer the stub's reads for these fixture ids and nothing
else; the live routes (T07, T10) read the tables, and T16 loads the same content through the
service APIs. Hashes are real SHA-256 values of the fixture's own content, never the design's
placeholder text (DV-A3). Nothing here is firm content: no size table, no template.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Final

_NS: Final = uuid.UUID("7b0c1a5e-a03d-4b1e-9a2c-5a3f1e2b0a11")
CT: Final = timezone(timedelta(hours=-5))  # CDT, the design's clock


def fixture_id(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _at(month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=CT).astimezone(UTC)


NORTHWIND_ENGAGEMENT: Final = fixture_id("engagement:northwind-py2025")
NORTHWIND_WORK_ITEM: Final = fixture_id("work-item:northwind-py2025")
GRANITE_ENGAGEMENT: Final = fixture_id("engagement:granite-peak-fy2026")
GRANITE_WORK_ITEM: Final = fixture_id("work-item:granite-peak-fy2026")
CENSUS_V2: Final = fixture_id("population:northwind-census-v2")
CENSUS_V1: Final = fixture_id("population:northwind-census-v1")
DISBURSEMENTS: Final = fixture_id("population:granite-peak-disbursements")
PARTICIPANTS: Final = fixture_id("sample-set:northwind-participants")
GL_SAMPLE: Final = fixture_id("sample-set:granite-peak-disbursements")
MARCUS: Final = fixture_id("user:marcus-delaney")
HANNAH: Final = fixture_id("user:hannah-leclerc")

TABLE_2: Final = {
    "label": "BH-EBP-210 step 3 · Table 2",
    "citation_id": fixture_id("citation:bh-ebp-210-step-3-table-2"),
    "verified": True,
}

# AUD-11a card 3, in draw order: (name, census ID, hire date).
PARTICIPANT_ROWS: Final = (
    ("Alicia Brennan", "NW-1184", date(2025, 2, 10)),
    ("Tomás Ibarra", "NW-0962", date(2021, 6, 14)),
    ("Priyanka Desai", "NW-1203", date(2025, 4, 7)),
    ("Gordon Whitfield", "NW-0418", date(2012, 9, 4)),
    ("Mei Tanaka", "NW-1150", date(2024, 9, 16)),
    ("Darnell Hughes", "NW-1022", date(2023, 3, 6)),
    ("Sofia Marchetti", "NW-1219", date(2025, 6, 2)),
    ("Kwame Mensah", "NW-1196", date(2025, 3, 17)),
    ("Rebecca Lindgren", "NW-0877", date(2019, 10, 21)),
    ("Hiroshi Nakamura", "NW-1171", date(2024, 11, 4)),
    ("Ingrid Solberg", "NW-0731", date(2017, 2, 13)),
    ("Felipe Navarro", "NW-1088", date(2023, 8, 28)),
    ("Aisha Rahman", "NW-1230", date(2025, 7, 14)),
    ("Connor Gallagher", "NW-0659", date(2015, 5, 11)),
    ("Yuki Mori", "NW-1189", date(2024, 12, 2)),
    ("Patrick Doyle", "NW-0990", date(2022, 1, 10)),
    ("Leila Farahani", "NW-1142", date(2024, 7, 8)),
    ("Andre Wilkins", "NW-1065", date(2023, 5, 15)),
    ("Natalie Brooks", "NW-1211", date(2025, 5, 5)),
    ("Vikram Sethi", "NW-0804", date(2018, 8, 6)),
    ("Chloe Dubois", "NW-0712", date(2016, 11, 14)),
    ("Benjamin Okoro", "NW-1158", date(2024, 10, 7)),
    ("Teresa Romero", "NW-0935", date(2020, 12, 7)),
    ("Ethan Caldwell", "NW-1004", date(2022, 6, 27)),
    ("Fatima Qureshi", "NW-1224", date(2025, 2, 3)),
)


def _tie(
    position: int, label: str, left: str, comparisons: list[tuple[str, str]], diff: str
) -> dict[str, object]:
    return {
        "id": fixture_id(f"tie:{label}:{position}"),
        "position": position,
        "label": label,
        "left_amount": Decimal(left),
        "comparisons": [
            {"label": c, "amount": Decimal(a), "citation": None, "ledger_ref": None}
            for c, a in comparisons
        ],
        "difference": Decimal(diff),
        "result": "tie" if Decimal(diff) == 0 else "off",
        "explanation": None,
        "engine_version": "2.3",
        "inputs_hash": _sha(f"tie:{label}:{left}:{comparisons}"),
    }


def _census(
    population_id: uuid.UUID, version_no: int, records: int, ties: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "id": population_id,
        "engagement_id": NORTHWIND_ENGAGEMENT,
        "work_item_id": NORTHWIND_WORK_ITEM,
        "source": {
            "kind": "upload",
            "evidence_version_id": fixture_id(f"evidence:northwind-census-v{version_no}"),
            "file_name": "Northwind Census PY2025.xlsx",
            "file_version_no": version_no,
            "uploaded_by_name": "Example client contact",
            "uploaded_on": date(2026, 9, 16 if version_no == 2 else 15),
        },
        "record_count": records,
        "record_unit": "participants",
        "amount_total": Decimal("14560000.00") if version_no == 2 else Decimal("14377700.00"),
        "sha256": _sha(f"northwind-census-v{version_no}"),
        "sampling_unit": "participant (census record)",
        "deviation_definition": "any attribute in EBP-03/EBP-04 not agreed to source",
        "ties": ties,
        "created_by_name": "Marcus Delaney",
        "created_at": _at(9, 16, 15, 12) if version_no == 2 else _at(9, 15, 16, 40),
    }


def _populations() -> dict[uuid.UUID, dict[str, object]]:
    v2 = _census(
        CENSUS_V2,
        2,
        412,
        [
            _tie(
                1,
                "PayGrid YTD register",
                "14560000.00",
                [("PayGrid YTD register", "14560000.00")],
                "0.00",
            ),
            _tie(
                2,
                "W-3 Box 1 + Box 12 D",
                "14560000.00",
                [("W-3 Box 1", "13813400.00"), ("W-3 Box 12 D", "746600.00")],
                "0.00",
            ),
        ],
    )
    v1 = _census(
        CENSUS_V1,
        1,
        409,
        [
            _tie(
                1,
                "PayGrid YTD register",
                "14377700.00",
                [("PayGrid YTD register", "14560000.00")],
                "-182300.00",
            )
        ],
    )
    gl: dict[str, object] = {
        "id": DISBURSEMENTS,
        "engagement_id": GRANITE_ENGAGEMENT,
        "work_item_id": GRANITE_WORK_ITEM,
        "source": {
            "kind": "general_ledger",
            "gl_snapshot_id": fixture_id("gl-snapshot:granite-peak-fy2026"),
            "connection_label": "NetSuite · Granite Peak Outdoor Supply",
            "query_label": "Disbursements Jul 1 \u2013 Sep 18, 2026",
            "query": {
                "account_codes": [],
                "side": "credit",
                "kinds": ["Payment", "Bill payment"],
                "posted_from": date(2026, 7, 1),
                "posted_to": date(2026, 9, 18),
            },
            "pulled_at": _at(9, 24, 10, 18),
        },
        "record_count": 1912,
        "record_unit": "payments",
        "amount_total": Decimal("38640200.00"),
        "sha256": _sha("granite-peak-disbursements-fy2026"),
        "sampling_unit": "payment",
        "deviation_definition": None,
        "ties": [
            _tie(
                1,
                "Front Range Bank operating account cash disbursements",
                "38640200.00",
                [("Front Range Bank operating account cash disbursements", "38640200.00")],
                "0.00",
            ),
            {
                **_tie(2, "No gaps in check numbers · ACH batch totals agree", "0", [], "0"),
                "left_amount": None,
                "difference": None,
            },
        ],
        "created_by_name": "Simone Baptiste",
        "created_at": _at(9, 24, 10, 18),
    }
    return {CENSUS_V2: v2, CENSUS_V1: v1, DISBURSEMENTS: gl}


POPULATIONS: Final = _populations()


def population(population_id: uuid.UUID) -> dict[str, object] | None:
    return POPULATIONS.get(population_id)


def _stamp(user: uuid.UUID, name: str, initials: str, at: datetime) -> dict[str, object]:
    return {"user_id": user, "name": name, "initials": initials, "at": at}


def _participant_items(q: str | None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "position": i,
            "record_key": key,
            "name": name,
            "hire_date": hired,
            "amount": None,
            "selection_reason": "random",
            "stratum_position": None,
        }
        for i, (name, key, hired) in enumerate(PARTICIPANT_ROWS, start=1)
    ]
    if q:
        needle = q.casefold()
        rows = [
            r
            for r in rows
            if needle in str(r["name"]).casefold() or needle in str(r["record_key"]).casefold()
        ]
    return rows


def _participants(version: int | None) -> dict[str, object] | None:
    if version not in (None, 1, 2):
        return None
    current = version or 2
    seed = 0x5E2A91 if current == 2 else 0x3C77D0
    versions = [
        {
            "version_no": 2,
            "status": "approved",
            "population_id": CENSUS_V2,
            "population_label": "census v2",
            "record_count": 412,
            "tie_result": "tie",
            "tie_difference": Decimal("0.00"),
            "seed_hex": "0x5E2A91",
            "final_size": 25,
            "override_pending": False,
            "created_by_name": "Marcus Delaney",
            "created_at": _at(9, 16, 15, 12),
            "prepared": _stamp(MARCUS, "Marcus Delaney", "MD", _at(9, 16, 15, 12)),
            "approved": _stamp(HANNAH, "Hannah Leclerc", "HL", _at(9, 16, 16, 5)),
        },
        {
            "version_no": 1,
            "status": "superseded",
            "population_id": CENSUS_V1,
            "population_label": "census v1",
            "record_count": 409,
            "tie_result": "off",
            "tie_difference": Decimal("-182300.00"),
            "seed_hex": "0x3C77D0",
            "final_size": 25,
            "override_pending": False,
            "created_by_name": "Marcus Delaney",
            "created_at": _at(9, 15, 16, 40),
            "prepared": None,
            "approved": None,
        },
    ]
    status = "approved" if current == 2 else "superseded"
    return {
        "id": PARTICIPANTS,
        "engagement_id": NORTHWIND_ENGAGEMENT,
        "work_item_id": NORTHWIND_WORK_ITEM,
        "title": "Participants",
        "purpose": "Eligibility, contribution and pay-rate tests on the same 25 participants",
        "program_step_key": None,
        "version_no": current,
        "status": status,
        "population": POPULATIONS[CENSUS_V2 if current == 2 else CENSUS_V1],
        "parameters": {
            "method": "attribute_nonstatistical",
            "rmm": "moderate",
            "tolerable_rate": Decimal("0.10"),
            "expected_rate": Decimal("0.00"),
            "confidence": Decimal("0.90"),
            "computed_size": 25,
            "statistical_crosscheck_size": 22,
            "override_size": None,
            "override_rationale": None,
            "final_size": 25,
            "seed": seed,
            "seed_hex": f"0x{seed:06X}",
            "seed_source": "scenario",
            "sampler_version": "2.3",
            "citations": [TABLE_2],
        },
        "strata": [],
        "items_total": 25,
        "items_amount": None,
        "versions": versions,
        "inputs_hash": _sha(f"participants:v{current}:inputs"),
        "items_hash": _sha(f"participants:v{current}:items"),
        "content_hash": _sha(f"participants:v{current}:content"),
        "allowed_actions": ["sample_set.export", "sample_set.generate_requests"]
        if current == 2
        else [],
    }


def _gl_sample(version: int | None) -> dict[str, object] | None:
    if version not in (None, 1):
        return None
    return {
        "id": GL_SAMPLE,
        "engagement_id": GRANITE_ENGAGEMENT,
        "work_item_id": GRANITE_WORK_ITEM,
        "title": "Disbursements",
        "purpose": None,
        "program_step_key": None,
        "version_no": 1,
        "status": "draft",
        "population": POPULATIONS[DISBURSEMENTS],
        "parameters": {
            "method": "threshold_random_stratified",
            "rmm": None,
            "tolerable_rate": None,
            "expected_rate": None,
            "confidence": None,
            "computed_size": 40,
            "statistical_crosscheck_size": None,
            "override_size": None,
            "override_rationale": None,
            "final_size": 40,
            "seed": 0x7C31B4,
            "seed_hex": "0x7C31B4",
            "seed_source": "scenario",
            "sampler_version": "2.3",
            "citations": [],
        },
        "strata": [
            {
                "position": 1,
                "min_amount": Decimal("50000.00"),
                "max_amount": None,
                "test_rule": "all",
                "random_count": None,
                "population_count": 24,
                "population_amount": None,
                "selected_count": 24,
            },
            {
                "position": 2,
                "min_amount": Decimal("7750.00"),
                "max_amount": Decimal("50000.00"),
                "test_rule": "random",
                "random_count": 16,
                "population_count": 1102,
                "population_amount": None,
                "selected_count": 16,
            },
            {
                "position": 3,
                "min_amount": None,
                "max_amount": Decimal("7750.00"),
                "test_rule": "none",
                "random_count": None,
                "population_count": 786,
                "population_amount": None,
                "selected_count": 0,
            },
        ],
        "items_total": 40,
        "items_amount": Decimal("3698700.00"),
        "versions": [
            {
                "version_no": 1,
                "status": "draft",
                "population_id": DISBURSEMENTS,
                "population_label": "Disbursements Jul 1 \u2013 Sep 18, 2026",
                "record_count": 1912,
                "tie_result": "tie",
                "tie_difference": Decimal("0.00"),
                "seed_hex": "0x7C31B4",
                "final_size": 40,
                "override_pending": False,
                "created_by_name": "Simone Baptiste",
                "created_at": _at(9, 24, 10, 20),
                "prepared": None,
                "approved": None,
            }
        ],
        "inputs_hash": _sha("disbursements:v1:inputs"),
        "items_hash": _sha("disbursements:v1:items"),
        "content_hash": _sha("disbursements:v1:content"),
        "allowed_actions": [],
    }


def sample_set(sample_set_id: uuid.UUID, version: int | None) -> dict[str, object] | None:
    if sample_set_id == PARTICIPANTS:
        return _participants(version)
    if sample_set_id == GL_SAMPLE:
        return _gl_sample(version)
    return None


def items(
    sample_set_id: uuid.UUID, version_no: int, q: str | None
) -> list[dict[str, object]] | None:
    """Northwind's 25 (both versions show Version 2's list in the design; v1's list is not
    designed, so only Version 2 answers). Granite Peak's 40 items are not designed: 501."""
    if sample_set_id == PARTICIPANTS and version_no == 2:
        return _participant_items(q)
    return None


def draw_progress(sample_set_id: uuid.UUID, version_no: int) -> dict[str, object] | None:
    if sample_set_id == PARTICIPANTS and version_no == 2:
        rows = _participant_items(None)
        return {
            "version_no": 2,
            "status": "approved",
            "items_done": 25,
            "items_total": 25,
            "failure_code": None,
            "items": rows,
        }
    return None
