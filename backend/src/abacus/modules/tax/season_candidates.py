"""The season's candidates from the prior year's returns (T-08-T09; S51 partials, TASK-8737;
DEC-5729; SPEC-710 AC-1 to AC-3). Registered with engagements' season setup (engagements never
imports tax).

A candidate is a client with at least one return for the prior tax year that is not on hold:
its forms (one per return), its entities, the prior engagement's office and team carried
forward (preparer: the senior or staff member; reviewer: the manager or reviewer; signer: the
engagement partner), one binder per prior engagement, and a renewal letter. The segment follows
the forms: individual and fiduciary returns are `individuals_trusts`, any entity return makes it
`entities_exempt`. Exception facts stated here: no signer (`signer_missing`) and two prior
engagements for one client (`binder_ambiguous`). The other ENG-07 facts (a seasonal preparer not
started, a bounced contact, offshore consent, walls on an assignee, confirmations, a changed
continuance fact) come from their owners and are not stated yet: such a row reads ready.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.api import (
    SeasonCandidate,
    engagement_retention_facts,
)
from abacus.modules.identity.api import team_of

_INDIVIDUAL_FORMS: Final = frozenset({"1040", "1040-SR", "1040-NR", "1041", "706", "709"})
_RETURNS = text(
    "SELECT engagement_id, client_entity_id, form FROM tax_returns "
    "WHERE tax_year = :y AND coalesce(on_hold, false) = false ORDER BY work_item_id"
)


async def candidates(tenant: TenantContext, tax_year: int) -> list[SeasonCandidate]:
    """The season `tax_year`'s candidates, from the `tax_year - 1` returns."""
    async with tenant_session(tenant) as session:
        rows = [tuple(r) for r in await session.execute(_RETURNS, {"y": tax_year - 1})]
    by_engagement: dict[UUID, list[tuple[UUID | None, str]]] = defaultdict(list)
    for engagement, entity, form in rows:
        if engagement is not None:
            by_engagement[cast(UUID, engagement)].append((cast(UUID | None, entity), str(form)))
    facts = await engagement_retention_facts(tenant, sorted(by_engagement, key=str))
    by_client: dict[UUID, list[UUID]] = defaultdict(list)
    for engagement, f in facts.items():
        if f.office_id is not None:
            by_client[f.client_id].append(engagement)
    out: list[SeasonCandidate] = []
    for client, engagements in sorted(by_client.items(), key=lambda kv: str(kv[0])):
        engagements.sort(key=str)
        prior = engagements[0]
        returns = [r for e in engagements for r in by_engagement[e]]
        forms = tuple(form for _, form in returns)
        team = [(u, str(r)) for u, r in await team_of(tenant.tenant_id, prior)]

        def first(*roles: str, members: list[tuple[UUID, str]] = team) -> UUID | None:
            return next((u for u, r in members if r in roles), None)

        signer = first("engagement_partner")
        flags: set[str] = {"signer_missing"} if signer is None else set()
        if len(engagements) > 1:
            flags.add("binder_ambiguous")
        out.append(
            SeasonCandidate(
                client_id=client,
                office_id=cast(UUID, facts[prior].office_id),
                segment=(
                    "individuals_trusts"
                    if all(f in _INDIVIDUAL_FORMS for f in forms)
                    else "entities_exempt"
                ),
                forms=forms,
                client_entity_ids=tuple(sorted({e for e, _ in returns if e is not None}, key=str)),
                preparer_user_id=first("senior", "staff"),
                reviewer_user_id=first("manager", "reviewer"),
                signer_user_id=signer,
                prior_engagement_id=prior,
                binders=len(engagements),
                letter_kind="renewal",
                flags=frozenset(flags),
            )
        )
    return out


__all__ = ["candidates"]
