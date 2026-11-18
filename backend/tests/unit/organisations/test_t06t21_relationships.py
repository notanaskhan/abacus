"""T-06-T21 (SPEC-702 F8; DEC-5632): the ownership cap in code, on every day an edge is in force.
The DB paths (walls, events, versions) run in the end-pass integration suite."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from abacus.modules.organisations.relationships import Edge, cap_exceeded

D = Decimal
E = UUID("00000000-0000-4000-8000-0000000000e1")


def test_sixty_plus_forty_fills_and_one_more_percent_exceeds() -> None:
    existing = [Edge(E, "owner_of", D("60"), date(2024, 1, 1), None)]
    assert not cap_exceeded(existing, Edge(E, "lp_of", D("40"), date(2025, 1, 1), None))
    full = [*existing, Edge(E, "lp_of", D("40"), date(2025, 1, 1), None)]
    assert cap_exceeded(full, Edge(E, "gp_of", D("1"), date(2025, 7, 1), None))


def test_an_ended_period_frees_its_percent_for_later_days() -> None:
    existing = [Edge(E, "owner_of", D("60"), date(2024, 1, 1), date(2024, 12, 31))]
    assert not cap_exceeded(existing, Edge(E, "owner_of", D("100"), date(2025, 1, 1), None))


def test_non_ownership_edges_never_count() -> None:
    existing = [Edge(E, "owner_of", D("100"), date(2024, 1, 1), None)]
    assert not cap_exceeded(existing, Edge(E, "trustee_of", None, date(2025, 1, 1), None))
