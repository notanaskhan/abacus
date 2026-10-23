"""F-04-T09 (F-04.13, DF-35, lint L10): kit sample data and variant spellings of the canonical
names fail the build in the fixtures, the journey specs and the scenario; the canonical names and
the short forms used in running text pass."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import seed_contamination as sc


@pytest.mark.parametrize(
    "text",
    [
        # F-04.13, kit sample data
        "Elena Ruiz",
        "owner: 'Ridgeview Partners'",
        "the Whitcombes' Schedule E",
        "brightwater-hale@inbox.accrued.app",
        "PBC 17% (4 / 24)",
        "86 of the 119 returns for period 2025",
        "21 integrations",
        "offices: Chicago, Denver, Austin",
        "126 engagements",
        "the 13-task close run",
        # F-04.13 and gaps.md §4, variant spellings of the canonical constants
        "Claire & Jonah Feld",
        "Jonah and Claire Feld",
        "Ridgeline Property Partners LP",
        "Ridgeline Property Partners, L.P.",
        "Harborview Dental Properties LP",
        "Copperleaf Coffee Roasters Inc.",
        "Copperleaf Coffee Roasters, Inc",
        "Granite Peak Outdoor Supply Inc",
    ],
)
def test_t09_contamination_is_found(text: str) -> None:
    assert list(sc.findings_in(text)), text


@pytest.mark.parametrize(
    "text",
    [
        "Jonah & Claire Feld",
        "Ridgeline Property Partners, LP",
        "Schedule K-1 from Ridgeline Property Partners, LP.",  # the sentence's own full stop
        "Harborview Dental Properties, LP",
        "Copperleaf Coffee Roasters, Inc.",
        "Granite Peak Outdoor Supply, Inc.",
        "Granite Peak's FS PBC",  # short forms in running text are canonical (gaps.md §4)
        "Copperleaf August close 43% (9/21)",
        "Thomas Whitcombe",  # the EQR partner (blueprint §9.2)
        "Northwind PBC 11 of 24",
        "53 integrations",
        "224 TY2025 returns",
        "27 audits and assurance engagements",
    ],
)
def test_t09_canonical_text_passes(text: str) -> None:
    assert not list(sc.findings_in(text)), text


def test_t09_a_finding_names_the_file_line_and_the_fix(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "clients.ts").write_text('export const A = "ok";\nexport const B = "Elena Ruiz";\n')
    (seed / "clients.test.ts").write_text('expect(rows).not.toContain("Elena Ruiz");\n')
    [finding] = sc.scan([seed])
    assert finding.path.endswith("clients.ts")
    assert finding.line == 2
    assert "Elena Ruiz" in finding.message and "use" in finding.message


def test_t09_the_lint_covers_the_scenario_the_fixtures_and_the_journeys() -> None:
    roots = {p.relative_to(sc.REPO).as_posix() for p in sc.ROOTS}
    assert roots == {
        "backend/src/abacus_tools/synthetic/scenarios",
        "apps/web/src/fixtures",
        "apps/web/e2e/journeys",
    }
    scanned = {p.relative_to(sc.REPO).as_posix() for p in sc.files()}
    assert "backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/people.py" in scanned
    assert "apps/web/src/fixtures/seed/clients.ts" in scanned


def test_t09_the_repository_is_clean() -> None:
    assert [str(f) for f in sc.scan()] == []
