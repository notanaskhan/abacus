# ac-test-author: ayushkbhatia
"""N-01-T25 (TASK-2333; ADR-078): independent AC tests for N-01-T22's matcher, written from the
acceptance text, SPEC-380 AC-10 to AC-12 and ADR-005.

Acceptance (the task row): "... no matcher output path files, ignores, holds or supersedes."

- **Never decides:** after a completed run, and after one that proposes a supersede-worthy
  destination, nothing is filed, ignored or held, no evidence version is written and no triage
  decision exists; no code under `abacus.modules.agents` reaches triage apply, and the matrix
  denies the agent and the system every inbox decision.
- **TRI fail-closed:** a client with a tax return and no §7216 consent gets no model call and no
  proposal.
- **Cross-client containment:** a reference the model was never given is discarded, so no proposal
  ever names another client's destination.

Boundary: the fake model only (ADR-076): T22's stub provider on the real Bedrock route and the
matcher's two intake activities; outcomes through SQL. The direct-route run on a real model is
N-01-T26's (`make evals`).
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path
from typing import Final

import pytest

import abacus.modules.agents as agents_package
from abacus.modules.identity.authz.matrix import RULES

from .support import Net
from .test_n01t22_intake_match import (  # T22's fake-model harness (ADR-076)
    Stub,
    _firm,  # pyright: ignore[reportPrivateUsage] -- T22's firm builder, shared harness
    answer,
)
from .test_n01t22_intake_match import raw as raw
from .test_n01t22_intake_match import stub as stub
from .test_n01t22_intake_match import wired as wired

pytestmark = pytest.mark.asyncio
DECISIONS: Final = ("inbox.file", "inbox.triage", "inbox.ask_client")


async def _untouched(net: Net, tenant: uuid.UUID, attachment: uuid.UUID) -> None:
    (row,) = await net.seed.rows(
        "SELECT status, filed_evidence_version_id, filed_destination_kind "
        "FROM inbox_attachments WHERE id = $1",
        attachment,
    )
    assert row["status"] == "waiting"
    assert row["filed_evidence_version_id"] is None and row["filed_destination_kind"] is None
    assert (
        await net.seed.value(
            "SELECT count(*) FROM triage_decisions WHERE attachment_id = $1", attachment
        )
        == 0
    )
    superseded = await net.seed.value(
        "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1 "
        "AND supersedes_version_id IS NOT NULL",
        tenant,
    )
    assert superseded == 0


async def test_ac_a_completed_run_files_ignores_holds_and_supersedes_nothing(
    net: Net,
    stub: Stub,
) -> None:
    firm = await _firm(net)
    stub.answer = answer(firm.request_marker, confidence=0.99)
    attachment = await firm.receive()
    versions_before = await net.seed.value(
        "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1", firm.tenant_id
    )
    _, status = await firm.match(attachment)
    assert status == "completed"
    await _untouched(net, firm.tenant_id, attachment)
    versions_after = await net.seed.value(
        "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1", firm.tenant_id
    )
    assert versions_after == versions_before  # a proposal is never a filing
    proposals = await net.seed.value(
        "SELECT count(*) FROM inbox_match_proposals p JOIN inbox_match_runs r "
        "ON r.id = p.match_id WHERE r.inbox_attachment_id = $1",
        attachment,
    )
    assert proposals == 1  # it proposed; a person decides


async def test_ac_no_agents_code_reaches_triage_apply() -> None:
    """No module under `abacus.modules.agents` imports or calls the triage decision path."""
    root = Path(agents_package.__file__).parent
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = [a.name for a in node.names]
                assert "triage_apply" not in (node.module or ""), path
                assert "triage_apply" not in names, path
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "/triage/apply" not in node.value, path
                assert "/bulk-file" not in node.value, path


def test_ac_the_matrix_denies_the_agent_and_the_system_every_inbox_decision() -> None:
    for action in DECISIONS:
        decisions = RULES[action].decisions
        for principal in ("agent", "system"):
            assert decisions.get(principal, "deny") == "deny", (action, principal)


async def test_ac_tri_without_consent_fails_closed(
    net: Net,
    stub: Stub,
) -> None:
    firm = await _firm(net)
    await net.seed.run(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
        "name, period_start, period_end, created_by) VALUES ($1, $2, $3, $4, 'tax_return', "
        "'TY2025 Form 1040', '2025-01-01', '2025-12-31', $5)",
        firm.tenant_id,
        firm.site.engagement_id,
        firm.site.client_id,
        firm.site.entity_id,
        firm.partner.user_id,
    )
    stub.answer = answer(firm.request_marker)
    attachment = await firm.receive()
    _, status = await firm.match(attachment)
    assert status != "completed"
    assert stub.calls == []  # no model saw a word of the return's client
    assert (
        await net.seed.value(
            "SELECT count(*) FROM inbox_match_proposals p JOIN inbox_match_runs r "
            "ON r.id = p.match_id WHERE r.inbox_attachment_id = $1",
            attachment,
        )
        == 0
    )
    await _untouched(net, firm.tenant_id, attachment)


async def test_ac_a_reference_never_given_never_becomes_a_proposal(
    net: Net,
    stub: Stub,
) -> None:
    firm = await _firm(net)
    other = await net.seed.site(firm.tenant_id, firm.partner.user_id, "Whitley")
    await net.seed.member(other, firm.partner, "engagement_partner")
    # The model answers with its own reference and one it invented (the other client's item).
    stub.answer = answer(firm.request_marker, extra_ref=f"D{uuid.uuid4().int % 900 + 100}")
    attachment = await firm.receive()
    _, status = await firm.match(attachment)
    assert status == "completed"
    rows = await net.seed.rows(
        "SELECT p.destination_id, p.request_item_id FROM inbox_match_proposals p "
        "JOIN inbox_match_runs r ON r.id = p.match_id WHERE r.inbox_attachment_id = $1",
        attachment,
    )
    assert len(rows) == 1  # the invented reference is discarded
    named = {r["destination_id"] for r in rows} | {r["request_item_id"] for r in rows}
    assert other.item_id not in named and other.client_id not in named
    [request] = stub.calls
    assert other.marker not in request.user  # the other client never reached the model
    await _untouched(net, firm.tenant_id, attachment)
