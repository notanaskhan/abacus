"""The deploy lock (Q-01-T18; platform-ops contract section 3.4). One SSM parameter per
environment, `/abacus/<env>/deploy-lock`, holding who holds it:
`{"holder", "run_ref", "git_sha", "taken_at", "purpose"}` (Internal; no client data).

    python -m abacus_tools.deploy_lock take --env staging --holder deploy-staging \
        --run-ref <run url> --git-sha <sha> --purpose deploy [--wait-seconds 1800]
    python -m abacus_tools.deploy_lock release --env staging --run-ref <run url>
    python -m abacus_tools.deploy_lock show --env staging      # `make deploy-lock ENV=staging`

`take` creates the parameter only if it does not exist (SSM `PutParameter` without overwrite is
the atomic test-and-set), so two deploys never both hold it; with `--wait-seconds` a second
deploy waits for the first to release, and never takes a stale lock by itself (an operator
releases a stale lock through an ops request). `release` deletes it only for the run that holds
it. `show` is read only: the holder and its age, `stale` past `STALE_AFTER`, or `free`. F-01's
`db_guard` refuses while the lock of `ABACUS_DEPLOY_LOCK_ENV` is held (`held`).

Taken by `deploy-staging.yml`, `deploy-production.yml`, `rollback.yml`, `ops-task.yml` and
`drill.yml` after their GitHub `concurrency` group and before their first change; released on
success, failure and cancellation.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal, Protocol

import boto3
from botocore.exceptions import ClientError

from abacus.kernel.clock import system_now

if TYPE_CHECKING:
    from types_boto3_ssm import SSMClient

ENVIRONMENTS: Final = ("staging", "production")
STALE_AFTER: Final = timedelta(minutes=90)  # longer than any holder's maximum run
POLL_SECONDS: Final = 15.0
Purpose = Literal["deploy", "ops-task"]


def parameter_name(env: str) -> str:
    if env not in ENVIRONMENTS:
        raise ValueError(f"no deploy lock for {env!r}")
    return f"/abacus/{env}/deploy-lock"


@dataclass(frozen=True)
class Lock:
    holder: str
    run_ref: str
    git_sha: str
    taken_at: str
    purpose: str

    def age(self, now: datetime) -> timedelta:
        return now - datetime.fromisoformat(self.taken_at)

    def stale(self, now: datetime) -> bool:
        return self.age(now) > STALE_AFTER


class Parameters(Protocol):
    """The three SSM calls the lock uses (a fake in tests)."""

    def create(self, name: str, value: str) -> bool: ...  # False: it already exists
    def read(self, name: str) -> str | None: ...
    def delete(self, name: str) -> None: ...


class SsmParameters:
    def __init__(self, client: SSMClient) -> None:
        self._client = client

    def create(self, name: str, value: str) -> bool:
        try:
            self._client.put_parameter(Name=name, Value=value, Type="String", Overwrite=False)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ParameterAlreadyExists":
                return False
            raise
        return True

    def read(self, name: str) -> str | None:
        try:
            found = self._client.get_parameter(Name=name)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ParameterNotFound":
                return None
            raise
        return found["Parameter"].get("Value")

    def delete(self, name: str) -> None:
        try:
            self._client.delete_parameter(Name=name)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ParameterNotFound":
                raise


def _ssm() -> Parameters:
    client: SSMClient = boto3.client("ssm")  # pyright: ignore[reportUnknownMemberType] -- region from the environment
    return SsmParameters(client)


def current(params: Parameters, env: str) -> Lock | None:
    raw = params.read(parameter_name(env))
    return Lock(**json.loads(raw)) if raw is not None else None


def take(
    params: Parameters,
    env: str,
    *,
    holder: str,
    run_ref: str,
    git_sha: str,
    purpose: Purpose,
    wait_seconds: float = 0.0,
    now: Callable[[], datetime] = system_now,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[bool, Lock | None]:
    """Take the lock: (True, ours) or, after waiting up to `wait_seconds`, (False, the holder's).
    The same run taking it again is a no-op success."""
    deadline = time.monotonic() + wait_seconds
    while True:
        ours = Lock(holder, run_ref, git_sha, now().isoformat(), purpose)
        if params.create(parameter_name(env), json.dumps(asdict(ours), sort_keys=True)):
            return True, ours
        held = current(params, env)
        if held is not None and held.run_ref == run_ref:
            return True, held
        if held is not None and time.monotonic() >= deadline:
            return False, held
        sleep(POLL_SECONDS)


def release(params: Parameters, env: str, *, run_ref: str) -> bool:
    """Release the lock this run holds; False (and nothing deleted) when another run holds it."""
    held = current(params, env)
    if held is None:
        return True
    if held.run_ref != run_ref:
        return False
    params.delete(parameter_name(env))
    return True


def held(env: str, params: Parameters | None = None) -> Lock | None:
    """The lock's holder, or None: for F-01's `db_guard`."""
    return current(params or _ssm(), env)


def describe(lock: Lock | None, now: datetime) -> str:
    if lock is None:
        return "free"
    minutes = int(lock.age(now).total_seconds() // 60)
    state = "stale" if lock.stale(now) else "held"
    return (
        f"{state}: {lock.holder} ({lock.purpose}) for {minutes} min, "
        f"run {lock.run_ref}, sha {lock.git_sha}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.deploy_lock")
    sub = parser.add_subparsers(dest="command", required=True)
    taking = sub.add_parser("take")
    taking.add_argument("--env", required=True, choices=ENVIRONMENTS)
    taking.add_argument("--holder", required=True)
    taking.add_argument("--run-ref", required=True)
    taking.add_argument("--git-sha", required=True)
    taking.add_argument("--purpose", required=True, choices=("deploy", "ops-task"))
    taking.add_argument("--wait-seconds", type=float, default=0.0)
    releasing = sub.add_parser("release")
    releasing.add_argument("--env", required=True, choices=ENVIRONMENTS)
    releasing.add_argument("--run-ref", required=True)
    showing = sub.add_parser("show")
    showing.add_argument("--env", required=True, choices=ENVIRONMENTS)
    return parser


def main(argv: list[str] | None = None, params: Parameters | None = None) -> int:
    args = _parser().parse_args(argv)
    ssm = params or _ssm()
    now = system_now()
    if args.command == "show":
        print(describe(current(ssm, args.env), now))
        return 0
    if args.command == "release":
        if release(ssm, args.env, run_ref=args.run_ref):
            print(f"released {parameter_name(args.env)}")
            return 0
        print(f"not released: {describe(current(ssm, args.env), now)}", file=sys.stderr)
        return 4
    taken, lock = take(
        ssm,
        args.env,
        holder=args.holder,
        run_ref=args.run_ref,
        git_sha=args.git_sha,
        purpose=args.purpose,
        wait_seconds=args.wait_seconds,
    )
    if taken:
        print(f"taken {parameter_name(args.env)}")
        return 0
    print(f"held: {describe(lock, now)}", file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main())
