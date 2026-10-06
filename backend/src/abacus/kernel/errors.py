"""Errors every module may raise; the API maps them to responses (abacus.api.app)."""

from __future__ import annotations


class NotFound(Exception):
    """The resource doesn't exist in the active tenant: 404. Row-level security makes another
    firm's rows indistinguishable from missing ones, so existence never leaks across firms."""
