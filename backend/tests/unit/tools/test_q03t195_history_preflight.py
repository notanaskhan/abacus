"""Q-03-T195 (ADR-090): the deploy pre-flight for replay histories. Every registered workflow has a
recorded history, or is named below as a known gap. A new workflow with neither fails here, so the
list only shrinks. Stage 2's `tests/workflows/test_*_replay.py` replay what's recorded."""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Final

from temporalio import workflow

from abacus.worker.__main__ import MODULES

HISTORIES: Final = Path(__file__).resolve().parents[2] / "workflows" / "histories"

# Recording needs Docker (`abacus_tools.workflows.record_*`). A workflow named here needs one.
KNOWN_GAPS: Final[frozenset[str]] = frozenset()  # S29 leftovers (TASK-6008): none left


# A workflow whose recorded histories carry a shorter name than its declared one (S29 leftovers,
# TASK-6008): the name, and the history stem its recorder writes.
ALIASES: Final[dict[str, str]] = {
    "AuditLabelIndexer": "audit-labels",
    "DrainSesEvents": "ses-drain",
    "IncidentClockReminders": "incident-reminders",
    "IntakeWithdrawalPurge": "intake-purge",
    "evidence_withdrawal_purge": "withdrawal-purge",
}


def _slug(name: str) -> str:
    dashed = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name).replace("_", "-").replace(".", "-")
    return dashed.lower().removesuffix("-workflow")


def _registered() -> set[str]:
    names: set[str] = set()
    for module in MODULES:
        for found in getattr(module, "WORKFLOWS", {}):
            if inspect.isclass(found):
                defn = workflow._Definition.from_class(
                    found
                )  # the SDK's only reader of a declared name
                if defn is not None and defn.name is not None:
                    names.add(defn.name)
    return names


def _recorded() -> set[str]:
    return {re.sub(r"-v\d+.*$", "", p.stem) for p in HISTORIES.glob("*.json")}


def _has_history(name: str, recorded: set[str]) -> bool:
    """A history's stem may name the workflow shortly (`access-end-v1-swept`, AccessEndSweep)."""
    slug = ALIASES.get(name, _slug(name))
    return any(slug == r or slug.startswith(f"{r}-") or r.startswith(f"{slug}-") for r in recorded)


def test_every_workflow_has_a_history_or_is_a_named_gap() -> None:
    recorded = _recorded()
    assert {n for n in _registered() if not _has_history(n, recorded)} - KNOWN_GAPS == set()


def test_the_gap_list_only_shrinks() -> None:
    recorded = _recorded()
    assert {n for n in KNOWN_GAPS if _has_history(n, recorded)} == set()


def test_every_alias_names_a_registered_workflow_and_a_recorded_history() -> None:
    recorded, registered = _recorded(), _registered()
    assert set(ALIASES) <= registered
    assert set(ALIASES.values()) <= recorded
