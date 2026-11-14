"""Ridgeline's preparer memo as drafted on Sep 10 (T-05-T62; TASK-7942; TXP-01 verbatim; DEC-4937).

The scenario's recorded draft: each section's text exactly as the TXP-01 handoff shows it, with
the source position its citation marker names ([1]-[6]; none where the artboard shows none). The
memo service stores it as one agent-drafted version through its synthetic-only recorder; the
fingerprint is code's over the facts then, so the 9:51 fix turns the approved memo Stale by code.
"""

from __future__ import annotations

from typing import Final

# (section key, text, the cited source's position or None)
SECTIONS: Final[tuple[tuple[str, str, int | None], ...]] = (
    (
        "overview",
        "The partnership owns three rental properties: Elm Street (Chicago, commercial), Larimer "
        "Lofts (Denver, residential) and Bergen Street (Brooklyn, residential). Books are kept on "
        "the income-tax basis. Partners at year-end: Ridgeline GP LLC (GP, 2%), Meera Shah (38%), "
        "Pell Street Ventures LLC (30%), Pell Street II LLC (5%) and Jonah Feld (25%).",
        1,
    ),
    (
        "structural_events",
        "On 6/30/2025 Pell Street Ventures LLC sold 5 points to Pell Street II LLC for $360,000. "
        "Items are allocated under §706(d) using the interim-closing method with a monthly "
        "convention. Pell Street II succeeds to 5/35 of Pell Street Ventures' 6/30 capital of "
        "2,319,835 (including 1,085 of first-half tax-exempt interest, per Reg. "
        "§1.704-1(b)(2)(iv)(l)) = 331,405; the 28,595 excess of price over capital is a §743(b) "
        "placeholder pending the partners' §754 decision, which must be attached to this timely "
        "filed return. Jonah Feld contributed 250,000 during 2025.",
        2,
    ),
    (
        "book_to_tax",
        "AJE-1 accrues the December real estate tax installment of 18,500. TJE-1 moves "
        "tax-exempt interest of 6,200 to Schedule K line 18a. Total assets of 17,914,500 make "
        "Schedule M-3 required.",
        3,
    ),
    (
        "depreciation",
        "2025 depreciation is 733,500: buildings 480,000; Elm Street roof 9,500 (39-year, "
        "mid-month); Larimer parking lot 180,000 (15-year, 100% bonus, acquired after Jan 19, "
        "2025); Bergen Street appliances 64,000 (5-year, 100% bonus).",
        4,
    ),
    (
        "liabilities_752",
        "Ridgeline GP LLC is an LLC, so no partner bears the economic risk of loss; all "
        "11,048,300 of liabilities are nonrecourse and shared by year-end profit percentages. The "
        "10,712,500 mortgage is qualified nonrecourse financing.",
        5,
    ),
    (
        "states_ptet",
        "Sourced by property: Illinois 46.0% (566,536), Colorado 31.5% (387,954), New York 22.5% "
        "(277,110). PTET elected in all three: IL 28,044 · CO 17,070 · NY 18,982, paid Mar 12, "
        "2026 with the state extensions (no 2025 estimates were made), so the deduction falls in "
        "TY2026.",
        6,
    ),
    (
        "distributions",
        "One cash distribution of 600,000 on Dec 15, 2025, by year-end percentages.",
        None,
    ),
    (
        "open_items",
        "Schedule M-2 is off 6,200: tax-exempt interest is missing from the capital rollforward "
        "(review point). §754 decision outstanding (waiting on the client, due with the return "
        "Sep 15). K-1s are drafts, shared internally with the Feld and Shah 1040s; release "
        "follows partner approval.",
        None,
    ),
    (
        "opportunities",
        "Cost segregation study — Elm Street. §754 election. NYC PTET for TY2027.",
        None,
    ),
)

__all__ = ["SECTIONS"]
