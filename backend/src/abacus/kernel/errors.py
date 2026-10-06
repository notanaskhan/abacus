"""Errors every module may raise; the API maps them to responses (abacus.api.app)."""

from __future__ import annotations

from typing import ClassVar


class NotFound(Exception):
    """The resource doesn't exist in the active tenant: 404. Row-level security makes another
    firm's rows indistinguishable from missing ones, so existence never leaks across firms."""


class DomainConflict(Exception):
    """The request conflicts with the resource's state: 409 with the class's fixed `code` (never
    a message from the request or the database)."""

    code: ClassVar[str] = "conflict"


class ServiceUnavailable(Exception):
    """A dependency isn't reachable right now: 503."""
