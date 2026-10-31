"""Granite Peak fixtures for the C9 v2 stub (A-03-T03; AUD-31 f; SPEC-580 AC-16).

Only what the AUD-31 handoff shows: Granite Peak Outdoor Supply FY2026, one entity, 128 accounts
mapped by rule and confirmed ("128 accounts", the count AUD-38 hands to tax), TB balanced 1 of 1.
The 128 rows and BH FS groupings v1's lines are client and firm content: A-03-T16 loads them
through the import endpoints and service APIs, so the stub answers 501 for them (DEC-1555).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Final

_NS: Final = uuid.UUID("3c9a7d20-a03d-4c9b-8e11-0f5b2a6e7c31")
CT: Final = timezone(timedelta(hours=-5))


def fixture_id(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)


GRANITE_ENGAGEMENT: Final = fixture_id("engagement:granite-peak-fy2026")
GRANITE_TB: Final = fixture_id("trial-balance:granite-peak-fy2026")
GRANITE_ENTITY: Final = fixture_id("entity:granite-peak-outdoor-supply")
GRANITE_MAPPING: Final = fixture_id("mapping-set:granite-peak-fy2026")
BH_GROUPINGS_V1: Final = fixture_id("grouping-set-version:bh-fs-groupings:1")
CALEB: Final = fixture_id("user:caleb-dunn")


def _summary() -> dict[str, object]:
    return {
        "id": GRANITE_MAPPING,
        "engagement_id": GRANITE_ENGAGEMENT,
        "trial_balance_id": GRANITE_TB,
        "trial_balance_version_no": 1,
        "client_entity_id": GRANITE_ENTITY,
        "entity_name": "Granite Peak Outdoor Supply",
        "period_end": date(2026, 6, 30),
        "grouping_set_version_id": BH_GROUPINGS_V1,
        "grouping_set_label": "BH FS groupings v1",
        "prior_source": "prior_engagement",
        "run_status": "ready",
        "status": "prepared",
        "tallies": {
            "accounts": 128,
            "mapped": 128,
            "need_review": 0,
            # The split by method is not in the design (prior year · High, number range · Medium).
            "prior_year_match": None,
            "number_range": None,
            "edited": None,
            "tb_balanced": 1,
            "tb_count": 1,
        },
        "sign_offs": [
            {
                "level": 1,
                "initials": "CD",
                "name": "Caleb Dunn",
                "at": datetime(2026, 9, 14, 11, 40, tzinfo=CT).astimezone(UTC),
                "stale": False,
            }
        ],
        "content_hash": hashlib.sha256(b"granite-peak-fy2026-mapping-v1").hexdigest(),
    }


def mapping_sets(engagement_id: uuid.UUID) -> list[dict[str, object]] | None:
    return [_summary()] if engagement_id == GRANITE_ENGAGEMENT else None


def run(mapping_set_id: uuid.UUID) -> dict[str, object] | None:
    if mapping_set_id != GRANITE_MAPPING:
        return None
    return {
        "mapping_set_id": GRANITE_MAPPING,
        "run_status": "ready",
        "run_done": 128,
        "run_total": 128,
        "failure_code": None,
    }
