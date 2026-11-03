"""The audit's gate providers (A-04-T43; F-03-T13's slots; DEC-2057). PROTECTED (red).

Every assurance gate an engagement's lifecycle reads is registered here through
`engagements.register_gate_provider`, over facts its owner computes:

- **G4** planning complete: A-04-T18's `g4_facts` (materiality stands, the register is the
  partner's at an unchanged hash, nothing proposed), with its blockers.
- **G5** review complete (A-06-T15, DEC-2215): met only when every registered reviewable on the
  engagement has each of its required levels (the owner's facts carry K-02's
  `required_review_levels`) signed on its current content and not stale, and no open or
  responded review note remains. Blockers name the objects: `unsigned:<type>:<id>:L<n>`,
  `stale:<type>:<id>:L<n>`, `review_note:<id>`. A provider that fails leaves G5 unmet
  (`review_unavailable`), never met. It replaces the review module's SPEC-313 provider.

A-07-T15 (G6 to G9) moves its providers here. A change to this file is a red diff: it is named
in `docs/architecture/protected-paths.md` and needs the security review.
"""

from __future__ import annotations

from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.assurance.planning_gate import g4_facts
from abacus.modules.engagements.api import GateFact, register_gate_provider, replace_gate_provider
from abacus.modules.review.api import (
    open_notes,
    reviewable_facts,
    reviewables_of,
    sign_off_states,
)


async def g5_blockers(tenant: TenantContext, engagement_id: UUID) -> list[str]:
    reviewables = await reviewables_of(tenant, engagement_id)
    if not reviewables:
        return ["no_reviewables"]
    blockers: list[str] = []
    for r in reviewables:
        facts = await reviewable_facts(tenant, r.target_type, r.target_id)
        states = await sign_off_states(
            tenant, r.target_type, [r.target_id], {r.target_id: facts.content_hash}
        )
        by_level = {s.level: s for s in states[r.target_id]}
        for level in facts.required_levels:
            state = by_level.get(level)
            if state is None or state.signed_by is None:
                blockers.append(f"unsigned:{r.target_type}:{r.target_id}:L{level}")
            elif state.stale:
                blockers.append(f"stale:{r.target_type}:{r.target_id}:L{level}")
    blockers.extend(
        f"review_note:{note_id}" for note_id, _ in await open_notes(tenant, engagement_id)
    )
    return blockers


async def g5_facts(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    try:
        blockers = await g5_blockers(tenant, engagement_id)
    except Exception:  # a provider that fails leaves the gate unmet, never met
        return GateFact(met=False, blockers=("review_unavailable",))
    return GateFact(met=not blockers, blockers=tuple(blockers))


def register() -> None:
    register_gate_provider("G4", g4_facts)
    replace_gate_provider("G5", g5_facts)
