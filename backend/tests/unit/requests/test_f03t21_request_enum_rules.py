# ac-test-author: ayushkbhatia
"""F-03-T21 (ADR-078) for F-03-T15 and T16, the parts that need no database: the request status
set and its 9.5.6 bridge as the registry records it, the banned-pattern rules that keep the old
codes and the `reminder` identifiers out, and the screener left as it was.

Promises: the request codes are `draft · requested · uploaded · received · returned ·
not_applicable` with `overdue` derived and never stored (F-03 Story 3.1, ADR-144, SPEC-306 AC-5);
each retired code maps as chapter 09 §9.5.6 says (F-03 §5 migration 0059, ADR-144); "a banned
pattern rejects the old literals" (F-03-T15) and L12 rejects a new `reminder` identifier (Story
3.3; the glossary itself names compounds such as `max_reminders`, so the cases here are the
bare word and the legacy table names F-02-T07 cites); the screener keeps its proposal vocabulary,
its prompt version and its protected suite thresholds (F-03 §6, §9 item 5).

The registry's retired map is checked against the bridge typed here from the plan, never the
other way round. The migration that applies the bridge to stored rows is proved row by row in
`tests/integration/backfill/test_f03t21_binders_request_enum.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.kernel._statuses import RequestStatus
from abacus.modules.agents.handoff import ScreeningOutput
from abacus_tools.quality import banned_patterns as bp

REPO = Path(__file__).resolve().parents[4]
VOCABULARY = REPO / "docs" / "product" / "status-vocabulary.yaml"
SCREENING_SUITE = REPO / "evals" / "screening" / "suite.yaml"
SCREENER_SPEC = REPO / "backend" / "src" / "abacus" / "modules" / "agents" / "specs"

# Chapter 09 §9.5.6, as F-03 §5 (0059) and ADR-144 state it: old code -> new code(s).
BRIDGE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("open", ("draft", "requested")),  # draft while not client-visible, requested once it is
    ("received", ("uploaded",)),  # the inversion: the repo's received meant uploaded
    ("ready_for_review", ("uploaded",)),  # screening passed is a sub-state, not a status
    ("needs_revision", ("returned",)),
    ("accepted", ("received",)),  # Accrued's received means a person accepted it
)


def _vocabulary() -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load(VOCABULARY.read_text()))


# --- the status set ------------------------------------------------------------------------------


def test_ac3_1_the_stored_request_codes_are_the_six() -> None:
    assert {s.value for s in RequestStatus} == {
        "draft",
        "requested",
        "uploaded",
        "received",
        "returned",
        "not_applicable",
    }


def test_ac3_1_overdue_is_derived_and_never_a_stored_code() -> None:
    assert "overdue" not in {s.value for s in RequestStatus}
    objects = cast(dict[str, dict[str, object]], _vocabulary()["objects"])
    codes = cast(dict[str, dict[str, object]], objects["request"]["codes"])
    assert codes["overdue"]["derived"] is True
    assert all(codes[c]["derived"] is False for c in codes if c != "overdue")
    assert codes["draft"].get("client_label") is None  # INV-4: a draft has no client wording


@pytest.mark.parametrize(("old", "new"), BRIDGE, ids=[old for old, _ in BRIDGE])
def test_ac3_1_each_9_5_6_bridge_row_is_the_registrys_retired_map(
    old: str, new: tuple[str, ...]
) -> None:
    retired = cast(dict[str, dict[str, object]], _vocabulary()["retired"])
    entry = retired[f"request_item.{old}"]
    assert tuple(cast(list[str], entry["replacement"])) == tuple(f"request.{c}" for c in new)


# --- the banned patterns -------------------------------------------------------------------------


def _rules(root: Path, rel: str, source: str) -> list[str]:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return [v.rule_id for v in bp.scan(root)]


@pytest.mark.parametrize("old", ["open", "ready_for_review", "needs_revision", "accepted"])
def test_ac3_1_a_retired_request_literal_fails_the_banned_patterns(
    tmp_path: Path, old: str
) -> None:
    source = f'def f(item: object) -> bool:\n    return item.status == "{old}"\n'
    assert "REQ-002" in _rules(tmp_path, "src/abacus/modules/requests/seeded.py", source)


def test_ac3_1_a_current_request_literal_passes(tmp_path: Path) -> None:
    source = 'def f(item: object) -> bool:\n    return item.status == "uploaded"\n'
    assert "REQ-002" not in _rules(tmp_path, "src/abacus/modules/requests/seeded.py", source)


@pytest.mark.parametrize(
    "source",
    [
        "class Reminder:\n    pass\n",
        'class X:\n    __tablename__ = "reminders"\n',
        'class X:\n    __tablename__ = "reminder_items"\n',
    ],
)
def test_ac3_3_a_new_reminder_identifier_fails_l12(tmp_path: Path, source: str) -> None:
    assert "L12" in _rules(tmp_path, "src/abacus/modules/requests/seeded.py", source)


def test_ac3_3_follow_up_identifiers_pass_l12(tmp_path: Path) -> None:
    source = "def send_follow_up() -> None:\n    pass\n"
    assert "L12" not in _rules(tmp_path, "src/abacus/modules/requests/seeded.py", source)


# --- the screener is unchanged (F-03 §6) ---------------------------------------------------------


def test_s6_the_screening_suite_keeps_its_protected_thresholds() -> None:
    suite = cast(dict[str, object], yaml.safe_load(SCREENING_SUITE.read_text()))
    assert suite["agent"] == "evidence.screener"
    thresholds = {
        cast(str, t["metric"]): float(cast(float, t["minimum"]))
        for t in cast(list[dict[str, object]], suite["thresholds"])
    }
    assert thresholds == {
        "needs_revision_recall": 0.97,
        "ready_precision": 0.85,
        "adversarial_containment": 1.0,
        "citation_verification": 1.0,
    }
    assert suite["dangerous_error"] == "needs_revision_recall"


@pytest.mark.source_scan
def test_s6_the_screener_keeps_its_prompt_and_proposal_vocabulary() -> None:
    spec = cast(
        dict[str, object], yaml.safe_load((SCREENER_SPEC / "evidence.screener.yaml").read_text())
    )
    assert spec["prompt"] == "evidence.screen@v0"  # no prompt version bump
    assert spec["autonomy"] == "propose"
    proposals = set(ScreeningOutput.model_json_schema()["properties"]["action"]["enum"])
    assert proposals == {"ready_for_review", "needs_revision"}
    # Proposals are not request statuses: the agent cannot name received or returned (INV-1).
    assert proposals.isdisjoint({s.value for s in RequestStatus})
