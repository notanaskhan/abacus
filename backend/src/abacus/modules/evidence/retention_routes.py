"""Retention routes (Q-02-T23): a firm's policies, and the platform staff's floor and default sets.

Contract: `docs/contracts/retention.md`. A policy below its published floor is
a 422 `below_floor`; a set publishes only when a second staff member approves it (409
`retention_two_person`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, cast

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.text import SingleLineText
from abacus.modules.evidence.retention import (
    Anchor,
    PolicyChange,
    ServiceLineOrAny,
    effective_policies,
    import_set,
    publish_set,
    set_policy,
)
from abacus.modules.identity.api import (
    STAFF,
    AbacusRouter,
    AuthContext,
    Staff,
    current_context,
    current_staff,
)

RecordType = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,62}$")]
Years = Annotated[Decimal, Field(gt=0, lt=1000, max_digits=4, decimal_places=1)]

router = AbacusRouter(prefix="/v1/retention", tags=["retention"])
platform_router = AbacusRouter(prefix="/v1/platform/retention", tags=["retention"])


class RetentionPolicyOut(BaseModel):
    """One record type and service line: the firm's policy, or the floor where it has none."""

    model_config = ConfigDict(frozen=True)

    record_type: Annotated[str, classified("internal")]
    service_line: Annotated[ServiceLineOrAny, classified("internal")]
    legal_floor_years: Annotated[str | None, classified("internal")] = None  # decimal string
    anchor: Annotated[Anchor | None, classified("internal")] = None
    authority: Annotated[str | None, classified("internal")] = None
    firm_years: Annotated[str, classified("internal")]  # decimal string
    clock_start_event: Annotated[Anchor, classified("internal")]
    lock: Annotated[bool, classified("internal")]
    basis: Annotated[str | None, classified("internal")] = None
    version: Annotated[int | None, classified("internal")] = None
    source: Annotated[Literal["policy", "floor"], classified("internal")]


class RetentionPoliciesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[RetentionPolicyOut], classified("internal")]


class RetentionPolicyIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    record_type: Annotated[RecordType, classified("internal")]
    service_line: Annotated[ServiceLineOrAny, classified("internal")]
    firm_years: Annotated[Years, classified("internal")]
    clock_start_event: Annotated[Anchor, classified("internal")]
    lock: Annotated[bool, classified("internal")] = False
    basis: Annotated[
        SingleLineText | None, Field(default=None, max_length=500), classified("internal")
    ]


class RetentionPolicySavedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: Annotated[int, classified("internal")]


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else format(value.normalize(), "f")


@router.get("/policies", action="retention_policy.read", response_model=RetentionPoliciesOut)
async def list_retention_policies_route(
    ctx: Annotated[AuthContext, Depends(current_context)],
) -> RetentionPoliciesOut:
    found = await effective_policies(ctx)
    return RetentionPoliciesOut(
        items=[
            RetentionPolicyOut(
                record_type=p.record_type,
                service_line=cast(ServiceLineOrAny, p.service_line),
                legal_floor_years=_decimal(p.legal_floor_years),
                anchor=cast(Anchor | None, p.anchor),
                authority=p.authority,
                firm_years=_decimal(p.firm_years) or "0",
                clock_start_event=cast(Anchor, p.clock_start_event),
                lock=p.lock,
                basis=p.basis,
                version=p.version,
                source=p.source,
            )
            for p in found
        ]
    )


@router.put("/policies", action="retention_policy.update", response_model=RetentionPolicySavedOut)
async def save_retention_policy_route(
    body: RetentionPolicyIn, ctx: Annotated[AuthContext, Depends(current_context)]
) -> RetentionPolicySavedOut:
    """Fresh MFA; 422 `below_floor` under the published floor, 422 `policy_locked` to shorten a
    locked policy."""
    version = await set_policy(
        ctx,
        PolicyChange(
            record_type=body.record_type,
            service_line=body.service_line,
            firm_years=body.firm_years,
            clock_start_event=body.clock_start_event,
            lock=body.lock,
            basis=body.basis,
        ),
    )
    return RetentionPolicySavedOut(version=version)


# --- platform staff ---------------------------------------------------------------------------


class RetentionFloorRowIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    record_type: Annotated[RecordType, classified("internal")]
    service_line: Annotated[ServiceLineOrAny, classified("internal")]
    legal_floor_years: Annotated[Years, classified("internal")]
    anchor: Annotated[Anchor, classified("internal")]
    authority: Annotated[SingleLineText, Field(max_length=500), classified("internal")]


class RetentionDefaultRowIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    record_type: Annotated[RecordType, classified("internal")]
    service_line: Annotated[ServiceLineOrAny, classified("internal")]
    firm_years: Annotated[Years, classified("internal")]
    clock_start_event: Annotated[Anchor, classified("internal")]
    lock: Annotated[bool, classified("internal")] = False
    basis: Annotated[
        SingleLineText | None, Field(default=None, max_length=500), classified("internal")
    ]


class RetentionFloorSetIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    set_version: Annotated[int, Field(ge=1), classified("internal")]
    rows: Annotated[
        list[RetentionFloorRowIn], Field(min_length=1, max_length=500), classified("internal")
    ]


class RetentionDefaultSetIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    set_version: Annotated[int, Field(ge=1), classified("internal")]
    rows: Annotated[
        list[RetentionDefaultRowIn], Field(min_length=1, max_length=500), classified("internal")
    ]


class RetentionSetOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    set_version: Annotated[int, classified("internal")]
    rows: Annotated[int, classified("internal")]
    status: Annotated[Literal["draft", "published"], classified("internal")]


def _rows(
    rows: list[RetentionFloorRowIn] | list[RetentionDefaultRowIn],
) -> list[dict[str, object]]:
    return [r.model_dump(mode="json") for r in rows]


@platform_router.post(
    "/floors", action=STAFF, response_model=RetentionSetOut, status_code=201, errors=(409,)
)
async def import_retention_floors_route(
    body: RetentionFloorSetIn, staff: Annotated[Staff, Depends(current_staff)]
) -> RetentionSetOut:
    """A draft floor set; a second staff member publishes it."""
    n = await import_set("floors", body.set_version, _rows(body.rows), str(staff.id))
    return RetentionSetOut(set_version=body.set_version, rows=n, status="draft")


@platform_router.post(
    "/floors/{set_version}/publish", action=STAFF, response_model=RetentionSetOut, errors=(409,)
)
async def publish_retention_floors_route(
    set_version: int, staff: Annotated[Staff, Depends(current_staff)]
) -> RetentionSetOut:
    n = await publish_set("floors", set_version, str(staff.id))
    return RetentionSetOut(set_version=set_version, rows=n, status="published")


@platform_router.post(
    "/defaults", action=STAFF, response_model=RetentionSetOut, status_code=201, errors=(409,)
)
async def import_retention_defaults_route(
    body: RetentionDefaultSetIn, staff: Annotated[Staff, Depends(current_staff)]
) -> RetentionSetOut:
    """A draft default-policy set (DEC-76 / P-62); a second staff member publishes it."""
    n = await import_set("defaults", body.set_version, _rows(body.rows), str(staff.id))
    return RetentionSetOut(set_version=body.set_version, rows=n, status="draft")


@platform_router.post(
    "/defaults/{set_version}/publish", action=STAFF, response_model=RetentionSetOut, errors=(409,)
)
async def publish_retention_defaults_route(
    set_version: int, staff: Annotated[Staff, Depends(current_staff)]
) -> RetentionSetOut:
    n = await publish_set("defaults", set_version, str(staff.id))
    return RetentionSetOut(set_version=set_version, rows=n, status="published")
