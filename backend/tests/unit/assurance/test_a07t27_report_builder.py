"""A-07-T27 (TASK-6312; A-07 F5; AU-C 700, 705, 706, 720; DEC-3012): the report builder.

Row acceptance: "An agent PATCH of opinion_form is refused at every layer, Qualified without a
decided card answers 409 decision_required, and two DOCX renders of v2 are byte-identical."
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
import yaml

from abacus.kernel.db import ActorKind, TenantContext
from abacus.modules.assurance import report_builder as rb
from abacus.modules.identity.api import AuthContext, Forbidden

ENGAGEMENT, WORK_ITEM = uuid.uuid4(), uuid.uuid4()
CLAUSES = (
    ("opinion_unmodified", True),
    ("opinion_qualified", False),
    ("basis_unmodified", True),
    ("basis_qualified", False),
    ("eom_going_concern", False),
    ("erisa_supplemental", False),
    ("other_information", False),
    ("firm_closing", True),
)


def _ctx(kind: ActorKind = "human") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)), user, uuid.uuid4(), None, None
    )


@dataclass(frozen=True)
class Card:
    card_id: uuid.UUID
    kind: str
    question_key: str
    option_key: str
    decided_by: uuid.UUID
    decided_at: datetime


async def test_ac_qualified_without_a_decided_card_is_409(monkeypatch: pytest.MonkeyPatch) -> None:
    async def none(*_: object, **__: object) -> list[Card]:
        return []

    monkeypatch.setattr(rb, "decided_cards", none)
    with pytest.raises(rb.DecisionRequired):
        await rb.validate(_ctx(), ENGAGEMENT, WORK_ITEM, rb.default_choices(),
                          "opinion_form", "qualified", None)  # fmt: skip


async def test_qualified_with_the_eps_decided_card_is_taken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = Card(
        uuid.uuid4(), "opinion", rb.OPINION_CARD, "qualified", uuid.uuid4(), datetime.now(UTC)
    )

    async def decided(*_: object, **__: object) -> list[Card]:
        return [card]

    monkeypatch.setattr(rb, "decided_cards", decided)
    choice = await rb.validate(_ctx(), ENGAGEMENT, WORK_ITEM, rb.default_choices(),
                               "opinion_form", "qualified", None)  # fmt: skip
    assert (choice.value, choice.decision_card_id) == ("qualified", card.card_id)
    with pytest.raises(rb.DecisionRequired):  # a card for another form doesn't count
        await rb.validate(_ctx(), ENGAGEMENT, WORK_ITEM, rb.default_choices(),
                          "opinion_form", "adverse", None)  # fmt: skip


async def test_ac_an_agent_patch_of_the_opinion_is_refused_in_the_service() -> None:
    with pytest.raises(Forbidden):
        await rb.validate(_ctx("agent"), ENGAGEMENT, WORK_ITEM, rb.default_choices(),
                          "opinion_form", "unmodified", None)  # fmt: skip


def test_ac_an_agent_patch_of_the_opinion_is_refused_by_the_matrix() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    matrix = yaml.safe_load(
        (root / "docs/architecture/permission-matrix/assurance.yaml").read_text()
    )
    for action in ("report.draft", "report.request_decision"):
        row = matrix["actions"].get(action)
        if row is not None:
            assert row.get("agent") in ("deny", "task_scope"), action


async def test_going_concern_is_locked_and_toggles_carry_their_codes() -> None:
    with pytest.raises(rb.ChoiceLocked):
        await rb.validate(_ctx(), ENGAGEMENT, WORK_ITEM, rb.default_choices(),
                          "going_concern", False, None)  # fmt: skip
    choice = await rb.validate(_ctx(), ENGAGEMENT, WORK_ITEM, rb.default_choices(),
                               "erisa_supplemental_schedules", True, None)  # fmt: skip
    assert choice.reason_code == "ERISA-SUPP"
    with pytest.raises(rb.ChoiceInvalid):
        await rb.validate(_ctx(), ENGAGEMENT, WORK_ITEM, rb.default_choices(),
                          "free_text", "anything", None)  # fmt: skip


def test_paragraphs_follow_the_choices_and_keep_the_firms_own() -> None:
    choices = {
        **rb.default_choices(),
        "opinion_form": rb.Choice("opinion_form", "qualified"),
        "going_concern": rb.Choice("going_concern", True, "AUD-19 going concern"),
        "other_information": rb.Choice("other_information", True, None, None, "OM-OTHER"),
    }
    paras = {p.block_id: p for p in rb.paragraphs(CLAUSES, choices)}
    assert paras["opinion_qualified"].included and not paras["opinion_unmodified"].included
    assert paras["basis_qualified"].included
    assert (
        paras["eom_going_concern"].included and paras["eom_going_concern"].reason_code == "EOM-GC"
    )
    assert paras["other_information"].reason_code == "OM-OTHER"
    assert paras["firm_closing"].included  # the firm's own clause keeps its default


def test_ac_the_same_version_hashes_and_renders_the_same() -> None:
    template = uuid.uuid4()
    choices = rb.default_choices()
    paras = rb.paragraphs(CLAUSES, choices)
    assert rb.canonical(template, choices, paras)[2] == rb.canonical(template, choices, paras)[2]


def test_ac_two_docx_renders_of_one_version_are_byte_identical() -> None:
    from abacus.modules.reporting.api import RenderInput, render_docx

    request = RenderInput(
        layout_key="report",
        blocks=[{"type": "paragraph", "runs": [{"type": "text", "text": "Opinion"}]}],
        values={"signature": "[Signature]"},
        title="Independent auditor's report",
        as_of=datetime(2026, 10, 2, tzinfo=UTC),
        mode="draft",
        content_hash="a" * 64,
    )
    assert render_docx(request).docx == render_docx(request).docx


def test_word_counts_count_blocks_switched() -> None:
    before = [rb.Paragraph("a", True), rb.Paragraph("b", False)]
    after = [rb.Paragraph("a", False), rb.Paragraph("b", True), rb.Paragraph("c", True)]
    assert rb.word_counts(before, after) == (2, 1)
