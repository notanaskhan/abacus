"""Incident decisions' error code (G-02-T02 declaration; SPEC-349 AC-22). Raised by G-02-T18."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict


class DeciderMustDiffer(DomainConflict):
    """An incident decision needs two different people, one partner and the QI (AC-22)."""

    code = "decider_must_differ"
