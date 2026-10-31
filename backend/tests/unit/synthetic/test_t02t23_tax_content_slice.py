"""T-02-T23 (TASK-2429; T-02 §5; POR-05, TXP-12, POR-13; DEC-1477): the `tax_content` slice.

The row's acceptance holds its figures as seed tests: Ridgeline's five K-1s, Bluestem's two and
Calloway's two; Bluestem's shareholders foot 70/30 to TXP-12 C's totals and Calloway's
beneficiaries to D's; the organizer foots 4 + 5 + 2 + 2 + 1 + 2 + 2 + 2 + 4 = 24 with 22 answered,
POR-05's three open questions are the team question and the two organizer ones, and the asks
carry Dana's four inquiries and Luis's two questions. Every K-1 set and the organizer survive the
import parsers the routes run (`k1_set`, the template CSV), no full TIN appears, and nothing in
the slice is a migration: it loads through the loader's events only.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from abacus.modules.requests.questionnaire_templates import parse as parse_template
from abacus.modules.tax.engine_adapter import parse_pdf
from abacus.modules.tax.k1_packages import parse_k1_set
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_content import (
    ASKS,
    BLUESTEM,
    CALLOWAY,
    K1_SETS,
    ORGANIZER,
    RIDGELINE,
    SHARES,
    SLICE,
    organizer_csv,
    set_of,
)

MIGRATIONS = Path(__file__).resolve().parents[3] / "migrations" / "versions"


def _box(client: str, ref: str, code: str) -> Decimal:
    recipient = next(r for r in set_of(client).recipients if r.ref == ref)
    return Decimal(next(b.amount for b in recipient.boxes if b.code == code))


def test_ac1_the_k1_sets_hold_five_two_and_two_recipients() -> None:
    assert [len(set_of(c).recipients) for c in (RIDGELINE, BLUESTEM, CALLOWAY)] == [5, 2, 2]
    assert [r.name for r in set_of(RIDGELINE).recipients] == [
        "Ridgeline GP LLC",
        "Meera Shah",
        "Pell Street Ventures LLC",
        "Pell Street II LLC",
        "Jonah Feld",
    ]
    assert [ref for ref, _ in SHARES] == ["P05"]  # the Feld 1040 (Shah's waits, DEC-1477)


def test_ac1_bluestem_foots_70_30_and_calloway_two_to_one() -> None:
    for code, total in (("1", 860_000), ("4", 12_400), ("16C", 4_200), ("16D", 620_000)):
        arjun, sunita = _box(BLUESTEM, "S01", code), _box(BLUESTEM, "S02", code)
        assert arjun + sunita == total
        assert arjun == total * Decimal("0.7")
    for code in ("1", "2a", "2b"):
        assert _box(CALLOWAY, "B01", code) == 2 * _box(CALLOWAY, "B02", code)
    # TXP-12's expanded row: Jonah Feld's drafted boxes.
    assert _box(RIDGELINE, "P05", "2") == 307_900
    assert _box(RIDGELINE, "P05", "19A") == 150_000


def test_every_set_and_pdf_parses_as_the_bridge_reads_it_and_no_full_tin_appears() -> None:
    for k1_set in K1_SETS:
        found = parse_k1_set(k1_set.manifest())
        assert len(found.recipients) == len(k1_set.recipients)
        assert found.is_final == k1_set.is_final
        for recipient in k1_set.recipients:
            parsed = parse_pdf(k1_set.pdf_name(recipient), b"%PDF-1.4\n%%EOF\n")
            assert parsed.kind == "k1"
            assert parsed.engine_return_id == k1_set.engine_return_id
            assert recipient.tin_last4 is None or len(recipient.tin_last4) == 4


def test_ac1_the_organizer_foots_to_24_with_22_answered() -> None:
    template = parse_template(organizer_csv(), "csv")
    counts = [len(s.questions) for s in template.sections]
    assert counts == [4, 5, 2, 2, 1, 2, 2, 2, 4]
    assert sum(counts) == len(ORGANIZER) == 24
    answered = [q for q in ORGANIZER if q.answer is not None]
    assert len(answered) == 22
    open_ = [q.wording for q in ORGANIZER if q.answer is None]
    assert open_ == [
        "Did you or Jonah contribute to an IRA, HSA or 529 plan for 2025?",
        "At any time in 2025, did either of you have a financial interest in, or signature "
        "authority over, a bank or brokerage account outside the United States?",
    ]


def test_ac1_the_asks_carry_kevins_dana_s_and_luis_s_questions() -> None:
    assert [(a.label, len(a.questions)) for a in ASKS] == [
        ("feld-digital-asset", 1),
        ("northwind-fraud-inquiries", 4),
        ("granite-peak-analytics", 2),
    ]
    inquiry = next(a for a in ASKS if a.kind == "inquiry")
    assert inquiry.addressee == "Dana Kowalski" and inquiry.due == "2026-09-18"


def test_the_slice_is_events_in_order_and_no_content_is_a_migration() -> None:
    events = slice_events(SLICE)
    kinds = [e.kind for e in sorted(events, key=lambda e: e.at)]
    assert kinds.index("tax.k1_contact_created") < kinds.index("tax.k1_set_imported")
    assert kinds.index("tax.engine_pdf_imported") < kinds.index("tax.k1_set_imported")
    assert kinds.index("requests.organizer_imported") < kinds.index("requests.organizer_answered")
    assert kinds.count("requests.organizer_answered") == 22
    for path in MIGRATIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "Pell Street" not in text and "2025 Tax Organizer" not in text, path.name
