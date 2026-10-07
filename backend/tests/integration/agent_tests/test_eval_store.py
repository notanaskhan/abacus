"""SPEC-005 AC-13, AC-14 (TASK-020): the evaluation store against a migrated database. A run is
immutable once finished; case results come only while it runs; eligibility (through the
gateway's own `eligible`) needs the latest finished full-suite real run on the current suite to
have passed; publish refuses forged, replayed, mismatched and unsigned summaries."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import asyncpg
import pytest

from abacus.ai_gateway import EVAL_SUITES, MODELS, eligible
from abacus.kernel.db import TenantContext
from abacus_tools.evals import publish, runner
from abacus_tools.evals.observation import Observation
from abacus_tools.evals.suite import Case, load
from abacus_tools.evals.summary import SIGNING_KEY_ENV, Summary, sign
from abacus_tools.evals.verdict import judge
from abacus_tools.stack import connect_db

from .support import Migrated

AGENT = "evidence.screener"
PROMPT, SUITE_VERSION = EVAL_SUITES[AGENT]
SUITE = Path(__file__).resolve().parents[4] / "evals" / "screening" / "suite.yaml"


def _attempts(*, right: bool = True) -> list[tuple[Case, Observation]]:
    suite = load(SUITE)
    attempts: list[tuple[Case, Observation]] = []
    for case in suite.subset("full"):
        for n in range(1, (suite.repeats if case.key else 1) + 1):
            if case.expected.stage != "screened":
                attempts.append((case, Observation(case.id, n, case.expected.stage)))
                continue
            answer = case.fake_answer
            assert answer is not None
            action = case.expected.action if right else "ready_for_review"
            attempts.append(
                (
                    case,
                    Observation(
                        case.id,
                        n,
                        "screened",
                        action=action,
                        model_action=answer.action if right else "ready_for_review",
                        confidence=answer.confidence,
                        citations_verified=True,
                        contained=True,
                        cost_usd=Decimal("0.001"),
                        budget_usd=Decimal("0.03"),
                    ),
                )
            )
    return attempts


def _summary(
    *,
    model: str,
    fake: bool = False,
    right: bool = True,
    subset: str = "full",
    suite_version: int = SUITE_VERSION,
    finished_at: datetime | None = None,
) -> Summary:
    suite = load(SUITE)
    verdict = judge(
        suite,
        _attempts(right=right),
        fake=fake,
        aborted=False,
        baseline=runner.baseline(AGENT, "small"),
        current_below=0.5,
        route="needs_revision",
    )
    now = finished_at or datetime.now(UTC)
    return Summary.model_validate(
        {
            "id": uuid.uuid4(),
            "agent": AGENT,
            "suite_version": suite_version,
            "prompt_version": PROMPT,
            "model": model,
            "tier": "small",
            "subset": subset,
            "fake": fake,
            "route": "fake",
            "seeds": {"trial_balance": 7},
            "sampling": suite.sampling,
            "status": verdict.status,
            "reasons": verdict.reasons,
            "metrics": verdict.metrics,
            "calibration": json.loads(json.dumps(verdict.calibration)),
            "total_cost_usd": verdict.total_cost_usd,
            "median_case_cost_usd": verdict.median_case_cost_usd,
            "started_at": now - timedelta(minutes=1),
            "finished_at": now,
            "cases": verdict.case_rows,
        }
    )


@pytest.fixture(autouse=True)
def baselines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A cost baseline, so a real run can pass (a missing one fails it)."""
    path = tmp_path / "baselines.yaml"
    path.write_text(f"{AGENT}:\n  small: '1.0'\n")
    monkeypatch.setattr(runner, "BASELINES", path)
    monkeypatch.setenv(SIGNING_KEY_ENV, "test-signing-key")


async def _store(dsn: str, summary: Summary) -> None:
    conn = await connect_db(dsn)
    try:
        await runner.store_start(conn, summary)
        await runner.store_finish(conn, summary)
    finally:
        await conn.close()


async def _eligible(model: str) -> bool:
    tenant = TenantContext(uuid.uuid4(), "agent", f"agent:{AGENT}:eval")
    return await eligible(tenant, AGENT, "fake", "small", model, PROMPT)  # SPEC-010: per route


def _model() -> str:
    return f"test-model-{uuid.uuid4().hex[:8]}"


# --- immutability --------------------------------------------------------------------------------


async def test_ac14_a_run_finishes_once_and_is_immutable_after(migrated_db: Migrated) -> None:
    summary = _summary(model=_model())
    conn = await connect_db(migrated_db.superuser_dsn)
    try:
        await runner.store_start(conn, summary)
        await runner.store_finish(conn, summary)
        for statement in (
            "UPDATE eval_runs SET status = 'failed' WHERE id = $1",
            "UPDATE eval_runs SET subset = 'fast' WHERE id = $1",
            "DELETE FROM eval_runs WHERE id = $1",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute(statement, summary.id)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("TRUNCATE eval_runs CASCADE")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "INSERT INTO eval_case_results (run_id, case_id, attempt, passed, graders, "
                "cost_usd) VALUES ($1, 'late', 1, true, '[]', 0)",
                summary.id,
            )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "UPDATE eval_case_results SET passed = false WHERE run_id = $1", summary.id
            )
    finally:
        await conn.close()


async def test_ac14_the_app_has_no_privileges_on_the_store(migrated_db: Migrated) -> None:
    conn = await connect_db(migrated_db.superuser_dsn)
    try:
        for table in ("eval_runs", "eval_case_results"):
            assert not await conn.fetchval(
                "SELECT has_table_privilege('abacus_app', $1, 'SELECT')", table
            )
    finally:
        await conn.close()


# --- eligibility ---------------------------------------------------------------------------------


async def test_ac13_a_fake_run_is_never_eligible(migrated_db: Migrated) -> None:
    model = _model()
    await _store(migrated_db.superuser_dsn, _summary(model=model, fake=True))
    assert not await _eligible(model)


async def test_ac13_a_passing_real_full_run_is_eligible_until_a_later_run_revokes_it(
    migrated_db: Migrated,
) -> None:
    model = _model()
    start = datetime.now(UTC) - timedelta(hours=1)
    passing = _summary(model=model, finished_at=start)
    assert passing.status == "passed", passing.reasons
    await _store(migrated_db.superuser_dsn, passing)
    assert await _eligible(model)
    # A later fast run, however good, doesn't count.
    await _store(
        migrated_db.superuser_dsn,
        _summary(model=model, subset="fast", finished_at=start + timedelta(minutes=5)),
    )
    assert await _eligible(model)
    # A later failing full run revokes eligibility...
    failing = _summary(model=model, right=False, finished_at=start + timedelta(minutes=10))
    assert failing.status == "failed"
    await _store(migrated_db.superuser_dsn, failing)
    assert not await _eligible(model)
    # ...a newer pass restores it, and a later aborted_cost revokes it again.
    await _store(
        migrated_db.superuser_dsn, _summary(model=model, finished_at=start + timedelta(minutes=15))
    )
    assert await _eligible(model)
    aborted = _summary(model=model, finished_at=start + timedelta(minutes=20)).model_copy(
        update={"status": "aborted_cost", "reasons": ()}
    )
    await _store(migrated_db.superuser_dsn, aborted)
    assert not await _eligible(model)


async def test_ac13_a_run_on_another_suite_version_doesnt_count(migrated_db: Migrated) -> None:
    model = _model()
    other_suite = _summary(model=model, suite_version=SUITE_VERSION + 1)
    await _store(migrated_db.superuser_dsn, other_suite)
    assert not await _eligible(model)


# --- publish -------------------------------------------------------------------------------------


async def test_ac13_publish_loads_a_signed_real_run_and_refuses_its_replay(
    migrated_db: Migrated,
) -> None:
    summary = sign(_summary(model=MODELS["small"][0]))
    await publish.publish(summary, migrated_db.superuser_dsn)
    conn = await connect_db(migrated_db.superuser_dsn)
    try:
        status = await conn.fetchval("SELECT status FROM eval_runs WHERE id = $1", summary.id)
    finally:
        await conn.close()
    assert status == "passed"
    with pytest.raises(publish.Refused, match="replay"):
        await publish.publish(
            sign(summary.model_copy(update={"id": uuid.uuid4()})), migrated_db.superuser_dsn
        )


async def test_ac13_publish_refuses_a_bad_signature(migrated_db: Migrated) -> None:
    summary = _summary(model=MODELS["small"][0]).model_copy(update={"signature": "0" * 64})
    with pytest.raises(publish.Refused, match="signature"):
        await publish.publish(summary, migrated_db.superuser_dsn)


async def test_ac13_publish_refuses_a_wrong_model(migrated_db: Migrated) -> None:
    with pytest.raises(publish.Refused, match="tier's"):
        await publish.publish(sign(_summary(model=MODELS["large"][0])), migrated_db.superuser_dsn)


async def test_ac13_publish_refuses_a_forged_status(migrated_db: Migrated) -> None:
    forged = sign(
        _summary(model=MODELS["small"][0], right=False).model_copy(
            update={"status": "passed", "reasons": ()}
        )
    )
    with pytest.raises(publish.Refused, match="doesn't follow"):
        await publish.publish(forged, migrated_db.superuser_dsn)
