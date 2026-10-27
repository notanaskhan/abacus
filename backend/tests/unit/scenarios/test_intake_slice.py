"""P-07-T50 (TASK-1444; DEC-593): scenario content wave 3 without a database: the
`thornbury_estate` holdout, the `intake` slice's events, and the synthetic CCH client list, whose
212 rows score 204 matched, 8 to review and 0 new under DEC-441's rule (pg_trgm's similarity,
modelled here; the load test scores them in Postgres)."""

from __future__ import annotations

import csv
import io
import re

from abacus.modules.organisations.intake import DEDUPE_FLOOR, core_name, score_names
from abacus.modules.organisations.service import normalise
from abacus_tools.synthetic.scenarios.brightwater_hale import client_list
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SCENARIO_HASH, build


def _trigrams(text: str) -> set[str]:
    """pg_trgm's: each alphanumeric word, lower case, padded with two spaces before, one after."""
    out: set[str] = set()
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        padded = f"  {word} "
        out |= {padded[i : i + 3] for i in range(len(padded) - 2)}
    return out


def _similarity(a: str, b: str) -> float:
    left, right = _trigrams(a), _trigrams(b)
    return len(left & right) / len(left | right) if left | right else 0.0


def _names_at_cli06() -> dict[str, str]:
    """Every client and entity name (normalised) at the CLI-06 snapshot, to its client."""
    scenario = build("E0", ("thornbury_estate",))
    out: dict[str, str] = {}
    for c in scenario.clients:
        for name in (c.name, *c.entities):
            out[normalise(name)] = c.name
    return out


def _best(row: str, names: dict[str, str]) -> tuple[float, str] | None:
    typed = normalise(row)
    core, _ = core_name(typed)
    scored: list[tuple[float, str]] = []
    for stored, client in names.items():
        if stored in (typed, core) or _similarity(typed, stored) >= DEDUPE_FLOOR:
            score = score_names(typed, stored, round(_similarity(typed, stored), 4))
            if score is not None:
                scored.append((score, client))
    return max(scored) if scored else None


def test_the_holdout_keeps_walter_thornbury_without_his_estate() -> None:
    assert build().fingerprint() == SCENARIO_HASH  # the default scenario is unchanged
    held = build("E0", ("thornbury_estate",))
    walter = next(c for c in held.clients if "Thornbury" in c.name)
    assert (walter.name, walter.entities, walter.kind) == (
        "Walter Thornbury",
        ("Walter Thornbury",),
        "individual",
    )
    assert len(held.clients) == 184
    assert not [e for e in held.events if e.client == "Estate of Walter Thornbury"]
    assert [e.label for e in held.events if e.client == "Walter Thornbury"] == [
        "client:walter-thornbury"
    ]


def test_the_intake_slice_loads_the_hit_only_with_the_holdout() -> None:
    slices = ("audit_core", "people", "acceptance", "intake")
    labels = {e.label for e in build("2026-09-24", slices=slices).events}
    assert {"draft:granite-peak", "draft:fairhaven", "acceptance-sent:meridian"} <= labels
    assert "conflict-check:walter-thornbury:harborline" not in labels
    held = build("2026-09-24", ("thornbury_estate",), slices)
    held_labels = {e.label for e in held.events}
    assert "conflict-check:walter-thornbury:harborline" in held_labels
    assert "draft:thornbury" not in held_labels  # the estate is not yet a client
    no_fairhaven = build("2026-09-24", ("fairhaven_ebp",), slices)
    assert "draft:fairhaven" not in {e.label for e in no_fairhaven.events}


def test_the_committed_file_is_the_generator_output() -> None:
    assert client_list.FILE.read_bytes().decode("utf-8") == client_list.cch_client_list()


def test_the_file_has_212_rows_in_the_cch_headings_and_no_identifiers() -> None:
    text = client_list.FILE.read_text("utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    assert tuple(rows[0]) == client_list.HEADINGS
    assert len(rows) - 1 == client_list.ROWS == 212
    assert len({r[0] for r in rows[1:]}) == 212  # client ids are unique
    assert not re.search(r"\d{3}-?\d{2}-?\d{4}|\d{2}-\d{7}", text)  # no TIN-shaped digits


def test_the_rows_score_204_matched_8_to_review_and_0_new() -> None:
    names = _names_at_cli06()
    matched = review = new = 0
    for row in client_list.rows():
        best = _best(row.name, names)
        if best is None:
            new += 1
            continue
        score, client = best
        assert client == row.expected, row.name
        if score >= client_list.MATCH_AT:
            assert not row.review, row.name
            matched += 1
        else:
            assert row.review, row.name
            review += 1
    assert (matched, review, new) == (204, 8, 0)
    rows = client_list.rows()
    assert rows[6].review and rows[7].review  # CLI-06 g skips rows 7 and 8
