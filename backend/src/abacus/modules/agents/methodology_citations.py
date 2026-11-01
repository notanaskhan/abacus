"""The `methodology_step` citable (K-01-T12; C4 §3.1, ADR-166; K-01 §3.4).

Registered from `agents`, which may import both evidence and methodology (methodology imports
only identity and platform). Locator `{template_version_id, step_key}`; the match id is
`step:<step_key>@v<n>` and `source_version` the version label, so a citation to BH-EBP-110 step 4
at v3 verifies against v3's step, and the same key at v2 resolves to its v2 step (the key is the
lineage anchor, K-01-T05).

- The verifier authorises `methodology.read` at the actor's firm before it reads (a refusal is
  `source_not_visible`); a version or key that has no step is `source_not_found`. An engagement
  agent never relates to the firm (identity's rule), so it authorises on its own engagement and
  may cite only the version that engagement pins (A-04-T11's section drafter; DEC-1868).
- A claimed quote must be in the step text, contiguously, compared space- and case-folded.
- Display names the program and step by code and number: "BH-EBP-110 · step 4".
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.errors import NotFound
from abacus.kernel.uow import UnitOfWork
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    CitationLabel,
    CitationVerdict,
    normalised_text,
    register_citable,
)
from abacus.modules.identity.api import Actor, AgentContext, Forbidden, Resource, authorise
from abacus.modules.methodology.api import step_at

VERIFIER_VERSION: Final = "v1"
SOURCE: Final = "methodology_template_version"
NIL: Final = UUID(int=0)
_KEY: Final = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")


def _locator(locator: Mapping[str, object]) -> tuple[UUID, str] | None:
    raw_id, key = locator.get("template_version_id"), locator.get("step_key")
    if not isinstance(raw_id, str) or not isinstance(key, str) or not _KEY.fullmatch(key):
        return None
    try:
        return UUID(raw_id), key
    except ValueError:
        return None


async def verify_methodology_step(
    tx: UnitOfWork, actor: Actor, claim: CitationClaim, anchor: CitationAnchor
) -> CitationVerdict:
    parsed = _locator(claim.locator)
    if parsed is None:
        return CitationVerdict("locator_invalid", SOURCE, NIL)
    version_id, key = parsed
    try:
        if isinstance(actor, AgentContext) and actor.engagement_id is not None:
            ref = await get_ref(actor, actor.engagement_id)
            if ref.methodology_version_id != version_id:
                return CitationVerdict("source_not_visible", SOURCE, version_id)
            await authorise(actor, "methodology.read", ref.resource())
        else:
            await authorise(actor, "methodology.read", Resource.firm(actor.tenant.tenant_id))
    except (Forbidden, NotFound):
        return CitationVerdict("source_not_visible", SOURCE, version_id)
    found = await step_at(tx.session, key, version_id)
    if found is None:
        return CitationVerdict("source_not_found", SOURCE, version_id)
    quote_sha: bytes | None = None
    if claim.quote is not None:
        folded = normalised_text(claim.quote)
        if folded == "" or folded not in normalised_text(found.text):
            return CitationVerdict("quote_not_found", SOURCE, version_id)
        quote_sha = hashlib.sha256(folded.encode()).digest()
    return CitationVerdict(
        None,
        SOURCE,
        version_id,
        locator={"template_version_id": str(version_id), "step_key": key},
        source_version=f"v{found.version}",
        match_id=f"step:{found.anchor}",
        quote_sha256=quote_sha,
    )


async def display_methodology_step(
    session: AsyncSession, locator: Mapping[str, object], engagement_id: UUID | None
) -> CitationLabel:
    """Firm content, not an engagement's: shown wherever the citation is readable."""
    parsed = _locator(locator)
    found = None if parsed is None else await step_at(session, parsed[1], parsed[0])
    if found is None:
        return CitationLabel("Methodology", "step no longer available")
    return CitationLabel(found.program_code, f"step {found.number} · {found.anchor}")


def register_methodology_step() -> None:
    register_citable(
        "methodology_step",
        verify_methodology_step,
        display_methodology_step,
        version=VERIFIER_VERSION,
    )
