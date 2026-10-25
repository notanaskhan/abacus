"""The output-check registry (P-09-T04; DE-3, DE-5, DE-6): additive, and run only on the
structured final turns of runtime v2's `converse()` (P-10). `call()` and the live screener,
matcher and upload-reviewer paths never consult it.

An owner registers a check for an output kind (the agents module registers AgentBlocks). A
check returns None when the output passes, or a `CheckFailure` (a code and a path, never the
offending text). The turn loop gives the model one repair with the failure's code and path;
if the repaired turn fails too, the output is settled as `unsupported` and shown as such
(P-09 §3.7). Unknown kinds fail closed: no check registered means no output shown.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal

REPAIRS: Final = 1


@dataclass(frozen=True)
class CheckFailure:
    code: str
    where: str


type OutputCheck = Callable[[object], CheckFailure | None]

_CHECKS: dict[str, OutputCheck] = {}


def register_output_check(kind: str, check: OutputCheck) -> None:
    """One check per kind; registering the same function again is a no-op (module reloads)."""
    found = _CHECKS.get(kind)
    if found is not None and (found.__module__, found.__qualname__) != (
        check.__module__,
        check.__qualname__,
    ):
        raise ValueError(f"output kind {kind!r} already has a check")
    _CHECKS[kind] = check


def run_output_check(kind: str, output: object) -> CheckFailure | None:
    check = _CHECKS.get(kind)
    if check is None:
        return CheckFailure("no_check", kind)
    return check(output)


@dataclass(frozen=True)
class Settled:
    """What a final turn settles as: `passed` (show it), `repair` (ask once more with the
    failure), or `unsupported` (show the Unsupported state, never the output)."""

    outcome: Literal["passed", "repair", "unsupported"]
    failure: CheckFailure | None
    repairs_used: int


def settle(kind: str, output: object, repairs_used: int) -> Settled:
    failure = run_output_check(kind, output)
    if failure is None:
        return Settled("passed", None, repairs_used)
    if repairs_used < REPAIRS and failure.code != "no_check":
        return Settled("repair", failure, repairs_used + 1)
    return Settled("unsupported", failure, repairs_used)


def registered_kinds() -> frozenset[str]:
    return frozenset(_CHECKS)


__all__ = [
    "REPAIRS",
    "CheckFailure",
    "OutputCheck",
    "Settled",
    "register_output_check",
    "registered_kinds",
    "run_output_check",
    "settle",
]
