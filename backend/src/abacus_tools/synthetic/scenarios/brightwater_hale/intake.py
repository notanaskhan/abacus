"""The `intake` slice (P-07-T50; P-07 §5): scenario content wave 3 for CLI-06, CLI-07 and ENG-03,
as events the loader replays through engagements' and organisations' services. Synthetic,
Brightwater Hale only; text verbatim from the ENG-03 and CLI-07 fixtures (which carry the
handoff's words). Opt-in (`--slice intake`, which brings `acceptance` for the questionnaire
templates and Harborline Trust Company, and `people`); SCENARIO_HASH is unchanged.

- **Thornbury intake holdout** (CLI-06 a to h, J19): `--holdout thornbury_estate` loads Walter
  Thornbury as a client with his own entity only (holdouts.py). With it, Samuel Ito's conflict
  check on "Harborline Trust Company" over the Walter Thornbury client is run and **left open**
  (CLI-06 h's hit: Harborline is Calloway Family Trust's custodian); without it the event is not
  loaded (`data["holdout"]`), and wave 2's cleared check over the estate client stands.
- **Granite Peak draft** (ENG-03 d, Mon Aug 24, 10:04 AM CT): "FY2026 Financial Statement
  Audit", FS audit, at step 1, G1 unmet because no acceptance is decided for it.
- **Fairhaven draft** (ENG-03 a, Tue Sep 8, 9:39 AM CT): "PY2025 EBP Audit" on the Fairhaven Foods
  401(k) Plan, at step 1, the team MO, LK, CD and FN. The `fairhaven_ebp` holdout leaves it out
  with its client.
- **Meridian continuance** (CLI-07 f): wave 2 opened it; here the answers, Low, the one
  prior-year flag (Fri Sep 11, 4:30 PM CT) and the send to Margaret Okonkwo (5:15 PM CT).
- **The 212-row CCH client list** is a file, not an event (`client_list.py`).

Both drafts are Margaret Okonkwo's, where ENG-03 shows Hannah Leclerc: a manager does not hold
`engagement.create` (DEC-412's finding), and a draft is readable by its creator alone (DEC-593).
Acts dated before the firm's Sep 1 setup are replayed on Sep 2 and keep their canon date in their
data (DEC-363).
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.acceptance import (
    HARBORLINE,
    MERIDIAN,
    REPLAY_FROM,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "intake"
NEEDS: Final = ("people", "acceptance")
GRANITE: Final = "Granite Peak Outdoor Supply, Inc."
FAIRHAVEN: Final = "Fairhaven Foods 401(k) Plan"
WALTER: Final = "Walter Thornbury"
HOLDOUT: Final = "thornbury_estate"

GRANITE_DRAFT: Final[dict[str, object]] = {
    "type_code": "fs_audit",
    "name": "FY2026 Financial Statement Audit",
    "fiscal_period_start": "2025-07-01",
    "fiscal_period_end": "2026-06-30",
    "team": [("MO", "engagement_partner"), ("HL", "manager")],
    "owner": "MO",
    "step": "client_type",
}
FAIRHAVEN_DRAFT: Final[dict[str, object]] = {
    "type_code": "ebp_audit",
    "name": "PY2025 EBP Audit",
    "fiscal_period_start": "2025-01-01",
    "fiscal_period_end": "2025-12-31",
    "team": [
        ("MO", "engagement_partner"),
        ("LK", "manager"),
        ("CD", "senior"),
        ("FN", "staff"),
    ],
    "owner": "MO",
    "step": "client_type",
}
DRAFTS: Final[dict[str, tuple[str, dict[str, object]]]] = {
    "granite-peak": (GRANITE, GRANITE_DRAFT),
    "fairhaven": (FAIRHAVEN, FAIRHAVEN_DRAFT),
}

# CLI-07 f: the sections' answers as the rail reads them (the "Audit & assurance v3" codes; the
# fixture's independence line has no section in v3, DEC-412), Low, one prior-year flag.
MERIDIAN_ANSWERS: Final[tuple[tuple[str, str], ...]] = (
    ("engagement_profile", "Complete · HL"),
    ("integrity_screening", "No matches · OFAC & adverse media"),
    ("scope_complexity", "No changes from FY2025"),
    ("client_identification", "No conflicts found"),
    ("prior_year_history", "1 flag · IL DOR notice open"),
    ("fees_collectability", "No unpaid fees"),
    ("competence_capacity", "Manufacturing audits: MO, HL"),
)
MERIDIAN_FLAGS: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "low",
        "Prior-year history — one open item",
        "FY2025 audit released Apr 2026 · IL DOR notice of tax due IL-1120 $5,880 (response sent "
        "Sep 2)\nNAS: the firm prepares the 2025 Form 1120",
    ),
)


def _at(month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=CT)


@register_slice(SLICE)
def intake_events() -> list[Event]:
    def event(
        label: str, at: datetime, kind: str, actor: str, data: dict[str, object], **kw: str
    ) -> Event:
        return Event(label, at, kind, actor, SLICE, data, **kw)

    return [
        # ENG-03 d, Mon Aug 24, 10:04 AM CT: before setup, so replayed on Sep 2 (DEC-363).
        event(
            "draft:granite-peak",
            REPLAY_FROM,
            "engagements.draft_created",
            "MO",
            {"draft": "granite-peak", "canon_at": "2026-08-24T10:04:00-05:00"},
            client=GRANITE,
        ),
        # ENG-03 a, Tue Sep 8, 9:39 AM CT.
        event(
            "draft:fairhaven",
            _at(9, 8, 9, 39),
            "engagements.draft_created",
            "MO",
            {"draft": "fairhaven"},
            client=FAIRHAVEN,
        ),
        # CLI-06 h, Tue Sep 8, 2:09 PM CT: the hit, left for Samuel's assessment.
        event(
            "conflict-check:walter-thornbury:harborline",
            _at(9, 8, 14, 9),
            "organisations.conflict_check_run",
            "SI",
            {"subject": "client", "names": [HARBORLINE], "clear": None, "holdout": HOLDOUT},
            client=WALTER,
        ),
        # CLI-07 f: Meridian's answers and flag (Fri Sep 11, 4:30 PM CT), sent at 5:15 PM CT.
        event(
            "acceptance-prepared:meridian",
            _at(9, 11, 16, 30),
            "engagements.acceptance_prepared",
            "HL",
            {"draft": "meridian", "risk_rating": "low"},
            client=MERIDIAN,
        ),
        event(
            "acceptance-sent:meridian",
            _at(9, 11, 17, 15),
            "engagements.acceptance_sent",
            "HL",
            {"draft": "meridian"},
            client=MERIDIAN,
        ),
    ]
