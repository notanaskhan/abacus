"""The audit's gate providers (A-04-T43; F-03-T13's slots; DEC-2057). PROTECTED (red).

Every assurance gate an engagement's lifecycle reads is registered here through
`engagements.register_gate_provider`, over facts its owner computes:

- **G4** planning complete: A-04-T18's `g4_facts` (materiality stands, the register is the
  partner's at an unchanged hash, nothing proposed), with its blockers.

A-06-T15 (G5) and A-07-T15 (G6 to G9) move their providers here. A change to this file is a red
diff: it is named in `docs/architecture/protected-paths.md` and needs the security review.
"""

from __future__ import annotations

from abacus.modules.assurance.planning_gate import g4_facts
from abacus.modules.engagements.api import register_gate_provider


def register() -> None:
    register_gate_provider("G4", g4_facts)
