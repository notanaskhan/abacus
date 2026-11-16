"""C-01-T24 (TASK-8301; C-01 §3 F8; CLS-06, POR-11) against Postgres: close issues and questions.

Row acceptance: "The Review badge reads 7 (2 + 5) with notes excluded, a question sends only
template wording and code facts, and Ben Ashby's answer marks the issue 'Client answered' and
fulfils the Sound Electric request." The fulfilment's upload half is the portal route's
(C-01-T27); here the answer records the request item it fulfils.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import replace

import pytest

from abacus.kernel import clock
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.closes import intake
from abacus.modules.closes import issues as close_issues
from abacus.modules.closes.contract_work import TransactionQuestionIn
from abacus.modules.requests.api import answer_transaction_question

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_c01t14_close_record import (
    _Firm,  # pyright: ignore[reportPrivateUsage] -- the rule under test
)
from .test_c01t19_close_intake import (
    BD1_0900_CT,
    _september,  # pyright: ignore[reportPrivateUsage] -- the published close fixture
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> AsyncIterator[_Firm]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    made = await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    await made.seed.run(
        "UPDATE firms SET time_zone = 'America/Chicago' WHERE tenant_id = $1", made.tenant
    )
    yield made
    await dispose_engine()


async def _queue(firm: _Firm, close: uuid.UUID) -> list[uuid.UUID]:
    ctx = firm.ctx()
    made: list[uuid.UUID] = []
    for n in range(2):
        made.append(
            await close_issues.raise_exception(
                ctx,
                close,
                severity="medium",
                issue_class="bank_rec",
                title=f"Medium {n}",
                account_ref="4410",
                register_line_ref=f"snap:{n}",
            )
        )
    for n in range(5):
        made.append(
            await close_issues.raise_exception(
                ctx, close, severity="low", issue_class="schedule", title=f"Low {n}", engine=False
            )
        )
    for n in range(4):
        await close_issues.add_note(ctx, close, issue_class="intake", title=f"Note {n}")
    return made


async def test_ac_the_review_badge_reads_7_with_notes_excluded(firm: _Firm) -> None:
    close, _, _ = await _september(firm)
    made = await _queue(firm, close)
    resolved = await close_issues.raise_exception(
        firm.ctx(), close, severity="medium", issue_class="flux", title="Shopify duplicate",
        engine=False,
    )  # fmt: skip
    await firm.seed.run("UPDATE issues SET status = 'resolved' WHERE id = $1", resolved)
    queue = await close_issues.close_issues(firm.ctx(), close)
    assert queue.open == 7
    assert queue.by_severity == {"high": 0, "medium": 2, "low": 5}
    assert queue.notes == 4
    assert {i.issue_id for i in queue.items} == set(made)
    shown = await close_issues.close_issues(firm.ctx(), close, include_resolved=True)
    assert resolved in {i.issue_id for i in shown.items}
    assert shown.open == 7
    medium = next(i for i in queue.items if i.title == "Medium 0")
    assert (medium.account_external_id, medium.register_line_ref) == ("4410", "snap:0")
    only = await close_issues.close_issues(firm.ctx(), close, issue_class="bank_rec")
    assert len(only.items) == 2 and only.open == 7


async def test_an_engine_exception_is_raised_once(firm: _Firm) -> None:
    close, _, _ = await _september(firm)

    async def once() -> uuid.UUID:
        return await close_issues.raise_exception(
            firm.ctx(),
            close,
            severity="low",
            issue_class="bank_rec",
            title="Outstanding check #2281 has not cleared",
            account_ref="4410",
            register_line_ref="snap:7",
        )

    assert await once() == await once()


async def _contact(firm: _Firm, close: uuid.UUID, user: uuid.UUID) -> uuid.UUID:
    client = await firm.seed.value(
        "SELECT e.client_id FROM closes c JOIN engagements e ON e.id = c.engagement_id "
        "WHERE c.work_item_id = $1",
        close,
    )
    return uuid.UUID(
        str(
            await firm.seed.value(
                "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind, user_id) "
                "VALUES ($1, $2, 'Ben Ashby', 'person', $3) RETURNING id",
                firm.tenant,
                client,
                user,
            )
        )
    )


async def test_ac_a_question_sends_only_template_wording_and_code_facts(firm: _Firm) -> None:
    close, _, _ = await _september(firm)
    with clock.frozen(BD1_0900_CT):
        await intake.publish_requests(firm.tenant, close)
    issue = await close_issues.raise_exception(
        firm.ctx(), close, severity="medium", issue_class="bank_rec",
        title="Sound Electric $3,200 against a usual 640", account_ref="4410",
        register_line_ref="snap:12",
    )  # fmt: skip
    ben = await firm.user("Ben Ashby")
    contact = await _contact(firm, close, ben)
    # An amount the engagement's ledger does not hold is outside its scope (ADR-065): refused.
    with pytest.raises(close_issues.OutOfScope):
        await close_issues.ask_question(
            firm.ctx(),
            issue,
            TransactionQuestionIn(
                template_id="close.question.unusual_payment",
                template_version=1,
                client_wording="Check #2285 for $3,200.00 to Sound Electric: what was it for?",
                assignee_contact_id=contact,
            ),
        )
    asked = await close_issues.ask_question(
        firm.ctx(),
        issue,
        TransactionQuestionIn(
            template_id="close.question.unusual_payment",
            template_version=1,
            client_wording="Please tell us what the Sound Electric payment was for.",
            assignee_contact_id=contact,
        ),
    )
    assert asked.status == "open" and asked.issue_id == issue
    (row,) = await firm.seed.rows(
        "SELECT template_id, context FROM transaction_questions WHERE id = $1", asked.question_id
    )
    assert row["template_id"] == "close.question.unusual_payment"
    assert '"register_line_ref": "snap:12"' in str(row["context"])
    queue = await close_issues.close_issues(firm.ctx(), close)
    item = next(i for i in queue.items if i.issue_id == issue)
    assert item.waiting_on_client and item.question_id == asked.question_id

    # Ben answers: the question reads answered (status vocabulary "Client answered").
    portal = replace(firm.ctx(ben), client=True)
    item_id = await firm.seed.value(
        "SELECT i.id FROM request_items i JOIN request_lists l ON l.id = i.request_list_id "
        "WHERE l.work_item_id = $1 ORDER BY i.id LIMIT 1",
        close,
    )
    answered = await answer_transaction_question(
        portal,
        asked.question_id,
        "Invoice attached: the walk-in cooler compressor.",
        fulfils_request_item_id=uuid.UUID(str(item_id)),
    )
    assert answered.status == "answered" and answered.fulfils_request_item_id == item_id
    after = await close_issues.close_issues(firm.ctx(), close)
    item = next(i for i in after.items if i.issue_id == issue)
    assert not item.waiting_on_client


async def test_only_the_addressed_contact_answers(firm: _Firm) -> None:
    close, _, _ = await _september(firm)
    with clock.frozen(BD1_0900_CT):
        await intake.publish_requests(firm.tenant, close)
    issue = await close_issues.raise_exception(
        firm.ctx(), close, severity="low", issue_class="bank_rec", title="Refund", engine=False
    )
    ben = await firm.user("Ben Ashby")
    contact = await _contact(firm, close, ben)
    asked = await close_issues.ask_question(
        firm.ctx(),
        issue,
        TransactionQuestionIn(
            template_id="close.question.unrecorded_deposit",
            template_version=1,
            client_wording="What was the August deposit from your dairy supplier?",
            assignee_contact_id=contact,
        ),
    )
    stranger = await firm.user("Someone Else")
    from abacus.kernel.errors import NotFound

    with pytest.raises(NotFound):
        await answer_transaction_question(
            replace(firm.ctx(stranger), client=True), asked.question_id, "Not mine"
        )
    with pytest.raises(NotFound):
        await answer_transaction_question(firm.ctx(), asked.question_id, "A firm member")
