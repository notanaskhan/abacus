"""CLS-11's and POR-16's consumer view of C20 v2.1 W1 (C-02-T08; SPEC-700 AC-3, AC-4, AC-23, AC-24;
DEC-5507), run against the C-02-T06 stub on the handoff's facts: Copperleaf's ledger console at
9:24 AM, Sep 14, 2026 (7 Posted, 1 Proposed, closing date Jul 31; authorized by Tess Moreno), the
2026-07-A batch with its resolved failure, the 429 and reauth states, and the client owner's
write grant on consent copy v2. A breaking change to a console or write-grant schema fails here.
The fixture half is `apps/web/src/fixtures/contracts/c20-w1.contract.test.ts`."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from typing import cast

import pytest
from pydantic import ValidationError

from abacus.api.export_openapi import document
from abacus.kernel._statuses import PostingBatchStatus
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.integrations.w1_contract import (
    ConnectionPaneOut,
    ConsoleTilesOut,
    LedgerConsoleOut,
    PostingLogRowOut,
    WriteGrantIn,
)

Json = dict[str, object]
PATHS = cast(dict[str, dict[str, Json]], json.loads(document())["paths"])
E = "/v1/client-entities/{client_entity_id}"
OPERATIONS = {
    ("get", f"{E}/ledger-console"): "ledger_connection.read",
    ("get", f"{E}/posting-batches"): "ledger_connection.read",
    ("get", f"{E}/posting-batches.csv"): "ledger_connection.export",
    ("get", f"{E}/ledger-activity"): "ledger_connection.read",
    ("get", "/v1/posting-batches/{batch_id}"): "ledger_connection.read",
    (
        "post",
        "/v1/write-capabilities/ledger_post_journal_entries:enable",
    ): "write_capability.enable",
    (
        "post",
        "/v1/write-capabilities/ledger_post_journal_entries:disable",
    ): "write_capability.enable",
    ("get", "/v1/integrations/quickbooks_online/settings/gl-posting"): "gl_posting_settings.read",
    (
        "put",
        "/v1/integrations/quickbooks_online/settings/gl-posting",
    ): "gl_posting_settings.update",
    (
        "put",
        "/v1/engagements/{engagement_id}/ledger-settings",
    ): "engagement_ledger_settings.update",
    ("post", "/v1/portal/connections/{connection_id}/write-grants"): "connection.grant_write",
    (
        "delete",
        "/v1/portal/connections/{connection_id}/write-grants/current",
    ): "connection.revoke_write",
}
CT = UTC  # the fixtures carry UTC instants; the screen renders CT


def _cls11a() -> LedgerConsoleOut:
    return LedgerConsoleOut(
        client_entity_id=uuid.uuid4(),
        client_entity_name="Copperleaf Coffee Roasters, Inc.",
        ledger_label="QuickBooks Online",
        tiles=ConsoleTilesOut(
            posted=7,
            proposed=1,
            failed_post=0,
            resolved_failures=1,
            closing_date=date(2026, 7, 31),
        ),
        connection=ConnectionPaneOut(
            connection_id=uuid.uuid4(),
            health="connected",
            authorized_by="Tess Moreno (client portal)",
            write_granted=True,
            last_sync_at=datetime(2026, 9, 14, 14, 2, tzinfo=CT),
            last_sync_transactions=1214,
            last_sync_errors=0,
            next_sync_at=datetime(2026, 9, 14, 15, 2, tzinfo=CT),
            closing_date=date(2026, 7, 31),
            closing_date_set_by="Raj Malhotra",
        ),
    )


def test_cls11a_the_console_reads_its_tiles_and_pane() -> None:
    page = _cls11a()
    assert (page.tiles.posted, page.tiles.proposed, page.tiles.failed_post) == (7, 1, 0)
    assert page.tiles.resolved_failures == 1
    assert page.connection is not None and page.connection.last_sync_transactions == 1214


def test_cls11b_the_log_names_the_july_batch_and_its_resolved_failure() -> None:
    row = PostingLogRowOut(
        batch_id=uuid.uuid4(),
        batch_code="2026-07-A",
        period="2026-07",
        status=PostingBatchStatus.POSTED,
        entry_count=6,
        approved_count=6,
        first_external_ref="47602",
        last_external_ref="47607",
        resolved_failures=1,
    )
    assert row.resolved_failures == 1


@pytest.mark.parametrize("health", ["needs_attention", "needs_reauth"])
def test_cls11c_d_unhealthy_connections_fit(health: str) -> None:
    pane = _cls11a().connection
    assert pane is not None
    changed = ConnectionPaneOut.model_validate({**pane.model_dump(), "health": health})
    assert changed.health == health


def test_por16_the_grant_names_consent_copy_v2_only() -> None:
    WriteGrantIn(
        capability_id="ledger_post_journal_entries",
        consent_copy_version="por16.qbo.post_entries.v2",
    )
    with pytest.raises(ValidationError):
        WriteGrantIn.model_validate(
            {"capability_id": "ledger_post_journal_entries", "consent_copy_version": "v1"}
        )


def test_only_the_client_owner_grants_writes_with_a_fresh_second_factor() -> None:
    for action in ("connection.grant_write", "connection.revoke_write"):
        rule = RULES[action]
        assert rule.mfa_recent
        granted = {r for r, d in rule.decisions.items() if d != "deny"}
        assert granted == {"client_admin"}


def test_the_firm_switch_is_security_admins_alone() -> None:
    rule = RULES["write_capability.enable"]
    assert rule.mfa_recent
    assert {r for r, d in rule.decisions.items() if d != "deny"} == {"security_admin"}


@pytest.mark.parametrize(("op", "action"), sorted(OPERATIONS.items()), ids=str)
def test_every_operation_is_declared_with_its_action_and_501(
    op: tuple[str, str], action: str
) -> None:
    method, path = op
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == action
    assert "501" in cast(Json, operation["responses"])
    assert RULES[action].decisions.get("agent", "deny") == "deny"
