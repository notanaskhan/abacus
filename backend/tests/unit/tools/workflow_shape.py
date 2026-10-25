"""Reading a GitHub Actions workflow's shape for tests (Q-01-T11, T18, T34, T38): its triggers
(YAML reads the bare `on` key as True), jobs, steps and run scripts, never by running it."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import yaml

REPO = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO / ".github" / "workflows"
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")

Mapping = dict[str, object]


def load(name: str) -> Mapping:
    return cast(Mapping, yaml.safe_load((WORKFLOWS / name).read_text()))


def triggers(workflow: Mapping) -> Mapping:
    raw = workflow.get("on", workflow.get(True))  # pyright: ignore[reportArgumentType] -- YAML 1.1 reads `on` as True
    return cast(Mapping, raw if isinstance(raw, dict) else {str(raw): None})


def jobs(workflow: Mapping) -> dict[str, Mapping]:
    return cast(dict[str, Mapping], workflow["jobs"])


def steps(job: Mapping) -> list[Mapping]:
    return cast(list[Mapping], job.get("steps", []))


def step(job: Mapping, name: str) -> Mapping:
    found = [s for s in steps(job) if s.get("name") == name]
    assert len(found) == 1, f"one step named {name!r}"
    return found[0]


def index(job: Mapping, name: str) -> int:
    return [s.get("name") for s in steps(job)].index(name)


def runs(job: Mapping) -> str:
    return "\n".join(str(s.get("run", "")) for s in steps(job))


def uses(workflow: Mapping) -> list[str]:
    return [
        str(s["uses"]).split(" ")[0]
        for job in jobs(workflow).values()
        for s in steps(job)
        if "uses" in s
    ]


def text(name: str) -> str:
    return (WORKFLOWS / name).read_text()
