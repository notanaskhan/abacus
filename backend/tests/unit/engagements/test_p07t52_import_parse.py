"""P-07-T52: reading a client list (ADR-052; DEC-643). Pure: no database."""

from __future__ import annotations

import pytest

from abacus.modules.engagements.client_import_parse import (
    MAX_ROWS,
    ImportFileInvalid,
    clean_cell,
    parse_client_list,
)

HEAD = "Client Name,Client Type,Federal ID Number,Primary Contact,Email Address\n"


def test_cch_headings_map_to_fields() -> None:
    parsed = parse_client_list(
        (
            HEAD + "Copperleaf Outfitters,S Corporation,98-4512345,Tess Moreno,t@example.test\n"
        ).encode(),
        "cch_axcess_tax_export",
    )
    assert parsed.mapping == {
        "Client Name": "client_name",
        "Client Type": "entity_type",
        "Federal ID Number": "ein",
        "Primary Contact": "contact_name",
        "Email Address": "email",
    }
    (row,) = parsed.rows
    assert (row.client_name, row.entity_type, row.contact_name, row.email) == (
        "Copperleaf Outfitters",
        "s_corp",
        "Tess Moreno",
        "t@example.test",
    )
    assert row.tin is not None and (row.tin.kind, row.tin.digits[-4:]) == ("ein", "2345")


@pytest.mark.parametrize(
    ("raw", "kind"),
    [("98-4512345", "ein"), ("984512345", "ein"), ("912-70-0001", "itin")],
)
def test_the_federal_id_form_says_its_kind(raw: str, kind: str) -> None:
    (row,) = parse_client_list((HEAD + f"A,Individual,{raw},,\n").encode(), "csv").rows
    assert row.tin is not None and row.tin.kind == kind


def test_hostile_cells_are_inert_and_noted() -> None:
    text, notes = clean_cell('=HYPERLINK("x") ‮Quill⁦')
    assert "‮" not in text and "⁦" not in text
    assert text.startswith("=HYPERLINK")
    assert notes == {"bidi_removed", "formula_like"}
    for lead in ("+1", "-1", "@SUM(A1)"):
        assert "formula_like" in clean_cell(lead)[1]


def test_a_tin_in_a_name_is_scrubbed() -> None:
    (row,) = parse_client_list((HEAD + "Ann Lee 912-70-0001,,,,\n").encode(), "csv").rows
    assert (
        "912" not in row.client_name and "70-0001" not in row.client_name
    )  # masked, last four kept
    assert "tin_in_text" in row.notes


def test_unknown_types_and_bad_emails_are_noted_not_kept() -> None:
    (row,) = parse_client_list((HEAD + "A,Cooperative,,,not-an-email\n").encode(), "csv").rows
    assert row.entity_type is None and row.email is None
    assert {"entity_type_unknown", "email_invalid"} <= set(row.notes)


@pytest.mark.parametrize(
    ("content", "source", "code"),
    [
        (b"", "csv", "empty_file"),
        (b"\xff\xfe\x00", "csv", "not_utf8_csv"),
        (b"Name,Type\nA,LLC\n", "cch_axcess_tax_export", "not_cch_export"),
        (b"Code,Type\nA1,LLC\n", "csv", "no_name_column"),
        (HEAD.encode(), "csv", "no_rows"),
        ((HEAD + "A,,,,\n" * (MAX_ROWS + 1)).encode(), "csv", "too_many_rows"),
    ],
)
def test_unreadable_files_are_refused_with_a_code(content: bytes, source: str, code: str) -> None:
    with pytest.raises(ImportFileInvalid) as refused:
        parse_client_list(content, source)  # pyright: ignore[reportArgumentType] -- a source code from the parametrize
    assert refused.value.code == code
