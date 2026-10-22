"""P-01-T05 acceptance: "The same template version and variables render byte-identical output,
and an unknown variable is refused." The C16 renderer whitelist, from the contract."""

from __future__ import annotations

import pytest

from abacus.modules.communications.templates import (
    TemplateInvalid,
    TemplateVersion,
    UnknownTemplateVariable,
    check_source,
    content_sha256,
    render,
)

MENTION = TemplateVersion(
    "notification.mention",
    "en-US",
    1,
    "{{kind_sentence}}",
    "Hi {{recipient_first_name}},\n\n{{kind_sentence}} on {{engagement_display_name}}.\n"
    "Open it: {{app_link}}\n",
    ("app_link", "engagement_display_name", "kind_sentence", "recipient_first_name"),
)
VALUES = {
    "recipient_first_name": "Hannah",
    "kind_sentence": "Margaret mentioned you",
    "engagement_display_name": "Northwind 401(k) Plan 2025 audit",
    "app_link": "https://app.example.test/n/1",
}


def test_the_same_version_and_values_render_byte_identical_output() -> None:
    first, second = render(MENTION, VALUES), render(MENTION, dict(reversed(VALUES.items())))
    assert first == second
    assert first.subject.encode() == b"Margaret mentioned you"
    assert "Hi Hannah," in first.body_text and "{{" not in first.body_text


def test_an_unknown_variable_in_the_values_is_refused() -> None:
    with pytest.raises(UnknownTemplateVariable):
        render(MENTION, {**VALUES, "client_tin": "x"})


def test_a_missing_value_is_refused() -> None:
    values = dict(VALUES)
    values.pop("app_link")
    with pytest.raises(UnknownTemplateVariable):
        render(MENTION, values)


def test_an_import_may_use_only_whitelisted_declared_variables() -> None:
    with pytest.raises(UnknownTemplateVariable):
        check_source("notification.mention", "en-US", "Hi", "{{client_name}}", ["client_name"])
    with pytest.raises(UnknownTemplateVariable):  # used but not declared
        check_source("notification.mention", "en-US", "Hi", "{{app_link}}", [])
    check_source("notification.mention", "en-US", "Hi", "{{app_link}}", ["app_link"])


def test_stray_braces_line_breaks_and_bad_keys_are_refused() -> None:
    with pytest.raises(TemplateInvalid):
        check_source("notification.mention", "en-US", "Hi", "{{ app_link", [])
    with pytest.raises(TemplateInvalid):
        check_source("notification.mention", "en-US", "Hi\nBcc: x", "Body", [])
    with pytest.raises(TemplateInvalid):
        check_source("Notification", "en-US", "Hi", "Body", [])
    with pytest.raises(TemplateInvalid):
        render(MENTION, {**VALUES, "recipient_first_name": "Hannah\r\nBcc: x"})


def test_the_content_hash_ignores_declaration_order() -> None:
    a = content_sha256("notification.mention", "en-US", "S", "B", ["app_link", "kind_sentence"])
    b = content_sha256("notification.mention", "en-US", "S", "B", ["kind_sentence", "app_link"])
    assert a == b and len(a) == 64
