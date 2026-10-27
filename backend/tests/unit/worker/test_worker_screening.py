"""AC-14, AC-20: the worker runs the relay and routes events to module subscriptions (TASK-011b
interface contract, "Worker"; TASK-011 Q4)."""

from __future__ import annotations

import asyncio
import importlib
import os
import signal
import uuid
from collections.abc import Sequence

import pytest

from abacus.kernel.config import settings
from abacus.kernel.uow.relay import Handler, OutboxEvent, Publisher, RoutingPublisher
from abacus.modules.agents.screenings import EVIDENCE_VERSION_CREATED
from abacus.worker import __main__ as worker_main


class _Worker:
    """A pool as the worker drives it: `run()` until `shutdown()`."""

    def __init__(self, log: list[str]) -> None:
        self.log = log
        self._stop = asyncio.Event()

    async def run(self) -> None:
        self.log.append("worker entered")
        await self._stop.wait()
        self.log.append("worker exited")

    async def shutdown(self) -> None:
        self._stop.set()


def _event(event_type: str) -> OutboxEvent:
    return OutboxEvent(uuid.uuid4(), uuid.uuid4(), event_type, {})


def test_ac14_the_worker_hosts_connections_and_agents() -> None:
    # SPEC-013: notifications subscribes to its catalogued events.
    # F-03-T07: collected from each module's api.py, in MODULES order.
    assert tuple(m.__name__.split(".")[2] for m in worker_main.MODULES) == (
        "agents",
        "assurance",  # A-01-T05: a computed gate's `gate.met` derives the phase it opens
        "communications",  # SPEC-015: invitation emails
        "connections",
        "evidence",  # SPEC-029 (TASK-054): upload processing
        "fieldwork",  # SPEC-037 (TASK-083): procedure selection
        "identity",  # P-08-T17: access changes end portal sessions and trusted devices
        "notifications",
        "platform",  # Q-01-T45: tenant provisioning
        "portal",  # R-01-T13: the request owner hears of a third party's upload
        "requests",  # P-06-T07: binders close on C1's terminal transitions
        "review",  # P-04-T16: the human-gate projector (C13)
    )
    assert tuple(m.SUBSCRIPTIONS for m in worker_main.MODULES) == worker_main.SUBSCRIBERS
    # SPEC-022 (TASK-038): automatic retrieval when a client connects or an item is classified.
    assert set(importlib.import_module("abacus.modules.connections.api").SUBSCRIPTIONS) == {
        "connection.created",
        "request_item.classified",
        "ledger_snapshot.recorded",  # SPEC-034 (TASK-069): waiting general ledgers follow
        # A-02-T16: a disconnected or replaced grant is revoked at the provider after commit.
        "connection_grant.revocation_requested",
    }
    assert worker_main.agents.SUBSCRIPTIONS in worker_main.SUBSCRIBERS


def test_ac14_the_publisher_routes_evidence_version_created_to_start_screening() -> None:
    built = worker_main.publisher()
    assert isinstance(built, RoutingPublisher)
    # SPEC-009 adds knowledge embedding beside screening.
    # Q-01-T26: the worker no longer imports notifications (its purge is a Schedule).
    catalogue = importlib.import_module("abacus.modules.notifications.api").CATALOGUE
    assert set(built.handlers) == set(catalogue) | {
        EVIDENCE_VERSION_CREATED,
        "knowledge_document.added",
        "client_invitation.issued",  # SPEC-015
        "portal.sign_in_code_requested",  # P-08-T10: the code is issued at delivery
        "staff_invitation.issued",  # SPEC-024 (TASK-041)
        "request_item.classified",  # SPEC-022: automatic retrieval
        "inbox_file.added",  # SPEC-027 (TASK-050): the engagement agent
        "firm.agents_resumed",
        "engagement.created",
        "due_dates.changed",  # SPEC-027 (TASK-051)
        "request_item.document_kind_changed",  # SPEC-029 (TASK-055 D5): re-check the upload
        "upload_checks.recorded",  # SPEC-030 (TASK-059): the upload reviewer may follow
        "inbox_file.extracted",  # SPEC-033 (TASK-066): the matcher may follow
        "follow_up.sent",  # P-06-T14: a sent follow-up's email, after the Undo window
        "ledger_snapshot.recorded",  # SPEC-034 (TASK-069): waiting general ledgers follow
        "work_item.status_changed",  # P-06-T07: binders close
        "engagement.status_changed",
        "legal_hold.lifted",  # Q-02-T29: LegalHoldRelease starts (placed also notifies)
        "access.changed",  # P-08-T17: portal sessions and trusted devices end
        "client_access.revoked",
        "portal.link_renew_requested",  # P-08-T21: a renewed link's email, token at delivery
        "portal_mfa.reset_notice_requested",  # P-08-T21: the firm reset the second step
        "gate.met",  # A-01-T05: the phase a computed gate opens is derived
        "evidence_version.withdrawn",  # P-06-T19: the withdrawal purge starts
        "fulfilment.voided",  # R-01 Story 2.2 (TASK-1248): the gates recompute
        "upload_review.recorded",  # P-06-T20: the screening aggregate recomposes
        # P-04-T16 (C13): the human-gate projector reconciles the gates these may change.
        "proposal.recorded",
        "guidance_draft.decided",
        "review_decision.recorded",
        "inbox_file.sorted",
        # On main since S10 but missing from this list (ED-165): the export build's start
        # (A-01-T19), the TB and workpaper staleness subscribers, the AI boundary facts.
        "engagement_export.requested",
        "trial_balance.version_created",
        "workpaper.content_changed",
        "ai_boundary.facts_changed",
        # A-01-T22: an expired or voided export's segments are deleted.
        "engagement_export.expired",
        "engagement_export.voided",
        # P-07-T47 (DEC-539): the C13 projector's engagement gates.
        "acceptance.decided",
        "independence.confirmed",
        "independence.declined",
        "independence.concluded",
        "eqr.eligibility_approved",
        # A-02-T16: grant revocation; A-02-T17: a changed tie-out check makes sign-offs stale.
        "connection_grant.revocation_requested",
        "tie_out_check.changed",
    }
    # SPEC-022: a new connection both notifies the leads and starts automatic retrieval.
    assert (
        importlib.import_module("abacus.modules.connections.api").on_connection_created
        in built.handlers["connection.created"]
    )
    assert list(built.handlers[EVIDENCE_VERSION_CREATED]) == [
        worker_main.agents.start_screening,
        # SPEC-029 (TASK-056 D1): every new version is processed, for previews.
        importlib.import_module("abacus.modules.evidence.api").SUBSCRIPTIONS[
            EVIDENCE_VERSION_CREATED
        ],
    ]


async def test_ac14_the_publisher_runs_every_subscribed_handler_and_ignores_other_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str]] = []

    def recorder(name: str) -> Handler:
        async def handle(event: OutboxEvent) -> None:
            seen.append((name, event.event_type))

        return handle

    monkeypatch.setattr(
        worker_main,
        "SUBSCRIBERS",
        (
            {"a.happened": recorder("one")},
            {"a.happened": recorder("two"), "b.happened": recorder("three")},
        ),
    )
    built = worker_main.publisher()
    await built.publish(_event("a.happened"))
    await built.publish(_event("b.happened"))
    await built.publish(_event("c.happened"))
    assert seen == [("one", "a.happened"), ("two", "a.happened"), ("three", "b.happened")]


async def test_ac20_a_failed_relay_database_check_stops_the_boot_after_ping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def ping() -> None:
        calls.append("ping")

    async def ping_relay() -> None:
        calls.append("ping_relay")
        raise RuntimeError("relay role cannot connect")

    monkeypatch.setattr(worker_main, "ping", ping)
    monkeypatch.setattr(worker_main, "ping_relay", ping_relay)
    monkeypatch.setattr(worker_main, "key_service", lambda: calls.append("keys"))
    with pytest.raises(RuntimeError, match="relay role cannot connect"):
        await worker_main.build_workers()
    assert calls == ["ping", "ping_relay"]


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
async def test_ac20_run_hosts_the_relay_inside_the_worker_until_the_signal(
    monkeypatch: pytest.MonkeyPatch, sig: signal.Signals
) -> None:
    log: list[str] = []
    seen: dict[str, object] = {}

    async def build(classes: Sequence[str]) -> list[_Worker]:
        return [_Worker(log)]

    async def relay(publisher: Publisher, stop: asyncio.Event) -> None:
        seen["publisher"] = publisher
        seen["stop"] = stop
        log.append("relay started")
        await stop.wait()
        await asyncio.sleep(0.05)
        log.append("relay finished")

    monkeypatch.setattr(worker_main, "build_workers", build)
    monkeypatch.setattr(worker_main, "run_relay", relay)
    asyncio.get_running_loop().call_later(0.1, os.kill, os.getpid(), sig)
    await asyncio.wait_for(worker_main.run(), timeout=10)
    # Pools shut down together with the relay's stop (contract revision 1): no fixed exit order.
    assert log[:2] == ["worker entered", "relay started"]
    assert sorted(log[2:]) == ["relay finished", "worker exited"]
    assert isinstance(seen["publisher"], RoutingPublisher)
    stop = seen["stop"]
    assert isinstance(stop, asyncio.Event)
    assert stop.is_set()


async def test_ac20_a_relay_that_dies_stops_the_worker_and_its_error_is_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []

    async def build(classes: Sequence[str]) -> list[_Worker]:
        return [_Worker(log)]

    async def dying(publisher: Publisher, stop: asyncio.Event) -> None:
        raise RuntimeError("relay crashed")

    monkeypatch.setattr(worker_main, "build_workers", build)
    monkeypatch.setattr(worker_main, "run_relay", dying)
    with pytest.raises(RuntimeError, match="relay crashed"):
        await asyncio.wait_for(worker_main.run(), timeout=10)  # no signal is sent
    assert log == ["worker entered", "worker exited"]


@pytest.mark.parametrize(("environment", "configured"), [("local", True), ("test", False)])
async def test_ac14_the_fake_provider_is_configured_only_in_local(
    monkeypatch: pytest.MonkeyPatch, environment: str, configured: bool
) -> None:
    provided: list[object] = []

    async def nothing() -> None:
        return None

    async def client() -> str:
        return "temporal-client"

    def fake_worker(client: object, **kwargs: object) -> str:
        return "the-worker"

    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    settings.cache_clear()
    try:
        monkeypatch.setattr(worker_main, "ping", nothing)
        monkeypatch.setattr(worker_main, "ping_relay", nothing)
        monkeypatch.setattr(worker_main, "key_service", lambda: None)
        monkeypatch.setattr(worker_main, "payload_codec", lambda: None)
        monkeypatch.setattr(worker_main, "check_ready", nothing)
        monkeypatch.setattr(worker_main, "temporal_client", client)
        monkeypatch.setattr(worker_main, "Worker", fake_worker)
        monkeypatch.setattr(worker_main, "configure_provider", provided.append)
        await worker_main.build_workers()
    finally:
        monkeypatch.undo()
        settings.cache_clear()
    assert bool(provided) is configured
