"""From service views to the contract's shapes (P-05-T05, T06). Names are resolved at read time
(never stored); a person the reader may not see is still named by the display name only."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from uuid import UUID

from abacus.modules.collaboration import contract as c
from abacus.modules.collaboration.anchors import AnchorFacts
from abacus.modules.collaboration.candidates import Candidate, initials
from abacus.modules.collaboration.threads import ThreadView
from abacus.modules.identity.api import names_of


async def people(ids: Iterable[UUID]) -> dict[UUID, c.PersonRefOut]:
    wanted = sorted(set(ids), key=str)
    names = await names_of(wanted)
    return {
        u: c.PersonRefOut(user_id=u, name=names.get(u, ""), initials=initials(names.get(u, "")))
        for u in wanted
    }


def anchor_out(
    kind: str, anchor_id: UUID, locator: dict[str, str | int] | None, facts: AnchorFacts
) -> c.AnchorFactsOut:
    return c.AnchorFactsOut(
        anchor_kind=kind,
        anchor_id=anchor_id,
        locator=locator,
        label=facts.label,
        engagement_id=facts.engagement_id,
        client_visible=facts.client_visible,
    )


def _thread_people(views: Sequence[ThreadView]) -> set[UUID]:
    found: set[UUID] = set()
    for v in views:
        for comment in v.comments:
            found.add(comment.author_user_id)
            if comment.redaction is not None:
                found.add(comment.redaction.redacted_by)
        found |= {e.actor_user_id for e in v.events}
    return found


async def threads_out(views: Sequence[ThreadView]) -> list[c.ThreadOut]:
    named = await people(_thread_people(views))
    out: list[c.ThreadOut] = []
    for v in views:
        comments = [
            c.ThreadCommentOut(
                id=m.id,
                author=named[m.author_user_id],
                author_side="client" if m.author_side == "client" else "firm",
                body=m.body,
                corrects_comment_id=m.corrects_comment_id,
                corrected_by_comment_id=m.corrected_by_comment_id,
                mentioned_user_ids=m.mentioned_user_ids,
                citation_ids=m.citation_ids,
                redaction=None
                if m.redaction is None
                else c.ThreadRedactionOut(
                    redacted_by=named[m.redaction.redacted_by],
                    redacted_at=m.redaction.redacted_at,
                    reason=m.redaction.reason,
                ),
                created_at=m.created_at,
            )
            for m in v.comments
        ]
        events = [
            c.ThreadEventOut(
                kind=e.kind,  # pyright: ignore[reportArgumentType] -- the table's CHECK
                actor=named[e.actor_user_id],
                ref_type=e.ref_type,  # pyright: ignore[reportArgumentType] -- the table's CHECK
                ref_id=e.ref_id,
                created_at=e.created_at,
            )
            for e in v.events
        ]
        out.append(
            c.ThreadOut(
                id=v.id,
                anchor=anchor_out(v.anchor_kind, v.anchor_id, v.locator, v.facts),
                engagement_id=v.engagement_id,
                status=v.status,  # pyright: ignore[reportArgumentType] -- the table's CHECK
                visibility="shared" if v.visibility == "shared" else "internal",
                opened_on_version_no=v.opened_on_version_no,
                pinned_version_no=v.pinned_version_no,
                comment_count=len(v.comments),
                unread=v.unread,
                muted=v.muted,
                last_comment_at=v.last_comment_at,
                comments=comments,
                events=events,
                allowed_actions=v.allowed_actions,  # pyright: ignore[reportArgumentType] -- THREAD_ACTIONS
            )
        )
    return out


def candidate_out(found: Candidate) -> c.PersonCandidateOut:
    return c.PersonCandidateOut(
        user_id=found.user_id,
        name=found.name,
        initials=initials(found.name),
        title=found.title,
        is_self=found.is_self,
        selectable=found.selectable,
        reason="not_on_engagement" if found.reason == "not_on_engagement" else None,
    )
