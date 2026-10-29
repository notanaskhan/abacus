"""N-01-T11 (TASK-1746; N-01 §5.3; DEC-47, DF-33; DEC-836): the `firm_inbox` scenario slice.

"make seed-demo and fixture mode show identical inbox and Files data and every footing test
passes" (the task row). Here: the footing (2+1+3+3+2+2+2+2+1+1+4 = 23 waiting; rows 9, 13, 16, 17
unmatched; 21 after Feld's two are applied; 214,600 + 168,300 + 129,500 = 512,400 on 5500; 12
documents with 3 + 4 = 7 virtual; Permanent file 6, Workpapers 3, Correspondence 4, Deliverables
5, Signed authorizations 0; Iyer's box 1b 3,310.00 within box 1a 5,120.00); the export the web
suite reads is the slice's own (no drift); the slice's events (the Intake team with Grace, one
`inbound_email_recorded` per message, replies chained to the message before, acts before setup
replayed after it with their canon time kept) and the loader's handlers for them; every matched
thread names a scenario client; no kit mailbox. The load itself is
`tests/integration/test_n01t11_firm_inbox_load.py`.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import cast

from abacus_tools.synthetic.scenarios.brightwater_hale import firm_inbox as fi
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.clients import build_clients
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import registered, slice_events


def test_ac_23_waiting_from_the_rows() -> None:
    per_row = [t.waiting for t in fi.threads()]
    assert per_row == [2, 1, 3, 3, 2, 2, 2, 2, 0, 1, 1, 4, 0, 0, 0, 0, 0]
    assert fi.waiting_total() == 23 == sum(per_row)


def test_ac_4_unmatched_rows_and_21_after_feld_is_applied() -> None:
    assert fi.unmatched_rows() == [9, 13, 16, 17]
    assert all(t.waiting == 0 for t in fi.threads() if t.client is None)
    inbox = cast(dict[str, object], fi.summary()["inbox"])
    assert inbox["waiting_after_feld_applied"] == 21
    assert fi.threads()[0].key == "feld"
    assert fi.threads()[0].waiting == fi.APPLIED_ON_FELD


def test_ac_the_files_figures_foot() -> None:
    assert sum(fi.MORTGAGE_STATEMENTS, Decimal(0)) == Decimal("512400")
    assert fi.MORTGAGE_ACCOUNT == "5500"
    assert sum(fi.RIDGELINE_VIRTUAL) == 7
    assert fi.RIDGELINE_SOURCE_DOCUMENTS == 12
    assert fi.RIDGELINE_FOLDERS == {
        "permanent_file": 6,
        "workpapers": 3,
        "correspondence": 4,
        "deliverables": 5,
        "signed_authorizations": 0,
    }
    assert fi.IYER_DIV_1B <= fi.IYER_DIV_1A


def test_ac_the_export_the_web_suite_reads_is_the_slices_own() -> None:
    on_disk = json.loads(fi.EXPORT.read_text("utf-8"))
    assert on_disk == json.loads(json.dumps(fi.summary()))


def test_the_slice_is_registered_and_its_events_go_through_the_intake_service() -> None:
    assert fi.SLICE in registered()
    assert loader.expand_slices((fi.SLICE,)) == (fi.SLICE,)
    events = slice_events(fi.SLICE)
    kinds = [e.kind for e in events]
    assert kinds[0] == "organisations.intake_team_created"
    assert events[0].data == {"name": "Intake", "members": ["GH"]}
    assert kinds.count("communications.inbound_email_recorded") == 18  # 17 rows, Feld has two
    for kind in set(kinds):
        assert kind in loader.HANDLERS, kind
    assert len({e.label for e in events}) == len(events)


def test_a_reply_names_the_message_before_it_in_its_thread() -> None:
    feld = [e for e in slice_events(fi.SLICE) if e.data.get("thread") == "feld"]
    assert [e.label for e in feld] == ["inbound:feld:feld-b", "inbound:feld:feld-a"]
    assert feld[0].data["in_reply_to"] is None
    assert feld[1].data["in_reply_to"] == feld[0].data["internet_message_id"]


def test_acts_before_setup_are_replayed_after_it_with_their_canon_time_kept() -> None:
    for event in slice_events(fi.SLICE):
        assert event.at >= SETUP_AT
        if "received_at" in event.data:
            received = datetime.fromisoformat(str(event.data["received_at"]))
            assert event.at == max(received, fi.REPLAY_FROM)
    first = next(e for e in slice_events(fi.SLICE) if e.label == "inbound:feld:feld-b")
    assert str(first.data["received_at"]).startswith("2026-08-03T09:24:00")


def test_every_matched_thread_names_a_scenario_client() -> None:
    names = {c.name for c in build_clients()}
    matched = {t.client for t in fi.threads() if t.client is not None}
    assert matched <= names, matched - names
    for event in slice_events(fi.SLICE):
        assert event.client == event.data.get("client")


def test_filed_files_wait_for_a_filing_service_and_the_ignored_one_is_set() -> None:
    states = [
        cast(dict[str, str], a)["state"]
        for e in slice_events(fi.SLICE)
        for a in cast(list[object], e.data.get("attachments", []))
    ]
    assert states.count("filed") == 3  # Feld's W-2 and 1098 of Aug 3, Whitley's Q3 estimates
    assert states.count("ignored") == 1  # Varga's duplicate donation receipt


def test_no_kit_mailbox_or_real_document_is_seeded() -> None:
    raw = fi.DATA.read_text("utf-8")
    assert "inbox.accrued.app" not in raw  # DEC-47: never the kit's mailbox
    content = loader._synthetic_file("Feld_1095C_2025.pdf")  # pyright: ignore[reportPrivateUsage]  # the handler's own bytes
    assert content.startswith(b"%PDF-1.4\n% Brightwater Hale scenario file: ")
