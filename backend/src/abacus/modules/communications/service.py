"""The guarded send path (ADR-065, ADR-005; SPEC-006 AC-4, AC-5, AC-7). PROTECTED.

`send` is the only way a message leaves the platform. A person, in a request they are making,
sends; agents only draft. Every draft is checked against the engagement's scope first: a clean
message is recorded `sent`, audited, and handed to delivery through the outbox
(`message.ready`; no transport until increments 2 and 8); a draft with violations is recorded
`blocked` with them (kinds and identifiers, never text), audited, and refused with 409
`out_of_scope`. A checker failure blocks too (`checker_error`). The body is confidential and
never logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from abacus.kernel.errors import DomainConflict
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Target, uow
from abacus.modules.communications.events import MessageReady
from abacus.modules.communications.repository import insert_message
from abacus.modules.communications.scope import Violation, check_scope
from abacus.modules.engagements.api import lock_ref
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, serving_request

_log = get_logger(__name__)


@dataclass(frozen=True)
class Draft:
    channel: str  # email | portal (no transport yet)
    recipient_ref: str  # an identifier of the recipient, never an address in logs
    body: str


@dataclass(frozen=True)
class MessageView:
    id: UUID
    status: str  # sent | blocked
    violations: list[Violation]


class OutOfScope(DomainConflict):
    """The draft names something outside the engagement's scope; nothing was sent."""

    code = "out_of_scope"

    def __init__(self, view: MessageView) -> None:
        super().__init__(self.code)
        self.view = view


async def send(ctx: AuthContext, engagement_id: UUID, draft: Draft) -> MessageView:
    if not isinstance(ctx, AuthContext) or not serving_request():  # pyright: ignore[reportUnnecessaryIsInstance] -- ADR-005 at runtime too
        raise Forbidden("message.send", "role")
    message_id = uuid4()
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "message.send", ref.resource())
        try:
            violations = await check_scope(ctx, ref, draft.body)
        except Exception as exc:  # fail closed
            _log.warning("message.checker_failed", error=exc)
            violations = [Violation("checker_error", "")]
        status = "blocked" if violations else "sent"
        await insert_message(
            tx.session,
            message_id=message_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            channel=draft.channel,
            recipient_ref=draft.recipient_ref,
            body=draft.body,
            status=status,
            violations=[{"kind": v.kind, "ref": v.ref} for v in violations],
            created_by=ctx.user_id,
        )
        tx.record(f"message.{status}", target=Target("message", message_id))
        if not violations:
            tx.emit(MessageReady(message_id=message_id, engagement_id=engagement_id))
    view = MessageView(message_id, status, violations)
    if violations:
        _log.info(
            "message.blocked",
            message_id=message_id,
            kinds=",".join(sorted({v.kind for v in violations})),
            count=len(violations),
        )
        raise OutOfScope(view)
    return view
