"""The canary's steps through the product's own services (Q-01-T30). PROTECTED.

It lives beside the worker, not in `platform`: the platform module depends on identity only
(ADR-008, BOUND-002), and the probe reaches requests, evidence, agents and communications. The
worker composes it at boot (`configure_canary_probe`), as it composes every module's parts.

`ServiceProbe` acts as the canary staff member (`identity.member_context`: an active member of
the synthetic canary firm, read fresh each step, never with an MFA time) through the same module
interfaces a person's request reaches: `requests.add_request_item`, `evidence.upload` (the
malware scan runs before anything is stored), the evidence processing state and preview, the
upload reviewer ("Review now") and its code-verified citations, the outbox through the relay
role, and `communications.send_email` (a synthetic firm's mail goes to the sink, F-04-T22).
Every write is in the canary firm's context, so the run leaves nothing outside a synthetic firm.

The screener step under `synthetic_only`: the upload reviewer has no answers on the fake route
(its routes are Bedrock and direct, TASK-059 D3), so the step reports the fake route as not run
(DEC-358) and the INV-2 check runs on no flags; under `client_data` it asks for a review and
checks every shown flag's citations.
"""

from __future__ import annotations

import asyncio
import io
import time
from collections.abc import Awaitable, Callable
from typing import Final
from uuid import UUID, uuid4

from abacus.ai_gateway import attempts_for
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import (
    DomainConflict,
    DomainForbidden,
    DomainInvalid,
    DomainTooLarge,
    DomainUnsupported,
    NotFound,
)
from abacus.kernel.uow.relay import event_state
from abacus.modules.agents.api import (
    ReviewUnavailable,
    request_review,
    review_citation_states,
    upload_review_available,
)
from abacus.modules.communications.api import send_email
from abacus.modules.evidence.api import screening_facts, upload, upload_preview
from abacus.modules.identity.api import AuthContext, Forbidden, firm_tenancy, member_context
from abacus.modules.platform.api import (
    CanaryFlag,
    CanaryNotSynthetic,
    CanaryPlan,
    CanaryScreen,
    CanaryStepFailed,
    canary_boundary,
    expected_route,
)
from abacus.modules.requests.api import NewRequestItem, add_request_item

SIMULATOR_ADDRESS: Final = "success@simulator.amazonses.com"
FILE_NAME: Final = "canary-statement.pdf"
POLL_SECONDS: Final = 2.0
PROCESSING_SECONDS: Final = 150.0  # inside the workflow's 3-minute step timeout (SLO-03: 2 min)
REVIEW_SECONDS: Final = 150.0
OUTBOX_SECONDS: Final = 30.0
_DONE_REVIEW: Final = frozenset({"completed", "failed", "escalated"})


def canary_pdf(stamp: str) -> bytes:
    """A one-page synthetic statement: Helvetica text only, unique per run (`stamp`)."""
    lines = ("Canary & Co synthetic statement", f"Run {stamp}", "Closing balance 1,000.00")
    body = "".join(f"({line}) Tj T* " for line in lines)
    stream = f"BT /F1 12 Tf 16 TL 72 720 Td {body}ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    )
    return out.getvalue()


async def _checked[T](step: Awaitable[T]) -> T:
    """A product refusal is the step's failure, by its code (never its text)."""
    try:
        return await step
    except (
        DomainInvalid,
        DomainConflict,
        DomainForbidden,
        DomainTooLarge,
        DomainUnsupported,
    ) as refused:
        raise CanaryStepFailed(refused.code) from refused
    except NotFound as missing:
        raise CanaryStepFailed("not_found") from missing
    except Forbidden as denied:
        raise CanaryStepFailed("forbidden") from denied


async def _until[T](
    seconds: float, ask: Callable[[], Awaitable[T | None]], timeout_code: str
) -> T:
    deadline = time.monotonic() + seconds
    while True:
        found = await ask()
        if found is not None:
            return found
        if time.monotonic() >= deadline:
            raise CanaryStepFailed(timeout_code)
        await asyncio.sleep(POLL_SECONDS)


class ServiceProbe:
    """The canary's steps as the canary staff member (see the module docstring)."""

    async def _person(self, plan: CanaryPlan) -> AuthContext:
        found = await member_context(UUID(plan.tenant_id), UUID(plan.user_id))
        if found is None:
            raise CanaryNotSynthetic("the canary staff member is not an active member")
        return found

    async def prepare(self, tenant_id: UUID) -> CanaryPlan:
        """The firm must be the configured canary firm and synthetic, before anything is
        written; the staff member must be an active member of it."""
        s = settings()
        if (
            s.canary_tenant_id != tenant_id
            or s.canary_staff_user_id is None
            or s.canary_engagement_id is None
        ):
            raise CanaryStepFailed("not_configured")
        facts = await firm_tenancy(TenantContext(tenant_id, "system", "platform.canary"))
        if facts is None or not facts.synthetic:
            raise CanaryNotSynthetic("the canary firm is not synthetic")
        plan = CanaryPlan(str(tenant_id), str(s.canary_staff_user_id), str(s.canary_engagement_id))
        await self._person(plan)
        return plan

    async def create_item(self, plan: CanaryPlan) -> UUID:
        ctx = await self._person(plan)
        item = await _checked(
            add_request_item(
                ctx,
                UUID(plan.engagement_id),
                NewRequestItem(description="Canary statement", audit_area="Cash"),
            )
        )
        return item.id

    async def upload(self, plan: CanaryPlan, item_id: UUID) -> UUID:
        ctx = await self._person(plan)
        uploaded = await _checked(
            upload(
                ctx,
                UUID(plan.engagement_id),
                item_id,
                file_name=FILE_NAME,
                content=canary_pdf(uuid4().hex),
            )
        )
        return uploaded.evidence_version_id

    async def wait_processing(self, plan: CanaryPlan, item_id: UUID, version_id: UUID) -> None:
        """Extracted, and its preview made (the scan ran before the upload was stored)."""
        ctx = await self._person(plan)
        engagement = UUID(plan.engagement_id)

        async def ready() -> bool | None:
            facts = (await screening_facts(ctx.tenant, [version_id])).get(version_id)
            status = facts.extraction_status if facts is not None else None
            if status is not None and status != "extracted":
                raise CanaryStepFailed(f"extraction_{status}")
            preview = await _checked(upload_preview(ctx, engagement, item_id, version_id))
            return True if status == "extracted" and preview.kind != "pending" else None

        await _until(PROCESSING_SECONDS, ready, "processing_timeout")

    async def screen(self, plan: CanaryPlan, item_id: UUID, version_id: UUID) -> CanaryScreen:
        allowed = expected_route(canary_boundary())
        if not upload_review_available():
            # DEC-358: no reviewer answers on the fake route; the route check still runs.
            return CanaryScreen(
                route=allowed if allowed == "fake" else "none", ran=False, flags=()
            )
        ctx = await self._person(plan)
        engagement = UUID(plan.engagement_id)
        try:
            await _checked(request_review(ctx, engagement, version_id))
        except ReviewUnavailable:
            return CanaryScreen(route="none", ran=False, flags=())

        async def finished() -> tuple[UUID, str, CanaryScreen] | None:
            states = await _checked(review_citation_states(ctx, engagement, version_id))
            if states.run_id is None or states.status not in _DONE_REVIEW:
                return None
            flags = tuple(
                CanaryFlag(category, verified, shown_uncited=False)
                for category, verified in states.flags
            )
            return states.run_id, states.status, CanaryScreen("none", True, flags)

        run_id, status, found = await _until(REVIEW_SECONDS, finished, "screen_timeout")
        if status != "completed":
            raise CanaryStepFailed(f"screen_{status}")
        routes = {a.route for a in await attempts_for(ctx.tenant, run_id)}
        route = routes.pop() if len(routes) == 1 else ("mixed" if routes else "none")
        return CanaryScreen(route, True, found.flags)

    async def observe_outbox(self, plan: CanaryPlan, version_id: UUID) -> None:
        """The upload's `evidence.uploaded` event left the outbox (the relay is running)."""

        async def published() -> bool | None:
            state = await event_state(
                UUID(plan.tenant_id),
                "evidence.uploaded",
                field="evidence_version_id",
                value=str(version_id),
            )
            if state == "absent":
                raise CanaryStepFailed("event_absent")
            return True if state == "published" else None

        await _until(OUTBOX_SECONDS, published, "outbox_lag")

    async def send_simulator(self, plan: CanaryPlan) -> None:
        """A reminder to the SES simulator's success address, as the firm's mail goes."""
        sent = await send_email(
            tenant_id=UUID(plan.tenant_id),
            message_id=uuid4(),
            to=SIMULATOR_ADDRESS,
            subject="Canary reminder",
            body="A synthetic reminder from the canary run.",
        )
        if not sent:
            raise CanaryStepFailed("mail_refused")
