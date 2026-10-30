"""N-02-T19: DocuSign Connect's HMAC and the hint's two identifiers (pure)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

from abacus.modules.signatures.status_poll import connect_event, verify_connect

KEY = b"connect-key-1"
OLD = b"connect-key-0"
BODY = json.dumps(
    {
        "event": "recipient-completed",
        "generatedDateTime": "2027-06-01T09:40:12.000Z",
        "data": {"envelopeId": "env-1", "recipientId": "1", "envelopeSummary": {"x": "y"}},
    }
).encode()


def _sign(key: bytes, body: bytes) -> str:
    return base64.b64encode(hmac.new(key, body, hashlib.sha256).digest()).decode()


def test_a_forged_call_is_refused_and_a_genuine_one_verifies() -> None:
    assert verify_connect(BODY, [_sign(KEY, BODY)], [KEY]) is True
    assert verify_connect(BODY, [_sign(b"guess", BODY)], [KEY]) is False
    assert verify_connect(BODY + b" ", [_sign(KEY, BODY)], [KEY]) is False  # body changed
    assert verify_connect(BODY, [], [KEY]) is False
    assert verify_connect(BODY, [_sign(KEY, BODY)], []) is False


def test_keys_rotate_any_configured_key_may_match() -> None:
    assert verify_connect(BODY, ["junk", _sign(OLD, BODY)], [KEY, OLD]) is True


def test_the_hint_reads_only_the_envelope_and_a_stable_event_id() -> None:
    first = connect_event(BODY)
    assert first is not None and first.provider_envelope_id == "env-1"
    assert connect_event(BODY) == first  # a replayed delivery has the same event id
    other = json.loads(BODY)
    other["event"] = "envelope-completed"
    assert connect_event(json.dumps(other).encode()) != first
    assert connect_event(b"not json") is None
    assert connect_event(json.dumps({"data": {}}).encode()) is None
