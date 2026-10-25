"""The canary (Q-01-T30; Q-01 F6 and §4.5; SLO-10). PROTECTED.

`CanaryWorkflow` (`canary:<tenant>`, time_sensitive) runs every 15 minutes on its Schedule as the
canary staff member of a synthetic firm ("Canary & Co"): it creates a request item, uploads a
synthetic PDF, waits for the scan, extraction and preview, runs the screener on the route the
environment's boundary allows, observes the upload's outbox event and sends a reminder to the
SES simulator address. Each step is an activity over the `CanaryProbe` port (`ServiceProbe` in
`abacus.worker.canary_probe`
is the service implementation, beside the worker); the checks that decide a pass are here, in code:

- **Synthetic only.** `canary.prepare` refuses a firm that is not synthetic, or a staff member
  who is not an active member, before anything is written (`CanaryNotSynthetic`).
- **INV-2.** Every flag the screener returns carries a code-verified citation, or is shown
  Uncited; a citation whose verification never ran fails the run as well (`inv2_violations`).
- **The route.** `synthetic_only` allows the fake route only; `client_data` allows Bedrock only,
  and under it the screener must have run (`expected_route`).
- **Paging.** A pass beats the heartbeat. The second consecutive failure calls the heartbeat's
  fail URL, once; the first failure and the third onward call nothing, so one bad run never
  pages and an open incident is not paged again (`should_page`, over the Schedule's previous
  runs through `kernel.dispatch.schedule_results`: no table, no row).

Results: the metric `abacus.canary.run` (outcome and the failed step's code) and a log line of
codes. The run writes only in the synthetic firm, through the same services a person uses.
"""

from __future__ import annotations

from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from typing import Final, Literal, Protocol
from uuid import UUID

import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.kernel.config import settings
from abacus.kernel.dispatch import (
    PlatformSchedule,
    ScheduledRun,
    WorkClass,
    register_work_classes,
    schedule_results,
)
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.modules.platform.workflow_types import (
    CanaryInput,
    CanaryOutcome,
    CanaryPlan,
    CanaryResult,
)
from abacus.modules.platform.workflows import CANARY_EVERY, CanaryWorkflow, canary_workflow_id

_log = get_logger(__name__)
_runs = meter(__name__).create_counter(
    "abacus.canary.run", description="Canary runs, by outcome and the failed step's code"
)
NOT_SYNTHETIC: Final = "CanaryNotSynthetic"
STEP_FAILED: Final = "CanaryStepFailed"
Boundary = Literal["synthetic_only", "client_data"]


class CanaryNotSynthetic(Exception):
    """The canary's firm is not synthetic, or its staff member is not an active member."""


class CanaryStepFailed(Exception):
    """A step ran and its check failed; `code` says which (no data)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# --- What the screener returned --------------------------------------------------------------


@dataclass(frozen=True)
class CanaryFlag:
    """One flag as returned: each citation's code verification (True, False, or None when it
    never ran) and whether the flag is shown Uncited."""

    category: str
    citations_verified: tuple[bool | None, ...]
    shown_uncited: bool


@dataclass(frozen=True)
class CanaryScreen:
    route: str  # the route that answered, or the boundary's route when the screener did not run
    ran: bool  # False: no screener answers on this route yet (no flags)
    flags: tuple[CanaryFlag, ...]


def inv2_violations(flags: Sequence[CanaryFlag]) -> list[str]:
    """INV-2: the categories of flags that break it. A flag passes when its verification ran on
    every citation and it either carries a verified one or is shown Uncited."""
    broken: list[str] = []
    for flag in flags:
        if any(v is None for v in flag.citations_verified):
            broken.append(flag.category)  # a citation code never checked
        elif not flag.shown_uncited and not any(flag.citations_verified):
            broken.append(flag.category)  # shown as cited with nothing verified
    return broken


def expected_route(boundary: Boundary) -> str:
    """The one route a canary run may be screened on (ADR-113, SPEC-026, SPEC-036)."""
    return "bedrock" if boundary == "client_data" else "fake"


def boundary() -> Boundary:
    return settings().model_data_boundary


def should_page(passed: bool, previous_failed: Sequence[bool]) -> bool:
    """Page on the second consecutive failure only: this run failed, the one before failed, and
    the one before that (if any) did not. `previous_failed` is newest first."""
    if passed or not previous_failed or not previous_failed[0]:
        return False
    return len(previous_failed) < 2 or not previous_failed[1]


def _failed(run: ScheduledRun) -> bool:
    if not run.completed or not isinstance(run.result, dict):
        return True  # a run that did not complete is a failed canary run
    return run.result.get("passed") is not True  # pyright: ignore[reportUnknownMemberType] -- a decoded CanaryResult


# --- Ports --------------------------------------------------------------------------------------


class CanaryProbe(Protocol):
    """What the canary does in the product, as the canary staff member. Each method raises
    `CanaryStepFailed` when its own check fails; any other error is retried, then fails it."""

    async def prepare(self, tenant_id: UUID) -> CanaryPlan: ...
    async def create_item(self, plan: CanaryPlan) -> UUID: ...
    async def upload(self, plan: CanaryPlan, item_id: UUID) -> UUID: ...
    async def wait_processing(self, plan: CanaryPlan, item_id: UUID, version_id: UUID) -> None: ...
    async def screen(self, plan: CanaryPlan, item_id: UUID, version_id: UUID) -> CanaryScreen: ...
    async def observe_outbox(self, plan: CanaryPlan, version_id: UUID) -> None: ...
    async def send_simulator(self, plan: CanaryPlan) -> None: ...


class Heartbeat(Protocol):
    """Better Stack's heartbeat: a beat on a pass, the fail URL on a page."""

    async def beat(self) -> None: ...
    async def fail(self, code: str) -> None: ...


class HttpHeartbeat:
    """The heartbeat URL (Restricted: it carries a token; never logged)."""

    def __init__(self, url: str) -> None:
        self._url = url.rstrip("/")

    async def beat(self) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            (await client.get(self._url)).raise_for_status()

    async def fail(self, code: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            (await client.post(f"{self._url}/fail", content=code.encode())).raise_for_status()


class LoggedHeartbeat:
    """No heartbeat URL (local and test): beats and pages are log lines only."""

    async def beat(self) -> None:
        _log.info("canary.heartbeat", outcome="passed")

    async def fail(self, code: str) -> None:
        _log.warning("canary.paged", code=code)


class RecordingHeartbeat:
    """For tests: what was sent, in order (`beat` or `fail:<code>`)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def beat(self) -> None:
        self.calls.append("beat")

    async def fail(self, code: str) -> None:
        self.calls.append(f"fail:{code}")


_probe: CanaryProbe | None = None
_heartbeat: Heartbeat | None = None


def configure_canary_probe(probe: CanaryProbe | None) -> None:
    global _probe
    _probe = probe


def configure_heartbeat(heartbeat: Heartbeat | None) -> None:
    global _heartbeat
    _heartbeat = heartbeat


def canary_probe() -> CanaryProbe:
    """The worker configures the service probe at boot (`abacus.worker.canary_probe`)."""
    if _probe is None:
        raise RuntimeError("no canary probe is configured (the worker sets it at boot)")
    return _probe


def heartbeat() -> Heartbeat:
    if _heartbeat is not None:
        return _heartbeat
    url = settings().canary_heartbeat_url
    return HttpHeartbeat(url.get_secret_value()) if url is not None else LoggedHeartbeat()


# --- Activities (names are the workflow's; arguments are identifiers) -------------------------


def _step_failed(code: str) -> ApplicationError:
    return ApplicationError(code, type=STEP_FAILED, non_retryable=True)


async def _guard[T](step: Awaitable[T]) -> T:
    """Turn the probe's own failures into non-retryable errors carrying their code."""
    try:
        return await step
    except CanaryNotSynthetic as refused:
        raise ApplicationError("not_synthetic", type=NOT_SYNTHETIC, non_retryable=True) from (
            refused
        )
    except CanaryStepFailed as failed:
        raise _step_failed(failed.code) from failed


@activity.defn(name="canary.prepare")
async def prepare_activity(given: CanaryInput) -> CanaryPlan:
    return await _guard(canary_probe().prepare(UUID(given.tenant_id)))


@activity.defn(name="canary.create_item")
async def create_item_activity(plan: CanaryPlan) -> str:
    return str(await _guard(canary_probe().create_item(plan)))


@activity.defn(name="canary.upload")
async def upload_activity(plan: CanaryPlan, item_id: str) -> str:
    return str(await _guard(canary_probe().upload(plan, UUID(item_id))))


@activity.defn(name="canary.wait_processing")
async def wait_processing_activity(plan: CanaryPlan, item_id: str, version_id: str) -> None:
    await _guard(canary_probe().wait_processing(plan, UUID(item_id), UUID(version_id)))


@activity.defn(name="canary.screen")
async def screen_activity(plan: CanaryPlan, item_id: str, version_id: str) -> str:
    """The screener's result, checked in code: the boundary's route and INV-2."""
    found: CanaryScreen = await _guard(
        canary_probe().screen(plan, UUID(item_id), UUID(version_id))
    )
    allowed = expected_route(boundary())
    if found.route != allowed:
        raise _step_failed("route_not_allowed")
    if allowed != "fake" and not found.ran:
        raise _step_failed("screener_not_run")  # a real route must have answered
    if inv2_violations(found.flags):
        raise _step_failed("uncited_flag")
    return found.route


@activity.defn(name="canary.observe_outbox")
async def observe_outbox_activity(plan: CanaryPlan, version_id: str) -> None:
    await _guard(canary_probe().observe_outbox(plan, UUID(version_id)))


@activity.defn(name="canary.send_simulator")
async def send_simulator_activity(plan: CanaryPlan) -> None:
    await _guard(canary_probe().send_simulator(plan))


@activity.defn(name="canary.report")
async def report_activity(outcome: CanaryOutcome) -> CanaryResult:
    """Beat or page (the second consecutive failure only), count the run and log its codes."""
    previous = await schedule_results(
        canary_workflow_id(outcome.tenant_id),
        exclude_run_id=activity.info().workflow_run_id,
        limit=2,
    )
    page = should_page(outcome.passed, [_failed(run) for run in previous])
    if outcome.passed:
        await heartbeat().beat()
    elif page:
        await heartbeat().fail(f"{outcome.failed_step}:{outcome.code}")
    _runs.add(
        1,
        {"outcome": "passed" if outcome.passed else "failed", "reason": outcome.code or "none"},
    )
    _log.info(
        "canary.run",
        tenant_id=outcome.tenant_id,
        passed=outcome.passed,
        failed_step=outcome.failed_step,
        code=outcome.code,
        route=outcome.route,
        paged=page,
    )
    return CanaryResult(
        outcome.tenant_id,
        outcome.passed,
        outcome.failed_step,
        outcome.code,
        outcome.route,
        page,
    )


CANARY_ACTIVITIES: tuple[object, ...] = (
    prepare_activity,
    create_item_activity,
    upload_activity,
    wait_processing_activity,
    screen_activity,
    observe_outbox_activity,
    send_simulator_activity,
    report_activity,
)
WORKFLOWS: dict[type, WorkClass] = {CanaryWorkflow: "time_sensitive"}
register_work_classes(WORKFLOWS)


def canary_schedules() -> tuple[PlatformSchedule, ...]:
    """The canary's Schedule, when this environment names a canary firm (`canary_tenant_id`)."""
    tenant = settings().canary_tenant_id
    if tenant is None:
        return ()
    return (
        PlatformSchedule(
            id=canary_workflow_id(str(tenant)),
            workflow=CanaryWorkflow,
            every=CANARY_EVERY,
            note="Q-01-T30: the canary, every 15 minutes (SLO-10)",
            arg=CanaryInput(str(tenant)),
        ),
    )
