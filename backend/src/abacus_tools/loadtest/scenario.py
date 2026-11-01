"""Load-test scenarios as YAML (Q-03-T035; Q-03 E1). One file per profile in `scenarios/`.

A scenario names who calls (one local persona, or several with weights: each virtual user is one
of them for the whole run and plays only that persona's groups), for how long, with how many
virtual users, and what they call: weighted endpoint groups (each a short request sequence,
timed per request under the group's name), SSE streams (time to first event) and Temporal-client
operations at a rate. Targets are optional per group; the pass rule is `stats.verdict`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus_tools.loadtest.bodies import BODIES

SCENARIOS = Path(__file__).resolve().parent / "scenarios"
_NAME = r"^[a-z][a-z0-9_]{0,39}$"
_PATH = r"^/[A-Za-z0-9_\-./?=&%{}]*$"


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Step(_Strict):
    """One request. `path` is relative to the API's base URL; `{name}` takes a `--var`. `body`
    names a generated request body (`bodies.BODIES`, Q-03-T044), sent instead of `json_body`."""

    method: Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    path: Annotated[str, Field(pattern=_PATH, max_length=300)]
    json_body: dict[str, object] | None = None
    body: Annotated[str | None, Field(pattern=_NAME)] = None
    expect: tuple[int, ...] = (200,)
    auth: bool = True
    # N-02-T47: a fresh `Idempotency-Key` per request, for routes that require one (a send).
    idempotency: bool = False

    @model_validator(mode="after")
    def _one_body(self) -> Step:
        if self.body is not None and self.json_body is not None:
            raise ValueError("a step sends json_body or a named body, not both")
        if self.body is not None and self.body not in BODIES:
            raise ValueError(f"no body {self.body!r}; known: {', '.join(sorted(BODIES))}")
        return self


class Group(_Strict):
    """An endpoint group: the unit percentiles are reported by."""

    name: Annotated[str, Field(pattern=_NAME)]
    weight: Annotated[int, Field(ge=1, le=1000)] = 1
    steps: Annotated[tuple[Step, ...], Field(min_length=1, max_length=20)]
    p95_ms: Annotated[float | None, Field(gt=0)] = None


class Persona(_Strict):
    """A local sign-in subject with a weight (Q-03-T044). A virtual user is one persona for the
    whole run; `groups`, when given, are the only groups it plays (a client never plays a staff
    mix)."""

    subject: Annotated[str, Field(min_length=1, max_length=100)]
    weight: Annotated[int, Field(ge=1, le=1000)] = 1
    groups: tuple[Annotated[str, Field(pattern=_NAME)], ...] = ()


class Stream(_Strict):
    """`count` concurrent SSE connections held `hold_seconds`; the sample is time to first
    event."""

    name: Annotated[str, Field(pattern=_NAME)]
    path: Annotated[str, Field(pattern=_PATH, max_length=300)]
    count: Annotated[int, Field(ge=1, le=2000)] = 1
    hold_seconds: Annotated[float, Field(gt=0, le=3600)] = 5.0
    p95_first_event_ms: Annotated[float | None, Field(gt=0)] = None


class TemporalOp(_Strict):
    """Temporal-client load: `count_workflows` (a visibility read) or `start_workflow`."""

    name: Annotated[str, Field(pattern=_NAME)]
    kind: Literal["count_workflows", "start_workflow"]
    rate_per_second: Annotated[float, Field(gt=0, le=500)] = 1.0
    query: Annotated[str | None, Field(max_length=300)] = None
    workflow: Annotated[str | None, Field(max_length=100)] = None
    task_queue: Annotated[str | None, Field(max_length=100)] = None
    args: tuple[object, ...] = ()
    p95_ms: Annotated[float | None, Field(gt=0)] = None

    @model_validator(mode="after")
    def _start_names_its_workflow(self) -> TemporalOp:
        if self.kind == "start_workflow" and not (self.workflow and self.task_queue):
            raise ValueError("start_workflow needs workflow and task_queue")
        return self


class Scenario(_Strict):
    name: Annotated[str, Field(pattern=_NAME)]
    description: Annotated[str, Field(max_length=500)] = ""
    duration_seconds: Annotated[float, Field(gt=0, le=36000)]
    users: Annotated[int, Field(ge=1, le=5000)] = 1
    think_ms: Annotated[float, Field(ge=0, le=60000)] = 0
    # Q-03-T043: virtual users start evenly over the first `ramp_seconds` (a sign-in wave), not
    # all at once.
    ramp_seconds: Annotated[float, Field(ge=0, le=3600)] = 0
    seed: int = 7
    # A local sign-in subject (`abacus_tools.local.seed_dev`); None calls without a token.
    persona: Annotated[str | None, Field(max_length=100)] = None
    # Q-03-T044: weighted personas instead of the one `persona` (never both).
    personas: tuple[Persona, ...] = ()
    max_error_rate: Annotated[float, Field(ge=0, le=1)] = 0.001  # Q-03 E2: below 0.1%
    groups: tuple[Group, ...] = ()
    streams: tuple[Stream, ...] = ()
    temporal: tuple[TemporalOp, ...] = ()

    @model_validator(mode="after")
    def _names_are_unique_and_something_runs(self) -> Scenario:
        names = [g.name for g in self.groups] + [s.name for s in self.streams]
        names += [t.name for t in self.temporal]
        if len(names) != len(set(names)):
            raise ValueError("group, stream and temporal names must be unique")
        if not names:
            raise ValueError("a scenario needs at least one group, stream or temporal operation")
        if self.ramp_seconds >= self.duration_seconds:
            raise ValueError("ramp_seconds must end before the run does")
        if self.personas and self.persona is not None:
            raise ValueError("a scenario names one persona or weighted personas, not both")
        known = {g.name for g in self.groups}
        for persona in self.personas:
            unknown = sorted(set(persona.groups) - known)
            if unknown:
                raise ValueError(f"persona {persona.subject} names unknown groups: {unknown}")
        if self.personas and self.groups:
            played = {g for p in self.personas for g in (p.groups or tuple(known))}
            if played != known:
                raise ValueError(f"no persona plays {sorted(known - played)}")
        return self


def load(source: Path) -> Scenario:
    return Scenario.model_validate(yaml.safe_load(source.read_text(encoding="utf-8")))


def profile(name: str) -> Scenario:
    """The named profile from `scenarios/<name>.yaml`."""
    if not name.replace("_", "").replace("-", "").isalnum():
        raise ValueError(f"profile {name!r} is not a name")
    path = SCENARIOS / f"{name}.yaml"
    if not path.is_file():
        known = sorted(p.stem for p in SCENARIOS.glob("*.yaml"))
        raise ValueError(f"no profile {name!r}; known: {', '.join(known)}")
    return load(path)
