"""The timeline: every scenario fact as a dated event, replayed in order through the owning
module's `api.py` inside `kernel.clock.frozen(event.at)` by the loader (F-04-T13; F-04.15).
Each event's id is stable from its label, so a second load writes nothing, and each carries
`trace_id = scenario:<SCENARIO_VERSION>:<event_id>`."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id

Actor = Literal["system"] | str  # "system", or a seat holder's initials


@dataclass(frozen=True)
class Event:
    label: str  # unique on the timeline; the id derives from it
    at: datetime
    kind: str  # "<module>.<operation>", the service call the loader makes
    actor: Actor
    slice: str
    data: Mapping[str, object] = field(default_factory=dict[str, object])
    client: str | None = None  # the client's name, for holdouts and epochs

    @property
    def id(self) -> str:
        return stable_id(f"event:{self.label}")

    def trace_id(self, version: str) -> str:
        return f"scenario:{version}:{self.id}"


def ordered(events: Iterable[Event]) -> list[Event]:
    """Events by time, then label; duplicate labels are an error."""
    seen: set[str] = set()
    out = sorted(events, key=lambda e: (e.at, e.label))
    for event in out:
        if event.label in seen:
            raise ValueError(f"event label {event.label!r} appears twice")
        if event.at.tzinfo is None:
            raise ValueError(f"event {event.label!r} needs a time zone")
        seen.add(event.label)
    return out
