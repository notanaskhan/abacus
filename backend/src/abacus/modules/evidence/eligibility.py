"""Destruction eligibility, pure (Q-05-T11; TASK-8713; SPEC-711 AC-21, AC-22; DEC-5709).

An evidence version is eligible once the later of its policy expiry (the firm's policy or the
legal floor, `retain_until_for`) and the retain-until observed on its stored object has passed;
never while a legal hold covers it, never inside an archive that is not locked, never without a
policy (no expiry, no destruction). Storage is content addressed, so one object can back several
versions: an object shared with any version that is not eligible stays out of the batch whole.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class VersionFacts:
    version_id: UUID
    object_key: str
    object_version_id: str
    record_type: str
    client_id: UUID | None
    policy_until: datetime | None
    observed_until: datetime | None
    held: bool
    unlocked_archive: bool


def eligible_at(f: VersionFacts) -> datetime | None:
    """The later of the policy's expiry and the object's observed retain-until."""
    if f.policy_until is None:
        return None
    if f.observed_until is None:
        return f.policy_until
    return max(f.policy_until, f.observed_until)


def eligible(f: VersionFacts, now: datetime) -> bool:
    at = eligible_at(f)
    return at is not None and at <= now and not f.held and not f.unlocked_archive


@dataclass(frozen=True, slots=True)
class Chosen:
    items: tuple[VersionFacts, ...]
    held: int
    shared_excluded: int

    @property
    def clients(self) -> int:
        return len({f.client_id for f in self.items if f.client_id is not None})


def select(facts: Iterable[VersionFacts], now: datetime) -> Chosen:
    """The batch: every eligible version whose object no non-eligible version also uses."""
    all_facts: Sequence[VersionFacts] = list(facts)
    blocked_keys = {f.object_key for f in all_facts if not eligible(f, now)}
    chosen = [f for f in all_facts if eligible(f, now) and f.object_key not in blocked_keys]
    shared = sum(1 for f in all_facts if eligible(f, now) and f.object_key in blocked_keys)
    held = sum(1 for f in all_facts if f.held and (eligible_at(f) or now) <= now)
    return Chosen(tuple(chosen), held, shared)


def quarter_ref(now: datetime) -> str:
    """The batch's reference: the calendar quarter of the assembly (2026-Q3)."""
    return f"{now.year:04d}-Q{(now.month - 1) // 3 + 1}"


__all__ = ["Chosen", "VersionFacts", "eligible", "eligible_at", "quarter_ref", "select"]
