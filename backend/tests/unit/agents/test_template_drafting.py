"""SPEC-035 Q3 (TASK-074): drafting on a template's items. The context names the item, its area
name and expected document, with the template's own guidance as tone examples and no year end;
approved drafted template guidance reaches engagements as `drafted`, with who approved."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from abacus.modules.agents.guidance_draft import (
    TEMPLATE_CONTEXT,
    _context,  # pyright: ignore[reportPrivateUsage] -- the builder under test
    template_examples,
    template_item,
)
from abacus.modules.engagements.api import (
    Area,
    MethodologyVersionView,
    TemplateItem,
    TemplateVersionSummary,
)
from abacus.modules.requests.guidance import Guidance, for_client, for_new_item


def _version(*items: TemplateItem) -> MethodologyVersionView:
    summary = TemplateVersionSummary(uuid.uuid4(), "Audit", uuid.uuid4(), 1, datetime.now(UTC))
    return MethodologyVersionView(
        summary, (Area("CASH", "Cash and bank"), Area("REV", "Revenue")), items, ()
    )


VERSION = _version(
    TemplateItem("CASH", "Bank statements for all accounts", "B"),
    TemplateItem("REV", "Sales contracts over $50k", "C", "To test revenue.", "Signed copies."),
    TemplateItem("REV", "Credit notes after year end", "C"),
)


def test_ac1_the_item_names_its_area_and_expected_document() -> None:
    assert template_item(VERSION, 0) == {
        "description": "Bank statements for all accounts",
        "audit_area": "Cash and bank",
        "expects": "bank_statement",
        "tier": "B",
    }
    assert template_item(VERSION, 3) is None
    assert template_item(VERSION, -1) is None


def test_q4_examples_are_the_template_s_own_guidance_on_other_items() -> None:
    assert template_examples(VERSION, 0) == [
        {
            "request": "Sales contracts over $50k",
            "why": "To test revenue.",
            "good_looks_like": "Signed copies.",
        }
    ]
    assert template_examples(VERSION, 1) == []


def test_q1_a_template_s_context_has_no_year_end() -> None:
    item = template_item(VERSION, 2)
    assert item is not None
    built = _context(TEMPLATE_CONTEXT, item, [], ["item", "examples"])
    text = built.render()
    assert "Year end" not in text
    assert text.count('<untrusted name="item">') == 1


def test_ac5_drafted_template_guidance_reaches_engagements_as_drafted() -> None:
    approver = uuid.uuid4()
    made = for_new_item(Guidance("Why.", "Good.", False, "small", "drafted", approver), None)
    assert (made.source, made.approved_by, made.why) == ("drafted", approver, "Why.")
    # The client display rule then applies (ADR-111): hidden unless the firm allows it.
    assert for_client(made.source, None, shown=False) == Guidance()
    assert for_client(made.source, None, shown=True) is None


def test_ac2_ordinary_template_guidance_stays_template() -> None:
    made = for_new_item(Guidance("Why.", "Good."), None)
    assert (made.source, made.approved_by) == ("template", None)
