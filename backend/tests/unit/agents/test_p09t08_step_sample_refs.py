"""P-09-T08 (TASK-7808): a tool step records the first five records it read (0751 `sample_refs`).

The harness writes `{record_type, id}` from the tool's declared record type and the `id` of each
row it returned, in order; a single-record read gives its own id; a tool without a declared type,
an unknown tool or a refusal writes none.
"""

from __future__ import annotations

import uuid

from abacus.modules.agents.tools.catalogue import register_all
from abacus.modules.agents.trace import SAMPLES_PER_STEP, step_sample_refs

register_all()  # the catalogue, as the worker registers it at boot (idempotent)


def _ids(n: int) -> list[str]:
    return [str(uuid.uuid4()) for _ in range(n)]


def test_ac_a_list_read_records_its_first_five_rows_in_order() -> None:
    ids = _ids(7)
    refs = step_sample_refs("requests.list_items", {"items": [{"id": i} for i in ids]})
    assert refs == [{"record_type": "request_item", "id": i} for i in ids[:SAMPLES_PER_STEP]]


def test_a_single_record_read_records_its_own_id() -> None:
    one = str(uuid.uuid4())
    assert step_sample_refs("requests.read_item", {"id": one}) == [
        {"record_type": "request_item", "id": one}
    ]


def test_duplicates_and_malformed_ids_are_skipped() -> None:
    a, b = _ids(2)
    rows = [{"id": a}, {"id": a}, {"id": "not-a-uuid"}, {"other": b}, {"id": b}]
    refs = step_sample_refs("requests.list_items", {"items": rows})
    assert [r["id"] for r in refs] == [a, b]


def test_nothing_without_a_result_a_type_or_a_known_tool() -> None:
    assert step_sample_refs("requests.list_items", None) == []
    assert step_sample_refs("no.such_tool", {"items": [{"id": _ids(1)[0]}]}) == []
