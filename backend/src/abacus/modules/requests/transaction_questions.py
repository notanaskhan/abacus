"""Transaction questions, the shared requests API (C-01-T24; C-01 §4.2, §4.4; chapter 03 §2.1).

A question is a person's ask to one client contact about one transaction: the firm's template
wording (a DB template, `template_id` and its version; P-25 off, so no agent wording, DEC-79)
filled with code facts (`context`: identifiers, amounts and dates from the ledger, never model
text). The caller authorised `transaction_question.send` and ran the outbound scope check
(ADR-065) before `ask`; `ask` only writes, inside the caller's unit of work, the question and
its `asked` event.

The client's answer (POR-11 c) is sealed at rest and recorded by the contact it was addressed
to (the client principal must hold that contact: an inquiry is its addressee's only). An answer
with an attachment fulfils the linked request item (`fulfils_request_item_id`).

Every write is audited (`transaction_question.sent`, `transaction_question.answered`); the
answer's text never leaves this module unsealed except to the firm's readers.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import contact_ids_of_user
from abacus.modules.identity.api import AuthContext, Forbidden

SUBJECT: Final = "transaction_question"
QuestionStatus = Literal["open", "answered", "withdrawn"]


class QuestionAlreadyAnswered(DomainConflict):
    code = "question_already_answered"


@dataclass(frozen=True)
class QuestionRow:
    id: UUID
    work_item_id: UUID
    request_list_id: UUID
    issue_id: UUID | None
    template_id: str
    template_version: int
    client_wording: str
    context: Mapping[str, object]
    asked_by: UUID
    asked_at: datetime
    assignee_contact_id: UUID
    status: QuestionStatus
    answered_at: datetime | None
    answered_by_contact_id: UUID | None
    fulfils_request_item_id: UUID | None
    row_version: int


_INSERT = text(
    "INSERT INTO transaction_questions (tenant_id, work_item_id, request_list_id, issue_id, "
    "template_id, template_version, client_wording, context, asked_by, assignee_contact_id) "
    "VALUES (:t, :w, :l, :i, :tpl, :v, :wording, CAST(:ctx AS jsonb), :by, :contact) "
    "RETURNING id"
)
_EVENT = text(
    "INSERT INTO transaction_question_events (tenant_id, question_id, kind, actor_kind, "
    "actor_id, contact_id) VALUES (:t, :q, :k, :ak, :a, :c)"
)
_FOR_ITEM = text(
    "SELECT id, work_item_id, request_list_id, issue_id, template_id, template_version, "
    "client_wording, context, asked_by, asked_at, assignee_contact_id, status, answered_at, "
    "answered_by_contact_id, fulfils_request_item_id, row_version FROM transaction_questions "
    "WHERE work_item_id = :w ORDER BY asked_at, id"
)
_ONE = text(
    "SELECT id, work_item_id, request_list_id, issue_id, template_id, template_version, "
    "client_wording, context, asked_by, asked_at, assignee_contact_id, status, answered_at, "
    "answered_by_contact_id, fulfils_request_item_id, row_version FROM transaction_questions "
    "WHERE id = :q FOR UPDATE"
)
_ANSWER = text(
    "UPDATE transaction_questions SET status = 'answered', answer_sealed = :sealed, "
    "answered_by_contact_id = :c, answered_at = clock_timestamp(), "
    "fulfils_request_item_id = :item, row_version = row_version + 1 "
    "WHERE id = :q AND status = 'open' RETURNING row_version"
)


def _row(r: object) -> QuestionRow:
    m = cast("Mapping[str, object]", r)
    raw = m["context"]
    context = cast("Mapping[str, object]", json.loads(raw) if isinstance(raw, str) else raw or {})
    return QuestionRow(
        id=cast(UUID, m["id"]),
        work_item_id=cast(UUID, m["work_item_id"]),
        request_list_id=cast(UUID, m["request_list_id"]),
        issue_id=cast("UUID | None", m["issue_id"]),
        template_id=cast(str, m["template_id"]),
        template_version=cast(int, m["template_version"]),
        client_wording=cast(str, m["client_wording"]),
        context=context,
        asked_by=cast(UUID, m["asked_by"]),
        asked_at=cast(datetime, m["asked_at"]),
        assignee_contact_id=cast(UUID, m["assignee_contact_id"]),
        status=cast(QuestionStatus, m["status"]),
        answered_at=cast("datetime | None", m["answered_at"]),
        answered_by_contact_id=cast("UUID | None", m["answered_by_contact_id"]),
        fulfils_request_item_id=cast("UUID | None", m["fulfils_request_item_id"]),
        row_version=cast(int, m["row_version"]),
    )


def _fingerprint(question_id: UUID) -> str:
    return f"{SUBJECT}:{question_id}:answer"


async def raise_question(
    tx: UnitOfWork,
    ctx: AuthContext,
    *,
    work_item_id: UUID,
    request_list_id: UUID,
    issue_id: UUID | None,
    template_id: str,
    template_version: int,
    client_wording: str,
    context: Mapping[str, str],
    assignee_contact_id: UUID,
) -> UUID:
    """Write the question and its `asked` event in the caller's unit of work (the caller
    authorised and scope-checked). Only a person asks (the events table CHECKs it too)."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("transaction_question.send", "role")
    question_id = cast(
        UUID,
        await tx.session.scalar(
            _INSERT,
            {
                "t": ctx.tenant_id,
                "w": work_item_id,
                "l": request_list_id,
                "i": issue_id,
                "tpl": template_id,
                "v": template_version,
                "wording": client_wording,
                "ctx": json.dumps(dict(context), sort_keys=True),
                "by": ctx.user_id,
                "contact": assignee_contact_id,
            },
        ),
    )
    await tx.session.execute(
        _EVENT,
        {
            "t": ctx.tenant_id,
            "q": question_id,
            "k": "asked",
            "ak": "human",
            "a": ctx.user_id,
            "c": None,
        },
    )
    tx.record(
        "transaction_question.sent",
        target=Target(SUBJECT, question_id),
        after=Ref(work_item_id=work_item_id, contact_id=assignee_contact_id),
    )
    return question_id


async def questions_for(tenant: TenantContext, work_item_id: UUID) -> list[QuestionRow]:
    """Every question on a work item, oldest first (for a caller authorised on it)."""
    async with tenant_session(tenant) as session:
        return [
            _row(r) for r in (await session.execute(_FOR_ITEM, {"w": work_item_id})).mappings()
        ]


async def answer(
    ctx: AuthContext,
    question_id: UUID,
    answer_text: str,
    *,
    fulfils_request_item_id: UUID | None = None,
    evidence_version_id: UUID | None = None,
) -> QuestionRow:
    """The addressed contact's answer, sealed; with an attachment (`evidence_version_id`, already
    uploaded by the portal route, which authorised `evidence.upload` on the item) it fulfils the
    linked request item in the same unit of work. Any other principal reads 404 (the question is
    not theirs to see)."""
    from abacus.modules.requests.service import fulfil_by_upload

    if not ctx.client:
        raise NotFound(SUBJECT)
    text_in = answer_text.strip()
    if not 1 <= len(text_in) <= 4000:
        raise NotFound(SUBJECT)
    mine = await contact_ids_of_user(ctx.tenant, ctx.user_id)
    async with uow(ctx.tenant) as tx:
        found = (await tx.session.execute(_ONE, {"q": question_id})).mappings().first()
        if found is None:
            raise NotFound(SUBJECT)
        row = _row(found)
        if row.assignee_contact_id not in mine:
            raise NotFound(SUBJECT)
        # A question's own codes (C-01-T24), not a request item's: only an unanswered one takes
        # an answer.
        if row.status in ("answered", "withdrawn"):
            raise QuestionAlreadyAnswered(facts={"status": row.status})
        sealed = await seal(ctx.tenant_id, text_in.encode(), _fingerprint(question_id))
        version = await tx.session.scalar(
            _ANSWER,
            {
                "sealed": sealed,
                "c": row.assignee_contact_id,
                "item": fulfils_request_item_id,
                "q": question_id,
            },
        )
        if version is None:
            raise QuestionAlreadyAnswered(facts={"status": "answered"})
        await tx.session.execute(
            _EVENT,
            {
                "t": ctx.tenant_id,
                "q": question_id,
                "k": "answered",
                "ak": "client",
                "a": None,
                "c": row.assignee_contact_id,
            },
        )
        if fulfils_request_item_id is not None and evidence_version_id is not None:
            await fulfil_by_upload(
                tx,
                request_item_id=fulfils_request_item_id,
                evidence_version_id=evidence_version_id,
            )
        tx.record(
            "transaction_question.answered",
            target=Target(SUBJECT, question_id),
            after=Ref(contact_id=row.assignee_contact_id),
        )
    async with tenant_session(ctx.tenant) as session:
        fresh = (await session.execute(_FOR_ITEM, {"w": row.work_item_id})).mappings()
        return next(_row(r) for r in fresh if r["id"] == question_id)
