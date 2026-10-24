"""Errors every module may raise; the API maps them to responses (abacus.api.app).

A conflict or an invalid request answers with its class's fixed `code` from the catalogue
(`docs/architecture/error-codes.yaml`) and, optionally, identifier-only `facts` (ADR-139):
identifiers, registry codes, integers and booleans, never free text. `{"detail": "gate_unmet",
"facts": {"gate": "G3"}}`, never "Gate G3 failed for client Acme Corp".
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import ClassVar, Final, cast

Fact = str | int | bool

# A fact key is a snake_case name; a string fact is an identifier or a code: no spaces, no
# sentences, at most 64 characters (a UUID, "G3", "AJE-06", "in_review", "evidence.read").
_FACT_KEY: Final = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_FACT_TEXT: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")


class FactsNotIdentifiers(ValueError):
    """An error's facts held free text: a developer mistake, caught before any response."""


def check_facts(facts: Mapping[str, object]) -> dict[str, Fact]:
    """The facts, if every key is a name and each value an identifier, a code, an int or a bool."""
    checked: dict[str, Fact] = {}
    for key, value in facts.items():
        if not _FACT_KEY.fullmatch(key):
            raise FactsNotIdentifiers(f"fact key {key!r} is not a snake_case name")
        identifier = isinstance(value, str) and _FACT_TEXT.fullmatch(value) is not None
        if not (isinstance(value, bool | int) or identifier):
            raise FactsNotIdentifiers(f"fact {key!r} holds something other than an identifier")
        checked[key] = cast(Fact, value)  # narrowed above: a bool, an int or an identifier
    return checked


class _Coded(Exception):
    """An error with a catalogue code and identifier-only facts."""

    code: ClassVar[str] = "error"

    def __init__(self, *args: object, facts: Mapping[str, object] | None = None) -> None:
        super().__init__(*args)
        self.facts: dict[str, Fact] = check_facts(facts or {})


class NotFound(Exception):
    """The resource doesn't exist in the active tenant: 404. Row-level security makes another
    firm's rows indistinguishable from missing ones, so existence never leaks across firms."""


class DomainConflict(_Coded):
    """The request conflicts with the resource's state: 409 with the class's fixed `code` (never
    a message from the request or the database)."""

    code: ClassVar[str] = "conflict"


class DomainInvalid(_Coded):
    """The request is well-formed but breaks a domain rule: 422 with the class's fixed `code`
    (never a message from the request or the database)."""

    code: ClassVar[str] = "invalid"


class DomainForbidden(_Coded):
    """The firm may not use this at all (an entitlement it doesn't hold): 403 with the class's
    fixed `code` and identifier-only facts, so the UI can name the reason (F-03-T28)."""

    code: ClassVar[str] = "forbidden"


class DomainRateLimited(_Coded):
    """Too many of these in a rolling window: 429 with the class's fixed `code`, identifier-only
    facts (`limit`, `retry_after` in seconds) and a `Retry-After` header (DEC-227)."""

    code: ClassVar[str] = "rate_limited"


class ServiceUnavailable(Exception):
    """A dependency isn't reachable right now: 503."""


class NotImplementedYet(Exception):
    """A contract stub whose implementation hasn't landed (contract first, AGENTS 15): 501
    `not_implemented`. Raised only behind the contract's flag."""
