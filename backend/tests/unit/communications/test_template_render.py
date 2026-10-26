"""The block renderer and the publish lint (R-01-T19; TASK-1352): pure, deterministic, escaped,
one link only through the button, variables only from the key's whitelist."""

from __future__ import annotations

import pytest

from abacus.modules.communications.lint import lint_template
from abacus.modules.communications.render import (
    Block,
    TemplateContent,
    content_sha256,
    render_email,
)
from abacus.modules.communications.template_keys import RECONNECT_REQUEST, REMINDER
from abacus.modules.communications.template_registry import VARIABLES, lint_values
from abacus.modules.communications.templates import TemplateInvalid, UnknownTemplateVariable

LINK = "http://localhost:5173/sign-in#link=Token0123456789"  # the test environment's portal
ALLOWED = frozenset(REMINDER.variables)
BLOCKS = frozenset(n for n, v in VARIABLES.items() if v.block)
VALUES = {
    "client_first_name": "Claire",
    "firm_name": "Probe & Co",
    "work_item": "2025 tax return",
    "open_items": "Form W-2\nForm 1099-INT",
    "due_date": "Sep 21",
    "portal_link": LINK,
    "staff_name": "Marcus",
}
CONTENT = TemplateContent(
    subject="{work_item}: {client_first_name}",
    preheader="Still open",
    blocks=(
        Block("h", "heading", "Hi {client_first_name}"),
        Block("p", "paragraph", "From {firm_name}"),
        Block("l", "item_list", "{open_items}"),
        Block("n", "note", "Ask {staff_name}"),
        Block("f", "footer", "Sent for {firm_name}"),
    ),
    cta_label="Open documents",
    cta_target="documents",
)


def test_ac9_the_same_content_and_values_are_byte_identical() -> None:
    first = render_email(CONTENT, VALUES, allowed=ALLOWED, block_variables=BLOCKS)
    second = render_email(
        CONTENT, dict(reversed(VALUES.items())), allowed=ALLOWED, block_variables=BLOCKS
    )
    assert first == second
    assert first.text == (
        "Hi Claire\n\nFrom Probe & Co\n\n- Form W-2\n- Form 1099-INT\n\n"
        f"Open documents: {LINK}\n\nAsk Marcus\n\nSent for Probe & Co\n"
    )
    assert content_sha256("reminder", "en-US", CONTENT) == content_sha256(
        "reminder", "en-US", CONTENT
    )


def test_ac9_values_are_escaped_and_the_button_is_the_only_link() -> None:
    rendered = render_email(
        CONTENT,
        {**VALUES, "client_first_name": '<script>x</script>"'},
        allowed=ALLOWED,
        block_variables=BLOCKS,
    )
    assert "<script>" not in rendered.html and "&lt;script&gt;" in rendered.html
    assert rendered.html.count("<a ") == 1 and f'href="{LINK}"' in rendered.html
    # The button goes before the first note.
    assert rendered.html.index("Open documents") < rendered.html.index("Ask Marcus")


def test_ac9_390_is_the_same_html_with_a_full_width_button() -> None:
    wide = render_email(CONTENT, VALUES, allowed=ALLOWED, block_variables=BLOCKS, width=600)
    narrow = render_email(CONTENT, VALUES, allowed=ALLOWED, block_variables=BLOCKS, width=390)
    assert wide.text == narrow.text and "max-width:390px" in narrow.html
    assert "width:100%;box-sizing:border-box" in narrow.html
    assert "width:100%;box-sizing:border-box" not in wide.html


@pytest.mark.parametrize(
    "values",
    [
        {"connection_name": "American Express"},  # not this key's
        {"client_first_name": "Claire\nBcc: x@example.test"},  # a value adds a line
        {"portal_link": "javascript:alert(1)"},  # not a secure link
        {"portal_link": "https://evil.example.com/sign-in#link=x"},  # not the portal (M3)
        {"portal_link": "http://localhost:5173/sign-in?link=x"},  # never a query string
    ],
)
def test_ac9_refused_values(values: dict[str, str]) -> None:
    with pytest.raises((UnknownTemplateVariable, TemplateInvalid)):
        render_email(CONTENT, {**VALUES, **values}, allowed=ALLOWED, block_variables=BLOCKS)


def test_ac9_a_missing_value_or_a_stray_brace_is_refused() -> None:
    with pytest.raises(UnknownTemplateVariable):
        render_email(
            CONTENT,
            {k: v for k, v in VALUES.items() if k != "staff_name"},
            allowed=ALLOWED,
            block_variables=BLOCKS,
        )
    stray = TemplateContent("S {", "", (), None, None)
    with pytest.raises(TemplateInvalid):
        render_email(stray, VALUES, allowed=ALLOWED, block_variables=BLOCKS)
    misplaced = TemplateContent("S", "", (Block("p", "paragraph", "{open_items}"),), None, None)
    with pytest.raises(TemplateInvalid):
        render_email(misplaced, VALUES, allowed=ALLOWED, block_variables=BLOCKS)


def test_ac9_the_lint_names_the_rule_and_the_block_never_the_text() -> None:
    bad = TemplateContent(
        "Refund {balance_due}",
        "",
        (
            Block("a", "paragraph", "We received $3,200."),
            Block("b", "paragraph", "TIN 912-34-5678 on account ••4436."),
            Block("c", "footer", "Powered by Accrued"),
            Block("d", "paragraph", "{open_items}"),
        ),
        None,
        None,
    )
    found = {f.fact() for f in lint_template(bad, REMINDER)}
    assert found == {
        "unregistered_variable:subject",
        "amount:a",
        "tin_shape:b",
        "account_number:b",
        "platform_name:c",
        "unregistered_variable:d",
    }
    assert lint_template(CONTENT, REMINDER) == []
    assert {f.fact() for f in lint_template(CONTENT, RECONNECT_REQUEST)} >= {
        "unregistered_variable:subject"
    }


# --- the security review's fixes (M3, L2) ------------------------------------------------------


def test_ac9_portal_link_goes_only_in_the_button() -> None:
    inline = TemplateContent(
        "S", "", (Block("p", "paragraph", "Open {portal_link}"),), "Open", "documents"
    )
    with pytest.raises(TemplateInvalid):
        render_email(inline, VALUES, allowed=ALLOWED, block_variables=BLOCKS)
    assert {f.fact() for f in lint_template(inline, REMINDER)} == {"foreign_link:p"}


@pytest.mark.parametrize(
    "text",
    ["See https://evil.example.com", "Visit www.example.org", "Write to help@example.com"],
)
def test_ac9_firm_text_carries_no_address_of_its_own(text: str) -> None:
    bad = TemplateContent("S", "", (Block("p", "paragraph", text),), None, None)
    assert "foreign_link:p" in {f.fact() for f in lint_template(bad, REMINDER)}


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Powered by Acc\u200brued", "platform_name"),  # a zero-width space inside the name
        ("SSN 912 34 5678", "tin_shape"),
        ("SSN 912.34.5678", "tin_shape"),
        ("SSN \uff19\uff11\uff12-34-5678", "tin_shape"),  # full-width digits
        ("A refund of USD 5000", "amount"),
        ("A refund of 5000 dollars", "amount"),
    ],
)
def test_ac9_the_shapes_are_read_after_folding(text: str, code: str) -> None:
    bad = TemplateContent("S", "", (Block("p", "paragraph", text),), None, None)
    assert f"{code}:p" in {f.fact() for f in lint_template(bad, REMINDER)}
    assert code in {f.code for f in lint_values({"work_item": text})} or code == "platform_name"


# --- the re-review: links in client-written values, separators, folding ------------------------


@pytest.mark.parametrize(
    "title", ["Pay at https://evil-pay.com", "See www.evil-pay.com", "Write to pay@evil-pay.com"]
)
def test_ac9_a_value_with_a_link_or_address_is_refused(title: str) -> None:
    assert ("foreign_link", "work_item") in {
        (f.code, f.variable) for f in lint_values({"work_item": title})
    }


def test_ac9_a_bare_domain_in_a_value_is_defanged_and_a_file_name_is_not() -> None:
    assert lint_values({"work_item": "W-2.pdf", "document_title": "Brokerage 1099.pdf"}) == []
    rendered = render_email(
        CONTENT,
        {**VALUES, "work_item": "pay at evil-pay.com", "open_items": "W-2.pdf\nK-1 report.xlsx"},
        allowed=ALLOWED,
        block_variables=BLOCKS,
    )
    for part in (rendered.subject, rendered.html, rendered.text):
        assert "evil-pay.com" not in part
    assert "evil-pay[.]com" in rendered.subject and "W-2.pdf" in rendered.text
    assert "K-1 report.xlsx" in rendered.text


@pytest.mark.parametrize("bad", ["\x00", "\x85", "\u2028", "\u2029"])
def test_ac9_a_value_with_any_line_break_or_nul_is_refused(bad: str) -> None:
    with pytest.raises(TemplateInvalid):
        render_email(
            CONTENT,
            {**VALUES, "client_first_name": f"Claire{bad}Bcc"},
            allowed=ALLOWED,
            block_variables=BLOCKS,
        )


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("SSN 912\u201334\u20135678", "tin_shape"),  # en dashes
        ("SSN 912\u201434\u20145678", "tin_shape"),  # em dashes
        ("SSN 912\u221234\u22125678", "tin_shape"),  # minus signs
        ("SSN 912/34/5678", "tin_shape"),
        ("Powered by Accru\u0301ed", "platform_name"),  # a combining accent
    ],
)
def test_ac9_dash_variants_and_combining_marks_are_folded(text: str, code: str) -> None:
    bad = TemplateContent("S", "", (Block("p", "paragraph", text),), None, None)
    assert f"{code}:p" in {f.fact() for f in lint_template(bad, REMINDER)}
