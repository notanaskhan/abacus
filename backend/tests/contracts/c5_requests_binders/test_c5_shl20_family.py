"""C5 v1.2, the SHL-20 family (P-06-T14 live, P-06-T15 stub, P-06-T20 live; contract §12; DEC-221,
DEC-324): every route exists with its one matrix action; the follow-ups v2 routes answer 404 with
`binders.engine` off and are live with it on; the screening routes answer 404 with `screening.card`
off; the card, its rerun and feedback are live (P-06-T20) and the screening-return draft answers
501 until P-06-T22; client-visible sends take an Idempotency-Key; the person's acts deny the
agent; the card carries C2's screening glyph and never a confidence. The change is additive: the
v1 and v1.1 routes and models the A-01 and R-01 consumer tests read are unchanged."""

from __future__ import annotations

import json
import uuid
from typing import cast

import pytest
from pydantic import ValidationError

from abacus.api.export_openapi import document
from abacus.kernel._flags import SCREENING_CARD
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.agents import screening_contract
from abacus.modules.agents.screening_contract import ScreeningFeedbackIn, ScreeningReturnDraftIn
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
ITEMS = "/v1/engagements/{engagement_id}/request-items/{item_id}"

LIVE: dict[tuple[str, str], str] = {
    ("post", "/v1/follow-ups/drafts"): "follow_up.draft",
    ("get", "/v1/follow-ups/{follow_up_id}"): "follow_up.draft",
    ("patch", "/v1/follow-ups/{follow_up_id}"): "follow_up.draft",
    ("post", "/v1/follow-ups/{follow_up_id}/send"): "follow_up.send",
    ("post", "/v1/follow-ups/send"): "follow_up.send",
    ("post", "/v1/follow-ups/{follow_up_id}/undo"): "follow_up.send",
    ("post", "/v1/follow-ups/{follow_up_id}/dismiss"): "follow_up.send",
    # P-06-T20 (DEC-324): the card, its rerun and feedback.
    ("get", f"{ITEMS}/screening"): "upload_review.read",
    ("post", f"{ITEMS}/screening/rerun"): "screening.request",
    ("post", "/v1/screenings/{screening_result_id}/feedback"): "screening.feedback",
}
STUBBED: dict[tuple[str, str], str] = {
    ("post", f"{ITEMS}/follow-ups"): "follow_up.draft",  # P-06-T22
}
IDEMPOTENT = {"/v1/follow-ups/{follow_up_id}/send", "/v1/follow-ups/send"}


@pytest.mark.parametrize(("method", "path"), sorted(LIVE | STUBBED))
def test_each_route_declares_its_one_action_and_its_answers(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == (LIVE | STUBBED)[(method, path)]
    responses = cast(Json, op["responses"])
    assert "404" in responses
    assert ("501" in responses) == ((method, path) in STUBBED)


@pytest.mark.parametrize("path", sorted(IDEMPOTENT))
def test_sends_take_an_idempotency_key(path: str) -> None:
    params = cast(list[Json], PATHS[path]["post"].get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True


@pytest.mark.parametrize("action", ["follow_up.send", "screening.feedback"])
def test_a_persons_acts_deny_the_agent(action: str) -> None:
    assert RULES[action].decisions.get("agent") == "deny"


def test_the_agent_may_still_draft_and_screening_stays_a_firm_read() -> None:
    assert RULES["follow_up.draft"].decisions.get("agent") == "task_scope"
    readers = {r for r, d in RULES["upload_review.read"].decisions.items() if d != "deny"}
    assert not readers & {"client_admin", "client_contributor", "agent"}


def test_the_card_is_the_c2_glyph_and_never_a_confidence() -> None:
    card = cast(dict[str, Json], SCHEMAS["ScreeningCardOut"]["properties"])
    assert card["verdict"].get("$ref") == "#/components/schemas/EvidenceScreeningStatus"
    card_family = (
        "ScreeningCardOut",
        "ScreeningCheckOut",
        "ScreeningFileFlagOut",
        "ScreeningProvenanceOut",
        "ScreeningFeedbackOut",
    )
    every = json.dumps({k: SCHEMAS[k] for k in card_family})
    assert "confidence" not in every  # the per-run proposals (SPEC-011) keep theirs


def test_a_follow_up_carries_its_items_each_with_due_date_and_overdue() -> None:
    item = cast(dict[str, Json], SCHEMAS["FollowUpItemOut"]["properties"])
    assert set(item) == {"request_item_id", "title", "due_on", "overdue"}
    follow_up = cast(dict[str, Json], SCHEMAS["FollowUpOut"]["properties"])
    assert {"subject", "body", "edited", "drafted_by_kind", "undo_until"} <= set(follow_up)


def test_a_thumbs_down_needs_a_reason() -> None:
    ScreeningFeedbackIn(thumb="up")
    ScreeningFeedbackIn(thumb="down", reason_code="wrong_period")
    with pytest.raises(ValidationError):
        ScreeningFeedbackIn(thumb="down")


def test_a_screening_return_names_at_least_one_file() -> None:
    ScreeningReturnDraftIn(kind="screening_return", returning=[uuid.uuid4()])
    with pytest.raises(ValidationError):
        ScreeningReturnDraftIn(kind="screening_return", returning=[])


async def test_screening_card_flag_off_is_404_and_on_is_501(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    seen: list[object] = []

    async def off(_tenant: object, flag: object) -> bool:
        seen.append(flag)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(screening_contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await screening_contract._stub(ctx)  # pyright: ignore[reportPrivateUsage] -- the gate
    assert seen == [SCREENING_CARD]
    monkeypatch.setattr(screening_contract, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await screening_contract._stub(ctx)  # pyright: ignore[reportPrivateUsage] -- the gate
