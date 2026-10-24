"""P-06-T14 (DEC-220): the follow-up variables of the C16 renderer. `firm_name` is a single-line
value like the others; `request_list` is the one block variable: one request per line, in a
body only, never blank, never a carriage return."""

from __future__ import annotations

import pytest

from abacus.modules.communications.templates import (
    TemplateInvalid,
    TemplateVersion,
    UnknownTemplateVariable,
    check_source,
    render,
)

SUBJECT = "{{firm_name}} is still waiting on {{engagement_display_name}}"
BODY = (
    "Hi {{recipient_first_name}},\n\n{{firm_name}} is still waiting for:\n\n{{request_list}}\n\n"
    "Open your list: {{app_link}}\n"
)
NAMES = [
    "app_link",
    "engagement_display_name",
    "firm_name",
    "recipient_first_name",
    "request_list",
]
REMINDER = TemplateVersion("notification.follow_up_sent", "en-US", 1, SUBJECT, BODY, tuple(NAMES))
VALUES = {
    "recipient_first_name": "Claire",
    "engagement_display_name": "Claire Feld · 2025 Form 1040",
    "firm_name": "Brightwater Hale",
    "app_link": "https://portal.example.test/client/engagements/1",
    "request_list": "- Brokerage statements\n- Form 1098",
}


def test_a_follow_up_template_imports_with_its_variables() -> None:
    check_source("notification.follow_up_sent", "en-US", SUBJECT, BODY, NAMES)


def test_the_request_list_renders_one_line_per_request_byte_identically() -> None:
    first = render(REMINDER, VALUES)
    assert first == render(REMINDER, dict(reversed(VALUES.items())))
    assert "- Brokerage statements\n- Form 1098\n" in first.body_text
    assert first.subject == "Brightwater Hale is still waiting on Claire Feld · 2025 Form 1040"


def test_a_block_variable_is_refused_in_a_subject() -> None:
    with pytest.raises(TemplateInvalid):
        check_source("notification.follow_up_sent", "en-US", "{{request_list}}", BODY, NAMES)


@pytest.mark.parametrize(
    "value", ["", "- Brokerage statements\n\n- Form 1098", "- Brokerage\r\n- Form 1098"]
)
def test_a_blank_or_carriage_return_request_list_is_refused(value: str) -> None:
    with pytest.raises(TemplateInvalid):
        render(REMINDER, {**VALUES, "request_list": value})


def test_firm_name_stays_single_line() -> None:
    with pytest.raises(TemplateInvalid):
        render(REMINDER, {**VALUES, "firm_name": "Brightwater\nHale"})


def test_an_unlisted_variable_is_still_refused() -> None:
    with pytest.raises(UnknownTemplateVariable):
        check_source(
            "notification.follow_up_sent",
            "en-US",
            SUBJECT,
            BODY + "{{amount}}",
            [*NAMES, "amount"],
        )
