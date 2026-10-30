"""N-02-T19 (ADR-342): DocuSeal's signed webhook and the hint's two identifiers (pure)."""

from __future__ import annotations

import hashlib
import hmac
import json

from abacus.modules.signatures.status_poll import (
    REPLAY_TOLERANCE_SECONDS,
    verify_webhook,
    webhook_event,
)

KEY = b"whsec_test-key-not-a-secret"
OLD = b"whsec_previous-test-key"
NOW = 1_812_000_000.0
BODY = json.dumps(
    {
        "event_type": "form.completed",
        "timestamp": "2027-06-01T09:40:12.000Z",
        "data": {"id": 101, "ip": "203.0.113.9", "submission": {"id": 41, "status": "pending"}},
    }
).encode()


def _sign(key: bytes, body: bytes, at: float = NOW) -> str:
    stamp = str(int(at))
    return f"{stamp}.{hmac.new(key, stamp.encode() + b'.' + body, hashlib.sha256).hexdigest()}"


def test_ac_a_forged_call_is_refused_and_a_genuine_one_verifies() -> None:
    assert verify_webhook(BODY, _sign(KEY, BODY), [KEY], NOW) is True
    assert verify_webhook(BODY, _sign(b"guess", BODY), [KEY], NOW) is False
    assert verify_webhook(BODY + b" ", _sign(KEY, BODY), [KEY], NOW) is False  # body changed
    assert verify_webhook(BODY, None, [KEY], NOW) is False
    assert verify_webhook(BODY, "", [KEY], NOW) is False
    assert verify_webhook(BODY, "not-a-signature", [KEY], NOW) is False
    assert verify_webhook(BODY, _sign(KEY, BODY), [], NOW) is False
    assert verify_webhook(b"", _sign(KEY, b""), [KEY], NOW) is False


def test_a_replayed_delivery_outside_the_tolerance_is_refused() -> None:
    stale = NOW - REPLAY_TOLERANCE_SECONDS - 1
    assert verify_webhook(BODY, _sign(KEY, BODY, stale), [KEY], NOW) is False
    early = NOW + REPLAY_TOLERANCE_SECONDS + 1
    assert verify_webhook(BODY, _sign(KEY, BODY, early), [KEY], NOW) is False
    edge = NOW - REPLAY_TOLERANCE_SECONDS
    assert verify_webhook(BODY, _sign(KEY, BODY, edge), [KEY], NOW) is True


def test_a_signature_cannot_be_moved_to_another_timestamp() -> None:
    _, signature = _sign(KEY, BODY).split(".", 1)
    assert verify_webhook(BODY, f"{int(NOW) - 1}.{signature}", [KEY], NOW) is False


def test_keys_rotate_any_configured_key_may_match() -> None:
    assert verify_webhook(BODY, _sign(OLD, BODY), [KEY, OLD], NOW) is True


def test_the_hint_reads_only_the_submission_and_a_stable_event_id() -> None:
    first = webhook_event(BODY)
    assert first is not None and first.provider_envelope_id == "41"
    assert webhook_event(BODY) == first  # a retried delivery has the same event id
    other = json.loads(BODY)
    other["event_type"] = "form.viewed"
    assert webhook_event(json.dumps(other).encode()) != first


def test_submission_events_name_the_submission_itself() -> None:
    body = json.dumps(
        {"event_type": "submission.completed", "timestamp": "t", "data": {"id": 41}}
    ).encode()
    event = webhook_event(body)
    assert event is not None and event.provider_envelope_id == "41"


def test_bodies_without_the_identifiers_give_no_hint() -> None:
    assert webhook_event(b"not json") is None
    assert webhook_event(json.dumps({"data": {}}).encode()) is None
    no_submission = {"event_type": "form.completed", "timestamp": "t", "data": {"id": 1}}
    assert webhook_event(json.dumps(no_submission).encode()) is None
    template = {"event_type": "template.created", "timestamp": "t", "data": {"id": 9}}
    assert webhook_event(json.dumps(template).encode()) is None
    flagged = {"event_type": "submission.completed", "timestamp": "t", "data": {"id": True}}
    assert webhook_event(json.dumps(flagged).encode()) is None
