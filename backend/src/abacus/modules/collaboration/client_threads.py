"""The client comment path (R-02-T22; SPEC-646 AC-31 to AC-34; ADR-236 decision 2, ADR-109).

P-05's own routes refuse client principals. The portal's routes (R-02) call these instead, after
authorising their own action (`client_approval.ask`, `deliverable.comment`, `tcwg.ask`) on the
client's scope:

- `post_client_comment`: a client-authored comment on the anchor's thread. The anchor's provider
  must report it `client_visible`; the thread is opened `shared` on the engagement (a client
  comments only on a shared thread, 0760's trigger), and the text is sealed, plain, 1 to 4,000
  characters, never in an audit or notification row (AC-34).
- `client_comments`: what the client may read on the anchor: the shared threads' comments, except
  under an `author_only` reader policy (POR-15 "Ask the auditor…", AC-33), where a client reads only
  the thread they opened (its locator carries the author), never another member's.

An anchor's reader policy is set where it is registered (`register_client_policy`); the default is
`anchor_readers`. Firm replies use the ordinary `post_comment` on the same thread.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.collaboration import repository as repo
from abacus.modules.collaboration.anchors import (
    AnchorNotShareable,
    Locator,
    anchor_facts,
    locator_key,
    provider_of,
)
from abacus.modules.collaboration.errors import CommentTooLong, EmptyComment
from abacus.modules.collaboration.events import CommentCreated
from abacus.modules.identity.api import AuthContext, Forbidden, names_of

ReaderPolicy = Literal["anchor_readers", "author_only"]
MAX_CLIENT_BODY: Final = 4000
AUTHOR_KEY: Final = "author"
_POLICIES: dict[str, ReaderPolicy] = {}


def register_client_policy(kind: str, policy: ReaderPolicy) -> None:
    """Who among a client's people reads a thread on `kind` (R-02's additive hook on P-05)."""
    known = _POLICIES.get(kind)
    if known is not None and known != policy:
        raise RuntimeError(f"the client reader policy of {kind} is already {known}")
    _POLICIES[kind] = policy


def policy_of(kind: str) -> ReaderPolicy:
    return _POLICIES.get(kind, "anchor_readers")


def _client(ctx: AuthContext) -> None:
    if ctx.client is None or ctx.tenant.actor_kind != "human":
        raise Forbidden("comment.create", "role")


def _clean(body: str) -> str:
    kept = "".join(c for c in body if c in "\n\t" or (c.isprintable() and c not in "‮‭"))
    kept = kept.strip()
    if not kept:
        raise EmptyComment
    if len(kept) > MAX_CLIENT_BODY:
        raise CommentTooLong
    return kept


def _scoped(ctx: AuthContext, kind: str, locator: Locator | None) -> dict[str, str | int]:
    """The thread's locator; under `author_only` the author is part of it, so each client author
    has their own thread and no one else's."""
    found: dict[str, str | int] = dict(locator or {})
    if policy_of(kind) == "author_only":
        found[AUTHOR_KEY] = str(ctx.user_id)
    return found


@dataclass(frozen=True)
class ClientComment:
    id: UUID
    thread_id: UUID
    author_name: str
    author_side: str
    body: str
    created_at: datetime
    locator: Mapping[str, str | int]


async def post_client_comment(
    ctx: AuthContext, *, anchor_kind: str, anchor_id: UUID, locator: Locator | None, body: str
) -> ClientComment:
    _client(ctx)
    scoped = _scoped(ctx, anchor_kind, locator)
    facts = await anchor_facts(ctx, anchor_kind, anchor_id, scoped)
    if facts is None or facts.engagement_id is None:
        raise NotFound("anchor")
    if not facts.client_visible:
        raise AnchorNotShareable(facts={"anchor_kind": anchor_kind})
    text = _clean(body)
    key = locator_key(provider_of(anchor_kind), scoped)
    from abacus.modules.collaboration.threads import _seal  # the module's one sealing rule

    sealed, fingerprint = await _seal(ctx, text)
    async with uow(ctx.tenant) as tx:
        thread = await repo.find_thread(
            tx.session,
            anchor_kind=anchor_kind,
            anchor_id=anchor_id,
            locator_key=key,
            pinned_version_no=None,
        )
        if thread is None:
            thread_id = await repo.insert_thread(
                tx.session,
                tenant_id=ctx.tenant_id,
                engagement_id=facts.engagement_id,
                work_item_id=facts.work_item_id,
                client_id=facts.client_id,
                anchor_kind=anchor_kind,
                anchor_id=anchor_id,
                anchor_locator=scoped or None,
                anchor_locator_key=key,
                opened_on_version_no=facts.version_no,
                pinned_version_no=None,
                created_by=ctx.user_id,
                visibility="shared",
                shared_scope_kind="engagement",
                shared_scope_id=facts.engagement_id,
            )
            await repo.insert_event(
                tx.session,
                tenant_id=ctx.tenant_id,
                engagement_id=facts.engagement_id,
                thread_id=thread_id,
                kind="opened",
                actor_user_id=ctx.user_id,
            )
            tx.record(
                "comment_thread.opened",
                target=Target("comment_thread", thread_id),
                after=Ref(anchor_id=anchor_id),
            )
        elif thread.visibility != "shared":
            raise AnchorNotShareable(facts={"anchor_kind": anchor_kind})
        else:
            thread_id = thread.id
        comment = await repo.insert_comment(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=facts.engagement_id,
            thread_id=thread_id,
            author_user_id=ctx.user_id,
            author_side="client",
            body_sealed=sealed,
            body_fingerprint=fingerprint,
            corrects_comment_id=None,
            citation_ids=[],
        )
        await repo.touch_thread(tx.session, thread_id)
        tx.record(
            "comment.posted",
            target=Target("comment_thread", thread_id),
            after=Ref(comment_id=comment.id, body=fingerprint),
        )
        tx.emit(
            CommentCreated(
                comment_id=comment.id,
                thread_id=thread_id,
                anchor_kind=anchor_kind,
                anchor_id=anchor_id,
                engagement_id=facts.engagement_id,
            )
        )
    name = (await names_of([ctx.user_id])).get(ctx.user_id, "")
    return ClientComment(comment.id, thread_id, name, "client", text, comment.created_at, scoped)


async def client_comments(
    ctx: AuthContext, *, anchor_kind: str, anchor_id: UUID, locator: Locator | None = None
) -> list[ClientComment]:
    """The anchor's comments a client may read, oldest first; redacted comments are left out."""
    _client(ctx)
    probe = _scoped(ctx, anchor_kind, locator)
    facts = await anchor_facts(ctx, anchor_kind, anchor_id, probe)
    if facts is None or not facts.client_visible:
        raise NotFound("anchor")
    author_only = policy_of(anchor_kind) == "author_only"
    async with tenant_session(ctx.tenant) as session:
        threads = [
            t
            for t in await repo.shared_threads_on_anchor(session, anchor_kind, anchor_id)
            if (not author_only or (t.anchor_locator or {}).get(AUTHOR_KEY) == str(ctx.user_id))
        ]
        rows = await repo.comments_of_threads(session, [t.id for t in threads])
    by_thread = {t.id: t for t in threads}
    people = sorted({c.author_user_id for c, _ in rows}, key=str)
    names = await names_of(people) if people else {}
    out: list[ClientComment] = []
    for comment, redaction in rows:
        if redaction is not None:
            continue
        text = (
            await open_sealed(ctx.tenant_id, comment.body_sealed, comment.body_fingerprint)
        ).decode()
        out.append(
            ClientComment(
                comment.id,
                comment.thread_id,
                names.get(comment.author_user_id, ""),
                comment.author_side,
                text,
                comment.created_at,
                dict(by_thread[comment.thread_id].anchor_locator or {}),
            )
        )
    return out


__all__ = [
    "AUTHOR_KEY",
    "ClientComment",
    "ReaderPolicy",
    "client_comments",
    "policy_of",
    "post_client_comment",
    "register_client_policy",
]
