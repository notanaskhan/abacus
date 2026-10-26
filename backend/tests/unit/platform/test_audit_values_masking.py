"""G-02-T09 (TASK-1330; SPEC-349 AC-11; DEC-60, ADR-031): a Restricted value only ever leaves the
platform's value slot masked, whatever its resolver returned; amounts are decimal strings."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.platform import audit_slots
from abacus.modules.platform.audit_slots import AuditEventRef, AuditValueRow, AuditValues

SSN = "900-00-2208"


def _viewer() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(TenantContext(uuid.uuid4(), "human", str(user)), user, user, None, None)


@pytest.mark.parametrize(
    ("value", "masked"),
    [
        (SSN, "•••-••-2208"),
        ("1234", "••••"),
        (None, None),
    ],
)
def test_ac11_mask_value_keeps_separators_and_the_last_four_digits(
    value: str | None, masked: str | None
) -> None:
    assert audit_slots.mask_value(value) == masked


def test_ac11_a_restricted_value_left_in_clear_by_its_resolver_leaves_masked() -> None:
    async def careless(_viewer: AuthContext, _event: AuditEventRef) -> AuditValues:
        return AuditValues(
            "resolved",
            rows=(
                AuditValueRow("tin", None, SSN, classification="restricted", amount="10.00"),
                AuditValueRow("status", "draft", "final", amount="11860"),
                AuditValueRow("total", None, None, amount="11860.00"),
            ),
        )

    audit_slots.register_audit_value_resolver("g02t09_probe_careless", careless)
    event = AuditEventRef(1, "probe.changed", "g02t09_probe_careless", "1", None, None)
    values = asyncio.run(audit_slots.audit_values(_viewer(), event))
    tin, status, total = values.rows
    assert (tin.after, tin.masked, tin.amount) == ("•••-••-2208", True, None)
    assert SSN not in repr(values)
    assert status.amount is None  # not a decimal string: dropped, never guessed
    assert total.amount == "11860.00"


def test_dec60_withheld_and_unavailable_carry_no_rows() -> None:
    async def leaky(_viewer: AuthContext, _event: AuditEventRef) -> AuditValues:
        return AuditValues("withheld", "need_to_know", rows=(AuditValueRow("tin", None, SSN),))

    audit_slots.register_audit_value_resolver("g02t09_probe_leaky", leaky)
    event = AuditEventRef(1, "probe.changed", "g02t09_probe_leaky", "1", None, None)
    values = asyncio.run(audit_slots.audit_values(_viewer(), event))
    assert (values.status, values.reason, values.rows) == ("withheld", "need_to_know", ())


def test_g02t09_no_source_resolver_means_no_source_section() -> None:
    event = AuditEventRef(1, "probe.changed", "probe", "1", None, None)
    assert asyncio.run(audit_slots.audit_source(_viewer(), event)) is None


def test_l8_a_restricted_not_included_item_leaves_masked_and_without_its_amount() -> None:
    async def careless(_viewer: AuthContext, _event: AuditEventRef) -> AuditValues:
        return AuditValues(
            "resolved",
            not_included=(
                audit_slots.AuditNotIncluded(
                    SSN, "review_required", amount="14900.00", classification="restricted"
                ),
                audit_slots.AuditNotIncluded("Accrued expenses", "review_required", "14900"),
                audit_slots.AuditNotIncluded("Accrued expenses", "review_required", "14900.00"),
            ),
        )

    audit_slots.register_audit_value_resolver("g02t09_probe_not_included", careless)
    event = AuditEventRef(1, "probe.changed", "g02t09_probe_not_included", "1", None, None)
    secret, malformed, fine = asyncio.run(audit_slots.audit_values(_viewer(), event)).not_included
    assert (secret.item_label, secret.amount) == ("•••-••-2208", None)
    assert malformed.amount is None
    assert fine.amount == "14900.00"
