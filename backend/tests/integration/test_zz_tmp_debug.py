from __future__ import annotations

from .review_support import person_ctx
from .test_p04t24_proposals import Cast, _k1, approve_proposal, engines, team  # noqa: F401


async def test_debug(team: Cast) -> None:
    proposal, _ = await _k1(team, uncited=False)
    await approve_proposal(person_ctx(team["samuel"]), proposal, seen_version=1, edits=[])
