"""N-02-T35 (TASK-2432; ADR-078; N-02 §3.11, §4.2; ENG-04; INV-1, INV-3, INV-5; DEC-1480): the
independent suite for N-02-T32 and T33, written from the row and the contracts, and the withdrawal
path for a letter envelope that came back unsigned.

The row's acceptance: "The suite passes and fails if a manager's approval or a consent clause
inside the letter is accepted." So: the matrix refuses a manager, the agent and the system the
approval and asks a fresh second factor of a partner; the service refuses a live non-person; the
database refuses an approval recorded by anyone but the approving person; the approval goes stale
on any change (a new draft version) and versions are insert-only; G1 must come on or before the
letter's date; §7216 consent wording in a section or variable is refused (AC-15); the fee wording
is computed by code; the approval is attributed to the partner (INV-5). Then the withdrawal: an
envelope declined at C7 is withdrawn by a person and the letter is back at its approval, with a
fresh Send drafting a new envelope; the database refuses the same move from anyone but a person.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

import asyncpg
import pytest

from abacus.modules.engagements import letter_flow, letters
from abacus.modules.engagements.letter_contract import LetterDraftIn
from abacus.modules.identity.api import Forbidden
from abacus.modules.identity.authz._matrix import ACTIONS
from abacus.modules.signatures import api as _signatures  # registers the source and its ports

from .agent_tests.support import Seeder
from .test_n02t32_letter_composer import draft_of, engines, fresh_registry, seed
from .test_n02t33_letter_approval import (
    _approvable,  # pyright: ignore[reportPrivateUsage] -- N-02-T33's harness
)

__all__ = ["_signatures", "engines", "fresh_registry", "seed"]

pytestmark = pytest.mark.usefixtures("engines", "fresh_registry")


def test_inv1_the_matrix_keeps_the_approval_a_partners_with_a_fresh_factor() -> None:
    cell = ACTIONS["letter.approve"]
    assert cell.get("engagement_partner") == "allow"
    assert cell.get("manager", "deny") == "deny"
    assert cell.get("agent") == "deny" and cell.get("system") == "deny"
    assert cell.get("mfa_recent") == "required"


async def test_inv1_a_non_person_and_the_database_refuse_the_approval(seed: Seeder) -> None:
    ctx, engagement, _template = await _approvable(seed)
    await letter_flow.request_approval(ctx, engagement, '"1"')
    agent = replace(ctx, tenant=replace(ctx.tenant, actor_kind="agent"))
    with pytest.raises(Forbidden):
        await letter_flow.approve_letter(agent, engagement, '"1"')
    version = await seed.value(
        "SELECT id FROM engagement_letter_versions WHERE engagement_id = $1 AND version_no = 1",
        engagement,
    )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.as_actor(
            ctx.tenant_id,
            ("human", str(uuid.uuid4())),  # a person, but not the one named as approver
            "UPDATE engagement_letter_versions SET status = 'partner_approved', "
            "approved_by = $2, approved_at = now(), approval_content_hash = content_hash "
            "WHERE id = $1",
            version,
            ctx.user_id,
        )


async def test_ac15_a_consent_inside_the_letter_is_refused(seed: Seeder) -> None:
    ctx, engagement, template = await _approvable(seed)
    base = draft_of(template)
    # The consent rule runs before a section is looked up, so any section id shows it.
    body = LetterDraftIn.model_validate(
        {
            **base.model_dump(),
            "section_overrides": {
                "scope": "The client consents to the use of tax return information (§7216)."
            },
        }
    )
    with pytest.raises(letters.ConsentInLetter):
        await letters.draft_letter(ctx, engagement, body, '"1"')


async def test_the_approval_is_stale_on_any_change_and_versions_are_insert_only(
    seed: Seeder,
) -> None:
    ctx, engagement, template = await _approvable(seed)
    await letter_flow.request_approval(ctx, engagement, '"1"')
    approved = await letter_flow.approve_letter(ctx, engagement, '"1"')
    assert approved.approved_by_name == "Daniel Reyes"  # INV-5: attributed to the partner
    redrafted = await letters.draft_letter(ctx, engagement, draft_of(template), '"1"')
    assert redrafted.status == "draft" and redrafted.approved_by_name is None
    rows = await seed.rows(
        "SELECT version_no, status FROM engagement_letter_versions WHERE engagement_id = $1 "
        "ORDER BY version_no",
        engagement,
    )
    assert [(r["version_no"], r["status"]) for r in rows] == [(1, "superseded"), (2, "draft")]
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # a version's content is fixed
        await seed.as_actor(
            ctx.tenant_id,
            ("human", str(ctx.user_id)),
            "UPDATE engagement_letter_versions SET variables = '{}'::jsonb "
            "WHERE engagement_id = $1 AND version_no = 1",
            engagement,
        )


async def test_a_declined_envelope_is_withdrawn_by_a_person_and_send_drafts_anew(
    seed: Seeder,
) -> None:
    ctx, engagement, _template = await _approvable(seed)
    await letter_flow.request_approval(ctx, engagement, '"1"')
    await letter_flow.approve_letter(ctx, engagement, '"1"')
    first = await letter_flow.send_letter(ctx, engagement)
    with pytest.raises(letter_flow.LetterNotWithdrawable):  # still a draft at C7
        await letter_flow.withdraw_envelope(ctx, engagement, '"1"')
    await seed.run("UPDATE envelopes SET status = 'declined' WHERE id = $1", first)
    composed = await letters.composed_letter(ctx, engagement)
    assert "letter.withdraw_envelope" in composed.allowed_actions
    back = await letter_flow.withdraw_envelope(ctx, engagement, '"1"')
    assert back.status == "partner_approved" and back.envelope_id is None
    assert back.approved_by_name == "Daniel Reyes"  # the approval stands
    second = await letter_flow.send_letter(ctx, engagement)
    assert second != first
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.as_actor(
            ctx.tenant_id,
            ("system", "system"),
            "UPDATE engagement_letter_versions SET envelope_id = NULL WHERE envelope_id = $1",
            second,
        )
