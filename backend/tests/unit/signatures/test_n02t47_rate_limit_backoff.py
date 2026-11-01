"""N-02-T47 (N-02 §5.6; ADR-079): provider rate-limit backoff and the signing surge profile.

DocuSeal's 429 becomes `ProviderRateLimited` with its Retry-After (seconds or an HTTP date,
clamped to 1..300, 30 when absent or unreadable); an activity turns it into Temporal's next retry
no sooner than that, so a deadline-day surge drains at the provider's pace. Any other refusal
stays `DocuSealError` and retries on the workflow's policy. The `signing_surge` profile parses,
names the E18 draft and holds send and the portal envelope view to p95 500 ms; `signatures` is a
mutation scope with a floor.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from temporalio.exceptions import ApplicationError

from abacus.modules.signatures import activities
from abacus.modules.signatures.docuseal import DocuSealError
from abacus.modules.signatures.provider import (
    RATE_LIMIT_DEFAULT_SECONDS,
    RATE_LIMIT_MAX_SECONDS,
    ProviderRateLimited,
    retry_after_seconds,
)
from abacus_tools.loadtest.journey_vars import journey_vars
from abacus_tools.loadtest.scenario import profile
from abacus_tools.quality.mutation import SCOPES

from . import test_n02t18_docuseal_adapter as t18

NOW = datetime(2026, 9, 15, 10, 30, tzinfo=UTC)
_honour = activities._honour_rate_limit  # pyright: ignore[reportPrivateUsage] -- the unit under test
_adapter = t18._adapter  # pyright: ignore[reportPrivateUsage] -- N-02-T18's recorded DocuSeal


@pytest.mark.parametrize(
    ("header", "seconds"),
    [
        ("12", 12.0),
        ("0", 1.0),
        ("86400", RATE_LIMIT_MAX_SECONDS),
        (None, RATE_LIMIT_DEFAULT_SECONDS),
        ("", RATE_LIMIT_DEFAULT_SECONDS),
        ("soon", RATE_LIMIT_DEFAULT_SECONDS),
        ("-5", RATE_LIMIT_DEFAULT_SECONDS),
        ("Tue, 15 Sep 2026 10:31:00 GMT", 60.0),
        ("Tue, 15 Sep 2026 10:29:00 GMT", 1.0),
    ],
)
def test_retry_after_reads_seconds_and_dates_and_stays_bounded(
    header: str | None, seconds: float
) -> None:
    assert retry_after_seconds(header, NOW) == seconds


def _answer(status: int, retry_after: str | None) -> Callable[[httpx.Request], httpx.Response]:
    def answer(_request: httpx.Request) -> httpx.Response:
        headers = {} if retry_after is None else {"Retry-After": retry_after}
        return httpx.Response(status, headers=headers, json={})

    return answer


@pytest.mark.asyncio
async def test_a_429_is_rate_limited_with_its_wait_and_other_refusals_are_not() -> None:
    with pytest.raises(ProviderRateLimited) as caught:
        await _adapter(_answer(429, "7")).status("41")
    assert caught.value.retry_after == 7.0
    with pytest.raises(DocuSealError) as other:
        await _adapter(_answer(503, "7")).status("41")
    assert other.value.status == 503


def test_the_activity_retries_no_sooner_than_the_providers_wait() -> None:
    with pytest.raises(ApplicationError) as caught, _honour():
        raise ProviderRateLimited(45.0)
    assert caught.value.next_retry_delay == timedelta(seconds=45)
    assert caught.value.type == "ProviderRateLimited"
    assert not caught.value.non_retryable


def test_other_failures_pass_through_untouched() -> None:
    with pytest.raises(DocuSealError), _honour():
        raise DocuSealError("get", 500)


def test_the_signing_surge_profile_holds_send_and_the_portal_view_to_500_ms() -> None:
    surge = profile("signing_surge")
    assert surge.duration_seconds == 3600
    groups = {g.name: g for g in surge.groups}
    send = groups["envelope_send"]
    assert send.p95_ms == 500
    assert send.steps[0].method == "POST"
    assert send.steps[0].idempotency
    assert send.steps[0].path == "/v1/envelopes/{e18_envelope_id}/send"
    assert groups["portal_envelopes"].p95_ms == 500
    assert "e18_envelope_id" in journey_vars()


def test_signatures_is_a_mutation_scope() -> None:
    assert SCOPES["signatures"] == ("src/abacus/modules/signatures/*.py",)
