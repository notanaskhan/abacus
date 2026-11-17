"""Relationship error codes (SPEC-702 F8, §4; T-06-T03, DEC-5511): plain-words 422s."""

from __future__ import annotations

from abacus.kernel.errors import DomainInvalid


class RelationshipSelfEdge(DomainInvalid):
    """An entity cannot be related to itself."""

    code = "relationship_self_edge"


class RelationshipPercentExceeds(DomainInvalid):
    """Ownership into one entity would exceed 100 percent (`facts.total_bp`)."""

    code = "relationship_percent_exceeds"
