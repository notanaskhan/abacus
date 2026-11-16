"""The integration health monitor (W-01-T13; W-01 §3 F4; WB-10, WB-11; DEC-5319; red).

- **The rule** (`transition`, pure): a probe's outcome moves an install's status. A refused token
  (401 or 403) moves a connected or needs-attention install to `needs_reauth` at once and writes
  one `token_expired` event; three server errors or timeouts in a row move it to
  `needs_attention` (`health_failed`); a healthy probe brings `needs_attention` back to
  `connected` (`health_recovered`). Only a person's reconnect clears `needs_reauth`; `paused`,
  `connecting` and `disconnected` are never moved by the monitor. A throttle (429) changes
  nothing.
- **The activity** (`apply_probe`): applies the rule to one firm install in one unit of work: the
  status, its reason code, the event and the `integration.health_changed` outbox event (the
  firm admin's `connection_needs_reauth` notification and the SSE topic subscribe to it). A
  repeated probe that changes nothing writes nothing, so the notification goes out once.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, ClassVar, Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import DomainEvent, Ref, Target, uow

Probe = Literal["ok", "unauthorized", "server_error", "timeout", "throttled"]
Status = Literal[
    "connecting", "connected", "needs_attention", "needs_reauth", "paused", "disconnected"
]
FAILURES_TO_ATTENTION: Final = 3
_I = classified("internal")


class IntegrationHealthChanged(DomainEvent):
    event_type: ClassVar[str] = "integration.health_changed"

    install_id: Annotated[UUID, _I]
    catalog_key: Annotated[str, _I]
    from_status: Annotated[str, _I]
    to_status: Annotated[str, _I]


@dataclass(frozen=True)
class Step:
    status: Status
    event: str | None
    reason: str | None
    failures: int


def transition(status: Status, probe: Probe, failures: int) -> Step:
    """The install's next status, the event it writes (if any), and the failure count."""
    if status not in ("connected", "needs_attention"):
        return Step(status, None, None, failures)
    if probe == "unauthorized":
        return Step("needs_reauth", "token_expired", "token_expired", 0)
    if probe in ("server_error", "timeout"):
        n = failures + 1
        if status == "connected" and n >= FAILURES_TO_ATTENTION:
            return Step("needs_attention", "health_failed", f"provider_{probe}", n)
        return Step(status, None, None, n)
    if probe == "ok":
        if status == "needs_attention":
            return Step("connected", "health_recovered", None, 0)
        return Step(status, None, None, 0)
    return Step(status, None, None, failures)  # throttled: nothing changes


_ROW: Final = text("SELECT status, catalog_key FROM firm_integrations WHERE id = :i FOR UPDATE")
_MOVE: Final = text(
    "UPDATE firm_integrations SET status = :s, status_reason_code = :r, "
    "status_changed_at = clock_timestamp() WHERE id = :i"
)
_EVENT: Final = text(
    "INSERT INTO integration_events (tenant_id, install_kind, install_id, catalog_key, kind, at, "
    "code, http_status) VALUES (:t, 'firm', :i, :k, :kind, :at, :code, :http)"
)


async def apply_probe(
    tenant: TenantContext,
    install_id: UUID,
    probe: Probe,
    *,
    failures: int,
    at: datetime,
    http_status: int | None = None,
) -> Step:
    """One tick's probe for one firm install (the system's act)."""
    async with uow(tenant) as tx:
        row = (await tx.session.execute(_ROW, {"i": install_id})).first()
        if row is None:
            return Step("disconnected", None, None, failures)
        current: Status = row[0]
        step = transition(current, probe, failures)
        if step.event is None:
            return step
        await tx.session.execute(_MOVE, {"s": step.status, "r": step.reason, "i": install_id})
        await tx.session.execute(
            _EVENT,
            {
                "t": tenant.tenant_id,
                "i": install_id,
                "k": row[1],
                "kind": step.event,
                "at": at,
                "code": step.reason,
                "http": http_status,
            },
        )
        tx.record(
            "integration.health_changed",
            target=Target("firm_integration", install_id),
            after=Ref(changed=1),
        )
        tx.emit(
            IntegrationHealthChanged(
                install_id=install_id,
                catalog_key=str(row[1]),
                from_status=current,
                to_status=step.status,
            )
        )
    return step
