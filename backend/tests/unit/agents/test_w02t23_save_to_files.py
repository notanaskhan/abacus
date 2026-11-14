"""W-02-T23 part 1 (TASK-8023; W-02 §3.9; SPEC-653 AC-W1, AC-W5, AC-Q2; DEC-5012): Save to Files
wiring. The pure parts here; the propose, approve, Undo and consume paths run against the
database in W-02-T24's independent suite (ADR-078) at the end pass."""

from __future__ import annotations

from abacus.modules.agents import file_tools as f


def test_ac_w1_the_access_sentence_names_who_can_open_the_folder() -> None:
    assert f.access_sentence("deliverables") == "The engagement team can open Deliverables."
    assert f.access_sentence("workpapers") == "The engagement team can open Workpapers."


def test_ac_w5_attach_only_is_read_from_the_answered_save_question() -> None:
    assert f.ATTACH_ONLY == "attach_only"
    sql = str(f._ATTACH_ONLY_CHOSEN)  # pyright: ignore[reportPrivateUsage]  # pins the query
    assert "state = 'answered'" in sql
    assert '"attach_only"' in sql


def test_the_save_tool_stays_a_proposal_and_the_save_an_approved_write() -> None:
    kinds = {decl.name: decl.kind for decl in f.FILE_TOOLS}
    assert kinds["files.propose_save"] == "propose"
    assert kinds[f.SAVE_TOOL] == "approved_write"


def test_c17_the_propose_reply_stays_identifiers_only() -> None:
    # The access sentence rides on the proposal's set_ref (AC-W1), never the tool's answer.
    assert set(f.ProposeSaveOut.model_fields) == {"proposal_id"}
