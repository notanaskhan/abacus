"""Security review (S8 wave B, LOW 8): `abacus_tools.schedules ensure` deletes the Schedules it
owns that are no longer declared (a canary for a firm that is no longer the canary keeps running
otherwise), never one it does not own; and `make schedules` refuses a Temporal that is not on the
local stack."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from abacus.kernel.config import settings
from abacus.kernel.dispatch import PlatformSchedule
from abacus_tools import schedules

OLD_CANARY = "canary:00000000-0000-4000-8000-0000000000aa"


@pytest.fixture
def temporal(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, list[str]]]:
    seen: dict[str, list[str]] = {"ensured": [], "deleted": []}
    existing = [
        "spend_anomaly:platform",
        "notification_purge:platform",
        "ses_events:platform",
        OLD_CANARY,  # declared no more
        "retired_job:platform",  # a platform job removed from the code
        "someone-elses-schedule",  # not ours: never touched
    ]

    async def schedule(job: PlatformSchedule) -> str:
        seen["ensured"].append(job.id)
        return "updated"

    async def schedule_ids() -> list[str]:
        return list(existing)

    async def delete(schedule_id: str) -> None:
        seen["deleted"].append(schedule_id)

    monkeypatch.setattr(schedules.dispatch, "schedule", schedule)
    monkeypatch.setattr(schedules.dispatch, "schedule_ids", schedule_ids)
    monkeypatch.setattr(schedules.dispatch, "delete", delete)
    yield seen


async def test_ensure_deletes_the_undeclared_schedules_it_owns_only(
    temporal: dict[str, list[str]],
) -> None:
    result = await schedules.ensure()
    assert sorted(temporal["deleted"]) == [OLD_CANARY, "retired_job:platform"]
    assert result[OLD_CANARY] == "deleted"
    assert "someone-elses-schedule" not in result
    assert set(temporal["ensured"]) == {j.id for j in schedules.declared()}


@pytest.mark.parametrize(
    ("schedule_id", "owned"),
    [
        ("spend_anomaly:platform", True),
        (OLD_CANARY, True),
        ("canary:not-a-uuid", False),
        ("platform", False),
        ("x:platform:extra", False),
        ("nightly-report", False),
    ],
)
def test_ownership_is_by_id_shape(schedule_id: str, owned: bool) -> None:
    assert schedules.owned(schedule_id) is owned


@pytest.fixture
def target(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    yield monkeypatch
    settings.cache_clear()


@pytest.mark.parametrize(
    "host", ["127.0.0.1:7233", "localhost:7233", "temporal:7233", "[::1]:7233"]
)
def test_the_local_guard_accepts_the_local_stack(target: pytest.MonkeyPatch, host: str) -> None:
    target.setenv("ABACUS_TEMPORAL_TARGET", host)
    settings.cache_clear()
    schedules.check_local()


@pytest.mark.parametrize(
    "host", ["acct.a1b2c.tmprl.cloud:7233", "us-east-2.aws.api.temporal.io:7233", "10.0.0.5:7233"]
)
def test_the_local_guard_refuses_a_hosted_temporal(target: pytest.MonkeyPatch, host: str) -> None:
    target.setenv("ABACUS_TEMPORAL_TARGET", host)
    settings.cache_clear()
    with pytest.raises(schedules.Refused):
        schedules.check_local()
    assert schedules.main(["ensure", "--local-only"]) == 2
