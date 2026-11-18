"""C-01-T27: POR-11's transaction questions in the portal (SPEC-656; C-01 §3; DEC-5633).

The client sees only questions addressed to a contact the signed-in person holds (an inquiry is
its addressee's only), in the firm's wording with a context line built from code facts
(identifiers and dates, never model text), and who asked. Never the issue, its severity, the
reconciliation, "Pending incorporation" or the agent (AC-47, INV-4). A close of another client
answers an empty list: nothing about it is disclosed, not even that it exists.

An answer is the choice the sheet offers plus the client's note (POR-04 e), recorded through the
shared requests API (sealed at rest; an attachment fulfils the linked request).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, Literal
from uuid import UUID

from abacus.modules.engagements.api import contact_ids_of_user
from abacus.modules.identity.api import AuthContext, names_of
from abacus.modules.requests.api import QuestionRow, answer_transaction_question, questions_for

Choice = Literal["lost_reissue", "voided", "something_else"]
# The client's words for each POR-04 question-sheet choice (the handoff's, verbatim).
CHOICE_WORDS: Final[Mapping[Choice, str]] = {
    "lost_reissue": "Lost — please reissue it",
    "voided": "Voided",
    "something_else": "Something else",
}


def context_line(context: Mapping[str, object]) -> str:
    """ "Front Range Bank ••4410 · check #2285" from the question's code facts only."""
    parts: list[str] = []
    account = context.get("account_label") or context.get("account_external_id")
    if account:
        parts.append(str(account))
    line = context.get("register_line_label") or context.get("register_line_ref")
    if line:
        parts.append(str(line))
    return " · ".join(parts)


async def mine(ctx: AuthContext, close_id: UUID) -> list[QuestionRow]:
    held = await contact_ids_of_user(ctx.tenant, ctx.user_id)
    return [q for q in await questions_for(ctx.tenant, close_id) if q.assignee_contact_id in held]


async def asked_by_names(rows: list[QuestionRow]) -> dict[UUID, str]:
    return await names_of(sorted({q.asked_by for q in rows}, key=str))


def answer_text(choice: Choice | None, note: str | None) -> str:
    words = [] if choice is None else [CHOICE_WORDS[choice]]
    if note and note.strip():
        words.append(note.strip())
    return " — ".join(words)


async def answer(
    ctx: AuthContext,
    question_id: UUID,
    choice: Choice | None,
    note: str | None,
    evidence_version_id: UUID | None,
    fulfils_request_item_id: UUID | None,
) -> QuestionRow:
    return await answer_transaction_question(
        ctx,
        question_id,
        answer_text(choice, note),
        fulfils_request_item_id=fulfils_request_item_id,
        evidence_version_id=evidence_version_id,
    )
