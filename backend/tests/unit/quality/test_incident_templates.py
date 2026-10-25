"""Q-01-T42: the status-page content and incident templates (`docs/ops/incident-templates.md`).
"No portal-facing text contains a firm, client or Accrued name": the portal banner wording names
no product and no firm, client or person; the incident templates name no firm, client or person;
the components are SHL-05's names in its order; and the status words are the canonical ones."""

from __future__ import annotations

import re
from pathlib import Path

DOC = Path(__file__).resolve().parents[4] / "docs" / "ops" / "incident-templates.md"
TEXT = DOC.read_text(encoding="utf-8")
SHL_05 = (
    "Accrued app",
    "Agents & Workbench",
    "Client portal",
    "E-signature & identity verification",
    "CCH Axcess Tax export",
    "QuickBooks Online sync",
    "Microsoft 365 mail ingest",
)
# The synthetic cast (DEC-27) and the product's names: none may appear where a client reads.
NAMES = re.compile(
    r"accrued|abacus|brightwater|hale\b|canary|felix|hannah|claire|feld\b|margaret|okonkwo",
    re.IGNORECASE,
)
PLACEHOLDER_FOR_A_PARTY = re.compile(r"\[(firm|client|person|name|user|email)[^\]]*\]", re.I)


def _between(start: str, end: str) -> str:
    return TEXT[TEXT.index(start) + len(start) : TEXT.index(end)]


def test_the_portal_banner_names_no_product_firm_client_or_person() -> None:
    banner = _between("<!-- portal-banner:start -->", "<!-- portal-banner:end -->")
    assert banner.count("\n- ") == 3
    assert not NAMES.search(banner)
    assert not PLACEHOLDER_FOR_A_PARTY.search(banner)


def test_the_incident_templates_name_no_firm_client_or_person() -> None:
    templates = _between("## Templates", "## Portal maintenance banner wording")
    assert (
        "### SEV1" in templates
        and "### SEV2" in templates
        and "### Planned maintenance" in templates
    )
    assert not PLACEHOLDER_FOR_A_PARTY.search(templates)
    lowered = templates.lower()
    for name in ("brightwater", "hale", "felix", "hannah", "claire", "margaret"):
        assert name not in lowered


def test_the_components_are_shl_05s_in_its_order() -> None:
    table = _between("## Components", "## Templates")
    rows = re.findall(r"^\| ([^|]+?) \| ", table, flags=re.MULTILINE)
    assert tuple(r for r in rows if r not in ("Component (SHL-05 name)", "---")) == SHL_05


def test_the_status_words_are_canonical() -> None:
    assert "`Operational`" in TEXT and "`Needs attention`" in TEXT
    for invented in ("Degraded performance", "Partial outage", "Major outage", "Down"):
        assert invented not in _between("## Templates", "## Before loading them")
