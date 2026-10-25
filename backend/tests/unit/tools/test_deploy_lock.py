"""Q-01-T18 (platform-ops contract 3.4): the deploy lock over a fake SSM. One holder at a time;
the same run taking it again is fine; a second run waits, then reports the holder; only the
holder releases; `show` reports free, held or stale and never changes anything."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from abacus_tools import deploy_lock
from abacus_tools.deploy_lock import Lock, describe, parameter_name, release, take


class FakeSsm:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.writes = 0

    def create(self, name: str, value: str) -> bool:
        self.writes += 1
        if name in self.values:
            return False
        self.values[name] = value
        return True

    def read(self, name: str) -> str | None:
        return self.values.get(name)

    def delete(self, name: str) -> None:
        self.writes += 1
        self.values.pop(name, None)


def _take(ssm: FakeSsm, run: str, **extra: float) -> tuple[bool, Lock | None]:
    return take(
        ssm,
        "staging",
        holder="deploy-staging",
        run_ref=run,
        git_sha="a" * 40,
        purpose="deploy",
        sleep=lambda _: None,
        **extra,  # type: ignore[arg-type]  # wait_seconds only
    )


def test_one_parameter_per_environment() -> None:
    assert parameter_name("staging") == "/abacus/staging/deploy-lock"
    assert parameter_name("production") == "/abacus/production/deploy-lock"
    with pytest.raises(ValueError):
        parameter_name("dev")


def test_the_first_run_takes_it_and_records_the_contract_fields() -> None:
    ssm = FakeSsm()
    taken, lock = _take(ssm, "run-1")
    assert taken and lock is not None
    stored = json.loads(ssm.values["/abacus/staging/deploy-lock"])
    assert set(stored) == {"holder", "run_ref", "git_sha", "taken_at", "purpose"}
    assert (stored["run_ref"], stored["purpose"]) == ("run-1", "deploy")


def test_a_second_run_is_refused_while_it_is_held() -> None:
    ssm = FakeSsm()
    _take(ssm, "run-1")
    taken, holder = _take(ssm, "run-2")
    assert not taken and holder is not None and holder.run_ref == "run-1"
    assert json.loads(ssm.values["/abacus/staging/deploy-lock"])["run_ref"] == "run-1"


def test_the_same_run_taking_it_again_is_a_no_op() -> None:
    ssm = FakeSsm()
    _take(ssm, "run-1")
    assert _take(ssm, "run-1")[0]


def test_a_waiting_run_takes_it_once_the_holder_releases() -> None:
    ssm = FakeSsm()
    _take(ssm, "run-1")
    released = {"n": 0}

    def sleep(_: float) -> None:
        released["n"] += 1
        release(ssm, "staging", run_ref="run-1")

    taken, lock = take(
        ssm,
        "staging",
        holder="deploy-staging",
        run_ref="run-2",
        git_sha="b" * 40,
        purpose="deploy",
        wait_seconds=60,
        sleep=sleep,
    )
    assert taken and lock is not None and lock.run_ref == "run-2"
    assert released["n"] == 1


def test_only_the_holder_releases() -> None:
    ssm = FakeSsm()
    _take(ssm, "run-1")
    assert release(ssm, "staging", run_ref="run-2") is False
    assert "/abacus/staging/deploy-lock" in ssm.values
    assert release(ssm, "staging", run_ref="run-1") is True
    assert ssm.values == {}
    assert release(ssm, "staging", run_ref="run-1") is True  # already free


def test_show_is_read_only_and_names_a_stale_lock() -> None:
    ssm = FakeSsm()
    now = datetime(2026, 11, 13, 17, 0, tzinfo=UTC)
    assert describe(None, now) == "free"
    old = Lock(
        "deploy-staging", "run-1", "a" * 40, (now - timedelta(hours=2)).isoformat(), "deploy"
    )
    ssm.values["/abacus/staging/deploy-lock"] = json.dumps(old.__dict__)
    before = ssm.writes
    assert deploy_lock.main(["show", "--env", "staging"], params=ssm) == 0
    assert ssm.writes == before
    assert describe(old, now).startswith("stale: deploy-staging (deploy) for 120 min")
    fresh = Lock("ops", "run-9", "c" * 40, (now - timedelta(minutes=5)).isoformat(), "ops-task")
    assert describe(fresh, now).startswith("held: ops (ops-task) for 5 min")


def test_the_command_exits_3_when_held_and_4_when_not_the_holder() -> None:
    ssm = FakeSsm()
    take_args = ["take", "--env", "staging", "--holder", "deploy-staging", "--git-sha", "a" * 40]
    assert (
        deploy_lock.main([*take_args, "--run-ref", "run-1", "--purpose", "deploy"], params=ssm)
        == 0
    )
    assert (
        deploy_lock.main([*take_args, "--run-ref", "run-2", "--purpose", "deploy"], params=ssm)
        == 3
    )
    assert deploy_lock.main(["release", "--env", "staging", "--run-ref", "run-2"], params=ssm) == 4
    assert deploy_lock.main(["release", "--env", "staging", "--run-ref", "run-1"], params=ssm) == 0
