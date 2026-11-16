"""The client's authorization for confirmations (A-08-T18; A-08 §3 F4; SPEC-657 AC-6.3; AUD-14;
DEC-5324; red).

- **One C7 envelope per request** (purpose `confirmation_authorization`, general family): the
  firm's authorization letter (an evidence version on the engagement) for the client's named
  signer, covering the Draft confirmations named. Each moves to Authorization requested and
  cannot send until the envelope completes.
- **Completion** (`envelope.completed` for this source): the authorization is stamped and each of
  its confirmations still awaiting it moves back to Draft with an `authorized` event, so it sends.
- Only a person requests it (the matrix denies the agent); the letter is the firm's document,
  never drafted here, and nothing here reaches the client's systems.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance.confirmations_service import (
    _person,  # pyright: ignore[reportPrivateUsage] -- the module's own person check
    _scope,  # pyright: ignore[reportPrivateUsage] -- the module's own scope check
)
from abacus.modules.assurance.events import ConfirmationAuthorizationSigned
from abacus.modules.identity.api import AuthContext
from abacus.modules.signatures.api import SourceDraft

SOURCE: Final = "confirmation_authorization"
ACTION: Final = "confirmation.request_authorization"
_ACTOR: Final = "assurance:confirmation_authorization"


class NotAuthorizable(DomainConflict):
    code = "confirmation_not_authorizable"


class LetterNotOnEngagement(DomainInvalid):
    code = "authorization_letter_invalid"


_DRAFTS: Final = text(
    "SELECT id, status FROM confirmations WHERE work_item_id = :w AND id = ANY(:ids) FOR UPDATE"
)
_INSERT: Final = text(
    "INSERT INTO confirmation_authorizations (tenant_id, engagement_id, work_item_id, "
    "letter_evidence_version_id, signer_contact_id, requested_by) VALUES (:t, :e, :w, :v, :s, :u) "
    "RETURNING id"
)
_ITEM: Final = text(
    "INSERT INTO confirmation_authorization_items (tenant_id, authorization_id, confirmation_id) "
    "VALUES (:t, :a, :c)"
)
_MOVE: Final = text(
    "UPDATE confirmations SET status = :s, row_version = row_version + 1 "
    "WHERE id = :c AND status = :from"
)
_EVENT: Final = text(
    "INSERT INTO confirmation_events (tenant_id, confirmation_id, kind, actor_kind, actor_id) "
    "VALUES (:t, :c, :k, :ak, :a)"
)
_ENVELOPE: Final = text(
    "UPDATE confirmation_authorizations SET envelope_id = :env "
    "WHERE id = :a AND envelope_id IS NULL"
)
_ROW: Final = text(
    "SELECT id, engagement_id, work_item_id, letter_evidence_version_id, signer_contact_id, "
    "completed_at FROM confirmation_authorizations WHERE id = :a"
)
_COVERED: Final = text(
    "SELECT confirmation_id FROM confirmation_authorization_items WHERE authorization_id = :a "
    "ORDER BY confirmation_id"
)
_COMPLETE: Final = text(
    "UPDATE confirmation_authorizations SET completed_at = clock_timestamp() "
    "WHERE id = :a AND completed_at IS NULL RETURNING engagement_id, requested_by"
)


async def request(
    ctx: AuthContext,
    work_item_id: UUID,
    confirmation_ids: Sequence[UUID],
    signer_contact_id: UUID,
    letter_evidence_version_id: UUID,
) -> UUID:
    """The envelope's id; 409 `confirmation_not_authorizable` unless every one named is Draft on
    the work item, 422 `authorization_letter_invalid` for a letter not on its engagement."""
    _person(ctx, ACTION)
    engagement_id = await _scope(ctx, work_item_id, ACTION)
    from abacus.modules.evidence.api import version_file_facts
    from abacus.modules.signatures.api import create_draft

    letter = await version_file_facts(ctx.tenant, letter_evidence_version_id)
    if letter.engagement_id != engagement_id:
        raise LetterNotOnEngagement(facts={"field": "letter_evidence_version_id"})
    wanted = sorted(set(confirmation_ids), key=str)
    async with uow(ctx.tenant) as tx:
        rows = (await tx.session.execute(_DRAFTS, {"w": work_item_id, "ids": wanted})).all()
        found = {cast(UUID, r[0]): str(r[1]) for r in rows}
        refused = [c for c in wanted if found.get(c) != "draft"]
        if refused:
            raise NotAuthorizable(facts={"confirmation_id": str(refused[0])})
        authorization = cast(
            UUID,
            await tx.session.scalar(
                _INSERT,
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "v": letter_evidence_version_id,
                    "s": signer_contact_id,
                    "u": ctx.user_id,
                },
            ),
        )
        for confirmation in wanted:
            await tx.session.execute(
                _ITEM, {"t": ctx.tenant_id, "a": authorization, "c": confirmation}
            )
            await tx.session.execute(
                _MOVE, {"s": "authorization_requested", "c": confirmation, "from": "draft"}
            )
            await tx.session.execute(
                _EVENT,
                {
                    "t": ctx.tenant_id,
                    "c": confirmation,
                    "k": "authorization_requested",
                    "ak": "human",
                    "a": str(ctx.user_id),
                },
            )
        tx.record(
            "confirmation.authorization_requested",
            target=Target("confirmation_authorization", authorization),
            after=Ref(n=len(wanted)),
        )
    envelope_id = await create_draft(ctx, SOURCE, authorization)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_ENVELOPE, {"env": envelope_id, "a": authorization})
        tx.record(
            "confirmation.authorization_drafted",
            target=Target("confirmation_authorization", authorization),
            after=Ref(envelope_id=envelope_id),
        )
    return envelope_id


async def authorization_draft(ctx: AuthContext, authorization_id: UUID) -> SourceDraft:
    """C7's draft for one authorization: the letter for the named signer (email code), purpose
    `confirmation_authorization` in the general family."""
    from abacus.modules.engagements.api import get_ref
    from abacus.modules.evidence.api import version_file_facts, version_fingerprint
    from abacus.modules.signatures.api import SourceDocument, SourceSigner

    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_ROW, {"a": authorization_id})).mappings().first()
    if row is None:
        raise NotFound("confirmation_authorization")
    await _scope(ctx, cast(UUID, row["work_item_id"]), ACTION)
    version = cast(UUID, row["letter_evidence_version_id"])
    sha = await version_fingerprint(ctx.tenant, version)
    if sha is None:
        raise NotFound("evidence_version")
    facts = await version_file_facts(ctx.tenant, version)
    engagement = cast(UUID, row["engagement_id"])
    return SourceDraft(
        purpose=SOURCE,
        policy_family="general",
        client_id=(await get_ref(ctx, engagement)).client_id,
        title=facts.file_name,
        documents=(
            SourceDocument(
                sha256=sha,
                evidence_version_id=version,
                page_count=facts.page_count or None,
                source_ref=f"{SOURCE}:{authorization_id}",
            ),
        ),
        signers=(
            SourceSigner(
                identity_method="email_code", contact_id=cast(UUID, row["signer_contact_id"])
            ),
        ),
        engagement_id=engagement,
        work_item_id=cast(UUID, row["work_item_id"]),
    )


async def authorization_documents(ctx: AuthContext, authorization_id: UUID) -> list[object]:
    return list((await authorization_draft(ctx, authorization_id)).documents)


async def authorization_signers(ctx: AuthContext, authorization_id: UUID) -> list[object]:
    return list((await authorization_draft(ctx, authorization_id)).signers)


async def on_envelope_completed(event: OutboxEvent) -> None:
    """`envelope.completed` for this source: stamp the authorization and return each covered
    confirmation still awaiting it to Draft (authorized). Idempotent; other sources pass."""
    if event.payload.get("source_kind") != SOURCE:
        return
    authorization = UUID(str(event.payload["source_id"]))
    tenant = TenantContext(event.tenant_id, "system", _ACTOR)
    async with uow(tenant) as tx:
        stamped = (await tx.session.execute(_COMPLETE, {"a": authorization})).first()
        if stamped is None:
            tx.record(
                "confirmation.authorization_completed",
                target=Target("confirmation_authorization", authorization),
                after=Ref(n=0),
            )
            return
        covered = [
            cast(UUID, r[0]) for r in (await tx.session.execute(_COVERED, {"a": authorization}))
        ]
        moved = 0
        for confirmation in covered:
            done = await tx.session.execute(
                _MOVE, {"s": "draft", "c": confirmation, "from": "authorization_requested"}
            )
            if getattr(done, "rowcount", 0):
                moved += 1
                await tx.session.execute(
                    _EVENT,
                    {
                        "t": event.tenant_id,
                        "c": confirmation,
                        "k": "authorized",
                        "ak": "system",
                        "a": _ACTOR,
                    },
                )
        if covered:
            # A-08 §4.7: the requester hears it was signed (once per authorization).
            tx.emit(
                ConfirmationAuthorizationSigned(
                    confirmation_id=covered[0],
                    engagement_id=cast(UUID, stamped[0]),
                    user_id=cast(UUID, stamped[1]),
                )
            )
        tx.record(
            "confirmation.authorization_completed",
            target=Target("confirmation_authorization", authorization),
            after=Ref(n=moved),
        )


def register() -> None:
    """At import (assurance/api.py): the C7 source; a reload replaces itself."""
    from abacus.modules.signatures.api import EnvelopeSource, register_envelope_source

    register_envelope_source(
        EnvelopeSource(
            kind=SOURCE,
            documents=authorization_documents,
            signers=authorization_signers,
            retention_record_type="audit_documentation",  # AU-C 230, as A-07
            completed_label="Authorized",
            draft=authorization_draft,
        )
    )
