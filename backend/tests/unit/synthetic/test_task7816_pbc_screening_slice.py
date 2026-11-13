"""TASK-7816 (DEC-4814): the `pbc_screening` slice, Granite Peak's screened PBC upload for J04's
trace to source (P-03-T25) and pbc-ai (P-04-T45) on the Sep 24 pass.

The events, their order and their people; the document and the one recorded reviewer answer. The
load itself (the services, the reviewer's path on the fake route, code's citation check and the
aggregate) runs on the local stack with `make seed-demo`, and J04's two `@sep24` journeys read it.
"""

from __future__ import annotations

import json
from datetime import datetime

from abacus.modules.agents.handoff import UploadReviewOutput
from abacus_tools.synthetic.scenarios.brightwater_hale import pbc_screening as slice_
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import BY_LABEL, team_of
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import HANDLERS, expand_slices
from abacus_tools.synthetic.scenarios.brightwater_hale.responses import load
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events

SEP_24_SNAPSHOT = datetime(2026, 9, 24, 10, 20, tzinfo=CT)


def test_every_event_is_before_the_sep_24_snapshot_in_story_order() -> None:
    events = slice_events(slice_.SLICE)
    assert [e.kind for e in events] == [
        *(["platform.flag_set"] * len(slice_.FLAGS)),
        "requests.pbc_list_published",
        "evidence.pbc_file_uploaded",
        "agents.pbc_upload_reviewed",
    ]
    times = [e.at for e in events]
    assert times == sorted(times)
    assert all(t < SEP_24_SNAPSHOT for t in times)
    assert all(e.kind in HANDLERS for e in events)


def test_the_publisher_is_on_granite_peaks_team_and_the_list_is_its_own() -> None:
    audit = BY_LABEL["A2"]
    assert audit.client == slice_.GRANITE
    assert slice_.GRANITE_LIST.engagement == "A2"
    assert (slice_.PUBLISHER, "manager") in team_of(audit)
    assert slice_.PUBLISHED_AT < slice_.UPLOADED_AT < slice_.REVIEWED_AT


def test_the_upload_answers_the_bank_statement_request_from_luis_ferrante() -> None:
    position = slice_.request_position()
    request = slice_.GRANITE_LIST.requests[position - 1]
    assert request.title == slice_.REQUEST_TITLE
    assert request.category == "Cash"
    assert request.assignee is not None and request.assignee.name == slice_.UPLOADER
    upload = next(e for e in slice_events(slice_.SLICE) if e.kind == "evidence.pbc_file_uploaded")
    assert upload.data == {
        "list": "granite-peak",
        "position": position,
        "by": "Luis Ferrante",
        "file": slice_.FILE_NAME,
    }


def test_the_slice_needs_sampling_and_turns_the_card_viewer_and_citations_on() -> None:
    expanded = expand_slices((slice_.SLICE,))
    assert expanded.index("sampling") < expanded.index(slice_.SLICE)
    assert slice_.FLAGS == ("screening.card", "evidence.viewer_v1", "evidence.citations_v2")


def test_the_card_statement_is_deterministic_and_carries_the_quoted_lines() -> None:
    first, second = slice_.card_statement(), slice_.card_statement()
    assert first == second and first.startswith(b"%PDF")
    for quote in (b"Example Card Services", b"PAYMENTS AND OTHER CREDITS"):
        assert quote in first


def test_the_one_recorded_answer_is_an_irrelevant_flag_quoting_the_statement() -> None:
    answers = load(slice_.ANSWERS)
    assert len(answers) == 1
    prompt, sha, text = answers[0]
    assert prompt == "evidence.upload_review@v3"
    assert len(sha) == 64 and int(sha, 16) > 0
    output = UploadReviewOutput.model_validate_json(text)
    assert output.no_concerns is False
    (flag,) = output.flags
    assert flag.category == "irrelevant"
    content = slice_.card_statement()
    assert all(c.quote.encode() in content for c in flag.citations)
    raw = json.loads((slice_.ANSWERS / slice_.RESPONSE_FILE).read_text(encoding="utf-8"))
    assert raw["document"] == slice_.FILE_NAME
