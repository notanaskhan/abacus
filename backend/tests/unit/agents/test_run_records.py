"""Q-02-T41 (TASK-1287; ADR-169 §3): a run record is content-free by construction and its
`record_sha256` is the canonical hash of its fields. Pure functions, no database."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.ai_gateway import ModelCall, prompt
from abacus.kernel.errors import ServiceUnavailable
from abacus.modules.agents import run_records
from abacus.modules.agents.models import AgentRun
from abacus.modules.agents.repository import RunCitationRow, RunOutputRows, RunWriteRow
from abacus.modules.agents.run_records import (
    FIELDS,
    build_record,
    fingerprint,
    fingerprinting_configured,
    record_sha256,
    record_state,
    scrub_citation,
)

TENANT = uuid.UUID(int=2)
START = datetime(2027, 1, 4, 15, 0, tzinfo=UTC)
VERSION = uuid.UUID(int=7)
PROMPT = "evidence.screen@v0"


def _run(**changes: object) -> AgentRun:
    values: dict[str, object] = {
        "id": uuid.UUID(int=1),
        "tenant_id": uuid.UUID(int=2),
        "agent_id": "evidence.screener",
        "spec_version": 1,
        "engagement_id": uuid.UUID(int=3),
        "methodology_version_id": None,
        "evidence_version_id": VERSION,
        "inbox_file_id": None,
        "shadow": False,
        "initiator_user_id": uuid.UUID(int=4),
        "source_event_id": None,
        "task_scope": ["evidence.read", "screening.run"],
        "status": "completed",
        "context_hash": "c" * 64,
        "output": {"rationale": "model words never kept"},
        "failure_code": None,
        "queued_reason": None,
        "estimated_start_at": None,
        "started_at": START,
        "finished_at": START + timedelta(seconds=9),
    }
    values.update(changes)
    return AgentRun(**values)


def _call(outcome: str = "ok", inputs: str = "a" * 64) -> ModelCall:
    return ModelCall(START, outcome, PROMPT, "fake-small", "fake", "local", inputs, None, None)


CITED = RunCitationRow(
    "screening_result",
    "evidence_version",
    VERSION,
    {
        "cell": "B12",
        "quote": "Cash at Harbor Bank",
        "value": "1234.56",
        "sheet": "Client sheet name",
        "verified": True,
        "reason": None,
    },
)
OUTPUTS = RunOutputRows({"screening_result": 1}, [("evidence_version", VERSION)], [CITED])


def test_ac44_a_citation_keeps_its_locator_and_fingerprints_never_the_words() -> None:
    scrubbed = scrub_citation(TENANT, CITED)
    assert scrubbed == {
        "source": "screening_result",
        "record": {"type": "evidence_version", "id": str(VERSION)},
        "locator": {"cell": "B12"},
        "quote_fingerprint": fingerprint(TENANT, "Cash at Harbor Bank"),
        "sheet_fingerprint": fingerprint(TENANT, "Client sheet name"),
        "verified": True,
        "reason": None,
    }
    text = json.dumps(scrubbed)
    for words in ("Cash at Harbor Bank", "1234.56", "Client sheet name"):
        assert words not in text


def test_ac44_a_fingerprint_is_keyed_per_firm_never_a_plain_hash() -> None:
    """Security review (DEC-396): a short quoted value (a 9xx TIN) can't be found by hashing
    guesses, and two firms' fingerprints of the same words differ."""
    words = "912-34-5678"
    mine, theirs = fingerprint(TENANT, words), fingerprint(uuid.UUID(int=99), words)
    assert mine != hashlib.sha256(words.encode()).hexdigest()
    assert mine != theirs
    assert mine == fingerprint(TENANT, words) and len(mine) == 64


def test_ac44_no_record_is_persisted_without_the_fingerprint_pepper_outside_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hosted = SimpleNamespace(environment="staging", run_record_fingerprint_pepper=None)
    monkeypatch.setattr(run_records, "settings", lambda: hosted)
    assert not fingerprinting_configured()
    with pytest.raises(ServiceUnavailable):
        fingerprint(TENANT, "words")


def test_ac44_a_locator_value_that_is_not_a_short_code_is_dropped() -> None:
    long = RunCitationRow("x", "evidence_version", None, {"cell": "Z" * 200, "page": 3})
    assert scrub_citation(TENANT, long)["locator"] == {"cell": None, "page": 3}


@pytest.mark.parametrize(
    ("status", "code", "state"),
    [
        ("completed", None, "succeeded"),
        ("escalated", None, "needs_input"),
        ("failed", "provider_unavailable", "failed"),
        ("failed", "cancelled", "cancelled"),
    ],
)
def test_ac44_the_outcome_follows_the_legacy_map(
    status: str, code: str | None, state: str
) -> None:
    assert record_state(_run(status=status, failure_code=code)) == state


def test_ac44_the_record_holds_the_decisive_call_and_every_input_hash() -> None:
    calls = [_call("invalid", "b" * 64), _call("repaired", "a" * 64), _call("provider_error")]
    fields = build_record(_run(), calls, OUTPUTS, [])
    assert fields["prompt_ref"] == PROMPT
    assert fields["prompt_sha256"] == prompt(PROMPT).sha256
    assert (fields["model"], fields["route"], fields["region"]) == ("fake-small", "fake", "local")
    assert fields["input_hashes"] == {"context": "c" * 64, "model_calls": ["a" * 64, "b" * 64]}
    assert fields["records_read"] == [{"type": "evidence_version", "id": str(VERSION)}]
    assert fields["outcome"] == {
        "state": "succeeded",
        "failure_code": None,
        "outputs": {"screening_result": 1},
    }
    assert "model words never kept" not in json.dumps(fields, default=str)


def test_ac44_a_run_that_called_no_model_has_no_model_facts() -> None:
    fields = build_record(_run(status="failed", failure_code="capacity_timeout"), [], OUTPUTS, [])
    assert all(
        fields[k] is None
        for k in ("prompt_ref", "prompt_sha256", "model", "route", "region", "boundary_basis")
    )
    assert fields["input_hashes"] == {"context": "c" * 64, "model_calls": []}


def test_ac44_written_suggestions_and_proposals_count_as_outputs() -> None:
    write = RunWriteRow("proposal", uuid.uuid4(), None, None, "k", "open", START, None, None, None)
    fields = build_record(_run(), [_call()], OUTPUTS, [write, write])
    outcome = cast("dict[str, object]", fields["outcome"])
    assert outcome["outputs"] == {"proposal": 2, "screening_result": 1}


def test_ac44_the_hash_is_canonical_and_covers_every_field() -> None:
    fields = build_record(_run(), [_call()], OUTPUTS, [])
    digest = fields["record_sha256"]
    assert digest == record_sha256(fields)
    assert set(FIELDS) | {"record_sha256"} == set(fields)
    reordered = dict(reversed(list(fields.items())))
    assert record_sha256(reordered) == digest
    for name in FIELDS:
        changed = dict(fields)
        changed[name] = "changed"
        assert record_sha256(changed) != digest, name


def test_ac44_a_record_is_built_only_once_the_run_has_ended() -> None:
    with pytest.raises(ValueError, match="ended"):
        build_record(_run(status="running", finished_at=None), [], OUTPUTS, [])
