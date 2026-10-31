"""K-02-T18 (TASK-2424; K-02 §3, US-3.5, US-5.1; KNW-04; DEC-1472): the `standards` slice.

The row's acceptance holds its footings as seed tests: the six TY2025 checklists cover 162 + 38 +
12 + 5 + 6 + 1 = 224 returns with the handoff's check counts, and Copperleaf's August example
foots to 20,020 within threshold with 14,900 held. Also: every version in the slice is a valid
payload for its kind and survives the import format (the export's workbook read back is the same
payload), each publish is a real change, and the timeline creates, imports and publishes in
order through the owners the handoff names.
"""

from __future__ import annotations

from typing import cast

from abacus.modules.methodology.standards import validate_payload
from abacus.modules.methodology.standards_import import export_workbook, read_payload
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events
from abacus_tools.synthetic.scenarios.brightwater_hale.standards import (
    AUGUST_EXAMPLES,
    AUGUST_HELD,
    STANDARDS,
    payload_of,
    spec_of,
)

CHECKLISTS = {
    "1040": (6, 38, 162),
    "1065": (4, 42, 38),
    "1120-S": (3, 36, 12),
    "1120": (2, 33, 5),
    "1041": (2, 31, 6),
    "990": (1, 29, 1),
}


def test_ac1_the_checklists_foot_to_224_returns_with_the_handoffs_counts() -> None:
    usage = 0
    for form, (version, checks, returns) in CHECKLISTS.items():
        spec = spec_of(f"bh-{form.lower()}-review-checklist")
        assert len(spec.versions) == version
        current = spec.versions[-1]
        items = current["items"]
        assert isinstance(items, list) and len(cast(list[object], items)) == checks
        assert spec.usage == returns
        usage += returns
    assert usage == 224
    draft = spec_of("bh-1040-review-checklist").draft
    assert draft is not None and draft["applies_to"] == {"form": "1040", "tax_year": 2026}


def test_ac1_the_august_example_foots_to_20020_with_14900_held() -> None:
    assert sum(amount for amount, _ in AUGUST_EXAMPLES) == 20_020
    assert all(state == "within" for _, state in AUGUST_EXAMPLES)
    assert AUGUST_HELD == 14_900


def test_every_version_is_valid_and_survives_the_import_format() -> None:
    for spec in STANDARDS:
        if spec.key == "bh-tax-02":
            continue  # its clients and signer are ids the loader resolves
        numbers = range(1, len(spec.versions) + 1 + (spec.draft is not None))
        seen: list[dict[str, object]] = []
        for n in numbers:
            payload = validate_payload(spec.kind, payload_of(spec, n))
            read = read_payload(
                spec.kind, export_workbook(spec.kind, spec.name, payload), csv_file=False
            )
            assert validate_payload(spec.kind, read) == payload, (spec.key, n)
            assert payload not in seen, (spec.key, n)  # each version changes something
            seen.append(payload)


def test_the_timeline_creates_imports_and_publishes_through_the_owners() -> None:
    events = slice_events("standards")
    owners = {s.key: s.owner for s in STANDARDS}
    created = [e for e in events if e.kind == "standards.created"]
    assert {e.data["key"] for e in created} == set(owners)
    assert all(e.actor == "MO" for e in created)
    for e in events:
        if e.kind == "standards.version_published":
            assert e.actor == owners[str(e.data["key"])]
    published = [e for e in events if e.kind == "standards.version_published"]
    assert len(published) == sum(len(s.versions) for s in STANDARDS)
    for key in owners:
        mine = [e for e in events if e.data.get("key") == key and e.kind != "standards.created"]
        assert [e.at for e in mine] == sorted(e.at for e in mine)
    assert {s.owner for s in STANDARDS} == {"DR", "PR", "MO"}
