"""R-01-T23 (TASK-1420; R-01 Story 7.2): the rules the lint adds to T19's: an attachment, a
second button and the banned words (the glossary's client-email bans and scope-guards' banned
terms, read from the generated copy beside the lint, which must match the source)."""

from __future__ import annotations

import pytest

from abacus.modules.communications.lint import lint_template, scope_guard_terms
from abacus.modules.communications.render import Block, TemplateContent
from abacus.modules.communications.template_keys import REMINDER
from abacus_tools.quality import scope_guards


def _with(text: str, *, label: str = "Open documents") -> TemplateContent:
    return TemplateContent(
        subject="Your {work_item}",
        preheader="",
        blocks=(Block("p1", "paragraph", text),),
        cta_label=label,
        cta_target="documents",
    )


def _facts(content: TemplateContent) -> set[str]:
    return {f.fact() for f in lint_template(content, REMINDER)}


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("The statement is attached.", "attachment"),
        ("See the enclosed letter.", "attachment"),
        ("Click here to upload.", "second_button"),
        ("[Upload now]", "second_button"),
        ("Open documents", "second_button"),  # the button's label again, as a block
        ("Ask the agent in your portal.", "banned_word"),
        ("Our AI read your files.", "banned_word"),
        ("One task left.", "banned_word"),
        ("An issue with your return.", "banned_word"),
        ("Your password is safe.", "banned_word"),
        ("Approved by Accrued Agent", "banned_word"),  # a scope-guards term
        ("ask the planner agent", "banned_word"),  # in any case (security review L3)
        ("Our TAX EXPORT is done.", "banned_word"),
    ],
)
def test_the_new_rules_name_the_block_never_the_text(text: str, code: str) -> None:
    facts = _facts(_with(text))
    assert f"{code}:p1" in facts
    assert all(text not in fact for fact in facts)


@pytest.mark.parametrize(
    "text",
    [
        "Hi {client_first_name}, please upload the files to your portal.",
        "Questions? Message {staff_name} in your portal.",
        "The IRS issued a notice; we will look at it.",  # "issued" is not "issue"
        "Drop the files in your portal and they'll be sorted for you.",
        "Our departmental team will be in touch.",  # whole words only: not "Departments"
    ],
)
def test_ordinary_client_words_pass(text: str) -> None:
    assert _facts(_with(text)) == set()


def test_the_runtime_terms_match_scope_guards_yaml() -> None:
    expected = sorted({t["term"] for t in scope_guards.load().terms})
    assert list(scope_guard_terms()) == expected
    assert scope_guards.EMAIL_TERMS.read_text() == scope_guards.email_terms()
