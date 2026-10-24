"""Q-02-T32 review fix (ADR-167 §2, SPEC-030 AC-5): a data-boundary refusal, `pii_in_context`
included, ends an agent's run and is never retried. Every agent activity raises it to Temporal as
non-retryable, and every agent's terminal map fails the run with `data_boundary` first."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from abacus.ai_gateway import DataBoundaryRefused
from abacus.modules.agents import activities, service, upload_review
from abacus.modules.agents.workflow_types import (
    EntryAssessRunInput,
    GuidanceDraftRunInput,
    MatchRunInput,
    RunInput,
)

TENANT = "00000000-0000-0000-0000-000000000001"
RUN = "00000000-0000-0000-0000-000000000002"
ITEM = "00000000-0000-0000-0000-000000000003"

Activity = Callable[..., Coroutine[Any, Any, object]]  # Any: each activity's own input type
# (activity, its input, the inner function it awaits)
CASES: list[tuple[Activity, object, str]] = [
    (activities.screen_activity, RunInput(TENANT, RUN), "_screen"),
    (activities.review_activity, RunInput(TENANT, RUN), "_review"),
    (activities.match_activity, MatchRunInput(TENANT, RUN, ITEM), "_match"),
    (activities.draft_activity, GuidanceDraftRunInput(TENANT, RUN, ITEM), "_draft"),
    (activities.assess_activity, EntryAssessRunInput(TENANT, RUN, ITEM), "_assess"),
]


@pytest.mark.parametrize(("run", "payload", "inner"), CASES, ids=[c[2] for c in CASES])
async def test_a_pii_in_context_refusal_is_non_retryable_for_every_agent(
    monkeypatch: pytest.MonkeyPatch,
    run: Activity,
    payload: object,
    inner: str,
) -> None:
    async def refused(*_: object) -> object:
        raise DataBoundaryRefused("refused", "pii_in_context")

    monkeypatch.setattr(activities, inner, refused)
    with pytest.raises(ApplicationError) as raised:
        await ActivityEnvironment().run(run, payload)
    assert raised.value.non_retryable
    assert raised.value.type == "DataBoundaryRefused"


@pytest.mark.parametrize("terminal", [service.TERMINAL, upload_review.TERMINAL])
def test_every_terminal_map_fails_the_run_with_data_boundary(
    terminal: dict[type[Exception], str],
) -> None:
    assert terminal[DataBoundaryRefused] == "data_boundary"
