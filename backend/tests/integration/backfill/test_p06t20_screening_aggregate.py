"""SPEC-319 AC-21 to AC-28 (P-06-T20; DEC-48, DEC-324): the screening aggregate, end to end.

Code composes a superseding `request_batch` row of `screening_results` from the code checks and
the verified review flags of a request item's live versions. The card, its rerun and feedback are
a person's reads and acts. No aggregate path writes a request's status or a review decision, and
the period verdict is code's alone.

Boundary: `create_app()` over HTTP and the migrated Postgres. The per-version rows (extractions,
checks, runs, reviews, flags, citations) are seeded as the superuser: no route makes them without
a model. The composer runs as the subscriber would, in its system context.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from typing import Literal, cast

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import OutboxEvent, Target, uow
from abacus.modules.agents import screening_card, upload_review
from abacus.modules.agents.api import ScreeningInput, create_review_run
from abacus.modules.agents.screening_aggregate import compose_for_item, on_version_withdrawn

from .support import Net, Person, Seeder, Site

REVIEWER = "evidence.upload_reviewer"
JUNE_1 = date(2026, 6, 1)
SEP_18 = date(2026, 9, 18)


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    owner: Person
    manager: Person
    client: Person
    site: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def card_path(self) -> str:
        return (
            f"/v1/engagements/{self.site.engagement_id}/request-items/{self.site.item_id}"
            "/screening"
        )

    async def version(
        self, title: str, item: uuid.UUID | None = None, *, detached: bool = False
    ) -> uuid.UUID:
        """A new evidence version fulfilling the item (the site's by default); `detached`: a
        client upload in detached-key mode, the kind a client may withdraw (ADR-162)."""
        evidence = await self.seed.value(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, $3, 'system', 'seed') RETURNING id",
            self.tenant_id,
            self.site.engagement_id,
            title,
        )
        version = uuid.uuid4()
        fingerprint = uuid.uuid4().hex * 2
        key = (
            f"tenants/{self.tenant_id}/v/{version}"
            if detached
            else f"tenants/{self.tenant_id}/sha256/{fingerprint}"
        )
        await self.seed.run(
            "INSERT INTO evidence_versions (id, tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, "
            "media_type, source, method, storage_mode) VALUES ($1, $2, $3, $4, 1, $5, $6, 'v1', "
            "10, 'application/pdf', 'upload', 'uploaded', $7)",
            version,
            self.tenant_id,
            self.site.engagement_id,
            evidence,
            fingerprint,
            key,
            "detached_key" if detached else "content_addressed",
        )
        if detached:
            await self.seed.run(
                "INSERT INTO evidence_object_keys (tenant_id, evidence_version_id, key_id, "
                "wrapped_key) VALUES ($1, $2, 'local', $3)",
                self.tenant_id,
                version,
                bytes(32),
            )
        await self.seed.run(
            "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
            "evidence_version_id, created_by_kind, created_by_id) "
            "VALUES ($1, $2, $3, $4, 'human', 'seed')",
            self.tenant_id,
            self.site.engagement_id,
            item or self.site.item_id,
            version,
        )
        return version

    async def dated(
        self, version: uuid.UUID, *, as_of: date | None = None, period_check: str | None = None
    ) -> None:
        """Code's facts: an extraction with the document's date, and the period check."""
        await self.seed.run(
            "INSERT INTO upload_extractions (tenant_id, engagement_id, evidence_version_id, "
            "extractor_version, status, as_of) VALUES ($1, $2, $3, 'v1', 'extracted', $4)",
            self.tenant_id,
            self.site.engagement_id,
            version,
            as_of,
        )
        if period_check is not None:
            await self.seed.run(
                "INSERT INTO upload_checks (tenant_id, engagement_id, evidence_version_id, "
                "checker_version, check_code, outcome, audience) "
                "VALUES ($1, $2, $3, 'v2', 'wrong_period', $4, 'client')",
                self.tenant_id,
                self.site.engagement_id,
                version,
                period_check,
            )

    async def run(self, version: uuid.UUID, status: str = "completed") -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
                "evidence_version_id, initiator_user_id, task_scope, status, finished_at) "
                "VALUES ($1, $2, 1, $3, $4, $5, ARRAY['evidence.read'], $6, "
                "CASE WHEN $6 = 'running' THEN NULL ELSE clock_timestamp() END) RETURNING id",
                self.tenant_id,
                REVIEWER,
                self.site.engagement_id,
                version,
                self.manager.user_id,
                status,
            ),
        )

    async def review(
        self, version: uuid.UUID, flag: str | None = None, *, shown: bool = True
    ) -> uuid.UUID | None:
        """A completed review; with `flag`, one flag and its verified v2 citation (returned)."""
        run = await self.run(version)
        review = await self.seed.value(
            "INSERT INTO upload_reviews (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, prompt_ref, no_concerns) VALUES ($1, $2, $3, $4, "
            "'evidence.upload_review@v3', $5) RETURNING id",
            self.tenant_id,
            self.site.engagement_id,
            version,
            run,
            flag is None,
        )
        if flag is None:
            return None
        await self.seed.run(
            "INSERT INTO upload_review_flags (tenant_id, review_id, position, category, "
            "confidence, rationale, citations, shown) VALUES ($1, $2, 1, $3, 0.9, "
            '\'Not what was asked for\', \'[{"quote": "STATEMENT", "verified": true}]\', $4)',
            self.tenant_id,
            review,
            flag,
            shown,
        )
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, "
                "cited_from_id, cited_from_ref, n, kind, source_type, source_id, locator, "
                "match_id, quote_sha256, verified, verifier_version, created_by_kind, "
                "created_by_run_id) VALUES ($1, $2, 'upload_review', $3, 'F1', 1, "
                "'document_text', 'evidence_version', $4, '{\"page\": 1}', $5, $6, true, 'v1', "
                "'agent', $7) RETURNING id",
                self.tenant_id,
                self.site.engagement_id,
                review,
                version,
                f"ev:{version.hex[:12]}#p1",
                bytes(32),
                run,
            ),
        )

    async def card(self, who: Person | None = None) -> dict[str, object]:
        response = await self.net.call("GET", self.card_path, who or self.manager)
        assert response.status_code == 200, response.text
        return cast(dict[str, object], response.json())

    async def compose(self) -> uuid.UUID | None:
        return await compose_for_item(self.tenant_id, self.site.item_id)

    async def aggregates(self) -> list[asyncpg.Record]:
        return await self.seed.rows(
            "SELECT * FROM screening_results WHERE tenant_id = $1 "
            "AND subject_kind = 'request_batch' ORDER BY batch_no",
            self.tenant_id,
        )


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'screening.card', 'true', 'test-seed', 'DEC-324')",
        tenant_id,
    )
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Granite")
    manager = await seed.person(tenant_id)
    await seed.member(site, manager, "manager")
    client = await seed.client_contact(site, "client_admin")
    await seed.run(
        "UPDATE request_items SET period_start = $2, period_end = $3 WHERE id = $1",
        site.item_id,
        JUNE_1,
        SEP_18,
    )
    return Firm(net, tenant_id, owner, manager, client, site)


def _check(card: dict[str, object], key: str) -> dict[str, object]:
    checks = cast(list[dict[str, object]], card["checks"])
    return next(c for c in checks if c["key"] == key)


# --- AC-21: composed by code, superseding, never updated ---------------------------------------


async def test_ac21_each_change_supersedes_and_an_unchanged_one_writes_nothing(
    firm: Firm,
) -> None:
    first = await firm.version("July statement.pdf")
    await firm.dated(first, as_of=date(2026, 7, 31))
    one = await firm.compose()
    assert one is not None
    assert await firm.compose() is None  # redelivered: nothing changed, nothing written
    second = await firm.version("August statement.pdf")
    await firm.dated(second, as_of=date(2026, 8, 31))
    two = await firm.compose()
    rows = await firm.aggregates()
    assert [r["id"] for r in rows] == [one, two]
    assert [r["batch_no"] for r in rows] == [1, 2]
    assert rows[1]["supersedes_id"] == one
    assert {r["created_by_kind"] for r in rows} == {"system"}
    assert {r["agent_run_id"] for r in rows} == {None}
    assert list(rows[1]["evidence_version_ids"]) == [first, second]
    actions = await firm.seed.actions(firm.tenant_id)
    assert actions.count("screening.completed") == 2
    for privilege in ("UPDATE", "DELETE"):
        assert not await firm.seed.value(
            "SELECT has_table_privilege('abacus_app', 'screening_results', $1)", privilege
        )


async def test_ac21_an_agent_or_a_person_never_writes_an_aggregate(firm: Firm) -> None:
    for kind in ("agent", "human"):
        actor = TenantContext(firm.tenant_id, kind, str(uuid.uuid4()))
        with pytest.raises(DBAPIError, match="composed by code"):
            async with tenant_session(actor) as session:
                await session.execute(
                    text(
                        "INSERT INTO screening_results (tenant_id, engagement_id, subject_kind, "
                        "request_item_id, batch_no, source_result_ids, "
                        "source_review_ids, evidence_version_ids, checks, file_flags, verdict, "
                        "citations, unverified) VALUES (:t, :e, 'request_batch', :i, "
                        "1, '{}', '{}', '{}', '[]', '[]', 'passed', '[]', '[]')"
                    ),
                    {"t": firm.tenant_id, "e": firm.site.engagement_id, "i": firm.site.item_id},
                )


async def test_ac21_a_version_row_keeps_every_0010_rule(firm: Firm) -> None:
    """The relaxed columns stay required on per-run rows (DEC-48 §4.2 (2), (4))."""
    run = await firm.run(firm.site.version_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.seed.run(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified, "
            "created_by_kind) VALUES ($1, $2, $3, $4, 'ready_for_review', NULL, 'x', '[]', "
            "'[]', 'agent')",
            firm.tenant_id,
            firm.site.engagement_id,
            firm.site.version_id,
            run,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.seed.run(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified, "
            "created_by_kind) VALUES ($1, $2, $3, $4, 'ready_for_review', 0.9, 'x', '[]', "
            "'[]', 'system')",
            firm.tenant_id,
            firm.site.engagement_id,
            firm.site.version_id,
            run,
        )


# --- AC-22: the rule; the period from code only -------------------------------------------------


async def test_ac22_a_verified_irrelevant_flag_flags_its_file_with_its_region(firm: Firm) -> None:
    good = [await firm.version(f"Invoice {n}.pdf") for n in range(2)]
    bad = await firm.version("Granite Rock Logistics - August statement.pdf")
    hidden = await firm.version("Invoice hidden flag.pdf")
    for version in [*good, bad, hidden]:
        await firm.dated(version, as_of=date(2026, 8, 3))
    for version in good:
        await firm.review(version)
    citation = await firm.review(bad, "irrelevant")
    await firm.review(hidden, "irrelevant", shown=False)  # no verified quote shown: no flag
    await firm.compose()
    card = await firm.card()
    assert card["verdict"] == "flagged"
    assert (card["files_total"], card["files_answering"]) == (4, 3)
    document = _check(card, "right_document")
    assert (document["verdict"], document["source"]) == ("flag", "model")
    assert document["citation_ids"] == [str(citation)]
    assert _check(card, "right_period")["verdict"] == "pass"
    assert card["file_flags"] == [
        {
            "evidence_version_id": str(bad),
            "file_name": "Granite Rock Logistics - August statement.pdf",
            "reason_code": "wrong_document",
            "region_ref": str(citation),
        }
    ]
    assert "confidence" not in json.dumps(card)
    assert card["provenance"]["prompt_ref"] == "evidence.upload_review@v3"  # pyright: ignore[reportIndexIssue] -- JSON
    assert "screening.feedback" in cast(list[str], card["allowed_actions"])


async def test_ac22_the_period_verdict_is_codes_alone(firm: Firm) -> None:
    last_year = await firm.version("Statement 2025.pdf")
    await firm.dated(last_year, as_of=date(2025, 8, 31))
    await firm.review(last_year)  # the reviewer saw nothing wrong
    await firm.compose()
    card = await firm.card()
    period = _check(card, "right_period")
    assert (period["verdict"], period["source"]) == ("flag", "code")
    assert _check(card, "right_document")["verdict"] == "pass"
    assert card["verdict"] == "flagged"
    assert [f["reason_code"] for f in cast(list[dict[str, object]], card["file_flags"])] == [
        "wrong_year"
    ]


async def test_ac22_two_passing_checks_pass_and_no_aggregate_path_decides(firm: Firm) -> None:
    version = await firm.version("July statement.pdf")
    await firm.dated(version, as_of=date(2026, 7, 31))
    await firm.review(version)
    status = await firm.seed.value(
        "SELECT status FROM request_items WHERE id = $1", firm.site.item_id
    )
    await firm.compose()
    rerun = await firm.net.call("POST", f"{firm.card_path}/rerun", firm.manager)
    assert rerun.status_code == 202, rerun.text
    card = await firm.card()
    assert card["verdict"] == "passed"
    assert (card["files_total"], card["files_answering"]) == (1, 1)
    assert (
        await firm.seed.value("SELECT status FROM request_items WHERE id = $1", firm.site.item_id)
        == status
    )
    assert not await firm.seed.value(
        "SELECT count(*) FROM review_decisions WHERE tenant_id = $1", firm.tenant_id
    )


async def test_ac22_without_any_run_the_card_is_not_screened(firm: Firm) -> None:
    card = await firm.card()
    assert card["verdict"] == "not_screened"
    assert card["screening_result_id"] is None
    assert [c["verdict"] for c in cast(list[dict[str, object]], card["checks"])] == [
        "not_run",
        "not_run",
    ]
    assert "screening.feedback" not in cast(list[str], card["allowed_actions"])


# --- AC-23: withdrawn versions are left out -----------------------------------------------------


async def test_ac23_a_withdrawn_version_leaves_the_card_and_the_next_aggregate(
    firm: Firm,
) -> None:
    kept = await firm.version("July statement.pdf")
    gone = await firm.version("Wrong file.pdf", detached=True)
    for version in (kept, gone):
        await firm.dated(version, as_of=date(2026, 7, 31))
    await firm.review(kept)
    await firm.review(gone, "irrelevant")
    await firm.compose()
    assert (await firm.card())["verdict"] == "flagged"
    client = TenantContext(firm.tenant_id, "human", str(firm.client.user_id))
    async with uow(client) as tx:  # the withdrawal is the client's own (0144's guard)
        await tx.session.execute(
            text(
                "INSERT INTO evidence_withdrawals (tenant_id, evidence_version_id, "
                "engagement_id, request_item_id, withdrawn_by_user_id, withdrawn_at, "
                "erase_after) VALUES (:t, :v, :e, :i, :u, clock_timestamp(), "
                "clock_timestamp() + interval '30 days')"
            ),
            {
                "t": firm.tenant_id,
                "v": gone,
                "e": firm.site.engagement_id,
                "i": firm.site.item_id,
                "u": firm.client.user_id,
            },
        )
        tx.record("evidence_version.withdrawn", target=Target("evidence_version", gone))
    stale = await firm.card()  # before code recomposes: never a verdict about the withdrawn file
    assert str(gone) not in json.dumps(stale)
    assert stale["verdict"] == "not_screened"
    assert stale["files_total"] == 1
    await on_version_withdrawn(
        OutboxEvent(
            uuid.uuid4(),
            firm.tenant_id,
            "evidence_version.withdrawn",
            {"evidence_version_id": str(gone), "request_item_id": str(firm.site.item_id)},
        )
    )
    rows = await firm.aggregates()
    assert list(rows[-1]["evidence_version_ids"]) == [kept]
    assert (await firm.card())["verdict"] == "passed"


# --- AC-24: who reads the card -------------------------------------------------------------------


async def test_ac24_the_card_is_a_firm_read_behind_its_flag(firm: Firm) -> None:
    client = await firm.net.call("GET", firm.card_path, firm.client)
    assert client.status_code in (403, 404), client.text
    await firm.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'screening.card'",
        firm.tenant_id,
    )
    forget_flags()
    off = await firm.net.call("GET", firm.card_path, firm.manager)
    assert off.status_code == 404, off.text


# --- AC-25: rerun --------------------------------------------------------------------------------


async def test_ac25_rerun_answers_409_while_a_review_runs_and_recomposes_otherwise(
    firm: Firm,
) -> None:
    version = await firm.version("July statement.pdf")
    await firm.dated(version, as_of=date(2026, 7, 31))
    running = await firm.run(version, "running")
    busy = await firm.net.call("POST", f"{firm.card_path}/rerun", firm.manager)
    assert busy.status_code == 409, busy.text
    assert busy.json()["detail"] == "screening_running"
    assert (await firm.card())["running"] is True
    await firm.seed.run(
        "UPDATE agent_runs SET status = 'failed', failure_code = 'test', "
        "finished_at = clock_timestamp() WHERE id = $1",
        running,
    )
    done = await firm.net.call("POST", f"{firm.card_path}/rerun", firm.manager)
    assert done.status_code == 202, done.text
    assert done.json()["running"] is False  # no real model route here: nothing starts
    assert (await firm.card())["files_total"] == 1
    assert "screening.rerun_requested" in await firm.seed.actions(firm.tenant_id)


async def test_ac25_rerun_starts_only_files_without_a_current_review(
    firm: Firm, reviews: list[ScreeningInput], monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed = await firm.version("Reviewed.pdf")
    fresh = await firm.version("New.pdf")
    await firm.review(reviewed)

    def current_spec(_agent: str) -> SimpleNamespace:
        return SimpleNamespace(prompt="evidence.upload_review@v3")  # the seeded reviews' prompt

    monkeypatch.setattr(screening_card, "spec", current_spec)
    response = await firm.net.call("POST", f"{firm.card_path}/rerun", firm.manager)
    assert response.status_code == 202, response.text
    assert response.json()["running"] is True
    assert [r.evidence_version_id for r in reviews] == [str(fresh)]


# --- AC-26: feedback -----------------------------------------------------------------------------


async def test_ac26_feedback_is_a_persons_insert_only_row_on_an_aggregate(firm: Firm) -> None:
    version = await firm.version("July statement.pdf")
    await firm.dated(version, as_of=date(2026, 7, 31))
    result = await firm.compose()
    path = f"/v1/screenings/{result}/feedback"
    bare = await firm.net.call("POST", path, firm.manager, body={"thumb": "down"})
    assert bare.status_code == 422, bare.text
    given = await firm.net.call(
        "POST",
        path,
        firm.manager,
        body={"thumb": "down", "reason_code": "wrong_request_match", "note": "Ask for the bill"},
    )
    assert given.status_code == 201, given.text
    assert given.json()["reason_code"] == "wrong_request_match"
    card = await firm.card()
    assert card["my_feedback"]["reason_code"] == "wrong_request_match"  # pyright: ignore[reportIndexIssue] -- JSON
    row = (
        await firm.seed.rows(
            "SELECT user_id, note_sealed FROM screening_feedback WHERE screening_result_id = $1",
            result,
        )
    )[0]
    assert row["user_id"] == firm.manager.user_id
    assert b"Ask for the bill" not in bytes(row["note_sealed"])  # sealed
    assert "screening.feedback_sent" in await firm.seed.actions(firm.tenant_id)
    for privilege in ("UPDATE", "DELETE"):
        assert not await firm.seed.value(
            "SELECT has_table_privilege('abacus_app', 'screening_feedback', $1)", privilege
        )
    run = await firm.run(version)
    per_run = await firm.seed.value(
        "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
        "agent_run_id, action, confidence, rationale, citations, unverified) VALUES ($1, $2, "
        "$3, $4, 'ready_for_review', 0.9, 'Fine', '[]', '[]') RETURNING id",
        firm.tenant_id,
        firm.site.engagement_id,
        version,
        run,
    )
    other = await firm.net.call(
        "POST", f"/v1/screenings/{per_run}/feedback", firm.manager, body={"thumb": "up"}
    )
    assert other.status_code == 404, other.text
    client = await firm.net.call("POST", path, firm.client, body={"thumb": "up"})
    assert client.status_code in (403, 404), client.text


# --- AC-27: tax-return information fails closed --------------------------------------------------


async def _tax_return_item(firm: Firm) -> uuid.UUID:
    work_item = await firm.seed.value(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
        "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', 'Feld 2025 return', $5) "
        "RETURNING id",
        firm.tenant_id,
        firm.site.engagement_id,
        firm.site.client_id,
        firm.site.entity_id,
        firm.owner.user_id,
    )
    binder = await firm.seed.value(
        "INSERT INTO request_lists (tenant_id, engagement_id, work_item_id) "
        "VALUES ($1, $2, $3) RETURNING id",
        firm.tenant_id,
        firm.site.engagement_id,
        work_item,
    )
    return cast(
        uuid.UUID,
        await firm.seed.value(
            "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
            "audit_area, created_by) VALUES ($1, $2, $3, 'Form W-2', 'Income', $4) RETURNING id",
            firm.tenant_id,
            firm.site.engagement_id,
            binder,
            firm.owner.user_id,
        ),
    )


async def test_ac27_a_tax_return_upload_at_a_real_firm_reaches_no_model(
    firm: Firm, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = await _tax_return_item(firm)
    version = await firm.version("1099-NEC.pdf", item)
    await firm.dated(version, period_check="passed")
    await firm.review(version, "irrelevant")  # an earlier review, before the gate
    monkeypatch.setattr(upload_review, "model_available", lambda: True)
    assert (
        await create_review_run(firm.tenant_id, version, uuid.uuid4(), firm.manager.user_id)
        is None
    )
    await compose_for_item(firm.tenant_id, item)
    rows = await firm.aggregates()
    checks = {c["key"]: c for c in json.loads(rows[-1]["checks"])}
    assert checks["right_document"]["verdict"] == "not_run"  # no model output used
    assert checks["right_period"]["verdict"] == "pass"  # code checks still run
    assert rows[-1]["verdict"] == "not_screened"
    assert list(rows[-1]["source_review_ids"]) == []
    await firm.seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", firm.tenant_id)
    await compose_for_item(firm.tenant_id, item)
    synthetic = await firm.aggregates()
    assert synthetic[-1]["verdict"] == "flagged"  # a synthetic firm's model output is used


# --- AC-28: a review decision names a per-version result only ------------------------------------


async def test_ac28_a_review_decision_cannot_name_an_aggregate(firm: Firm) -> None:
    version = await firm.version("July statement.pdf")
    result = await firm.compose()
    person = TenantContext(firm.tenant_id, "human", str(firm.manager.user_id))
    with pytest.raises(DBAPIError, match="per-version"):
        async with tenant_session(person) as session:
            await session.execute(
                text(
                    "INSERT INTO review_decisions (tenant_id, engagement_id, "
                    "evidence_version_id, request_item_id, decision, screening_result_id, "
                    "corrects_proposal, actor_kind, actor_id) VALUES (:t, :e, :v, :i, "
                    "'accept', :r, false, 'human', :a)"
                ),
                {
                    "t": firm.tenant_id,
                    "e": firm.site.engagement_id,
                    "v": version,
                    "i": firm.site.item_id,
                    "r": result,
                    "a": str(firm.manager.user_id),
                },
            )


# --- Security review (DEC-324): rerun authority, repeats, guards ---------------------------------


@pytest.fixture
def reviews(monkeypatch: pytest.MonkeyPatch) -> list[ScreeningInput]:
    """A real reviewer route is enabled and the firm's reviewer is on; dispatches are recorded."""
    started: list[ScreeningInput] = []

    async def dispatch(given: ScreeningInput, *, again: bool = False) -> None:
        started.append(given)

    async def enabled(_tenant_id: uuid.UUID) -> bool:
        return True

    monkeypatch.setattr(screening_card, "model_available", lambda: True)
    monkeypatch.setattr(screening_card, "review_enabled", enabled)
    monkeypatch.setattr(screening_card, "dispatch_review", dispatch)
    return started


async def test_sec1_staff_may_rerun_the_code_checks_but_start_no_review(
    firm: Firm, reviews: list[ScreeningInput], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(screening_card, "RERUN_WINDOW_SECONDS", 0)  # two people, back to back
    staff = await firm.seed.person(firm.tenant_id)
    await firm.seed.member(
        firm.site, staff, "staff"
    )  # screening.request, not upload_review.request
    version = await firm.version("July statement.pdf")
    response = await firm.net.call("POST", f"{firm.card_path}/rerun", staff)
    assert response.status_code == 202, response.text
    assert response.json()["running"] is False
    assert reviews == []
    assert (await firm.card())["files_total"] == 1  # the code part still recomposed
    manager = await firm.net.call("POST", f"{firm.card_path}/rerun", firm.manager)
    assert manager.status_code == 202, manager.text
    assert [r.evidence_version_id for r in reviews] == [str(version)]


async def test_sec1_a_firm_with_the_reviewer_off_starts_no_review(
    firm: Firm, reviews: list[ScreeningInput], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def disabled(_tenant_id: uuid.UUID) -> bool:
        return False

    monkeypatch.setattr(screening_card, "review_enabled", disabled)
    await firm.version("July statement.pdf")
    response = await firm.net.call("POST", f"{firm.card_path}/rerun", firm.manager)
    assert response.status_code == 202, response.text
    assert response.json()["running"] is False
    assert reviews == []


async def test_sec2_parallel_reruns_start_exactly_one_run(
    firm: Firm, reviews: list[ScreeningInput]
) -> None:
    version = await firm.version("July statement.pdf")
    answers = await asyncio.gather(
        *(firm.net.call("POST", f"{firm.card_path}/rerun", firm.manager) for _ in range(5))
    )
    assert sorted(a.status_code for a in answers) == [202, 409, 409, 409, 409]
    assert [a.json()["detail"] for a in answers if a.status_code == 409] == [
        "screening_running"
    ] * 4
    assert [r.evidence_version_id for r in reviews] == [str(version)]


async def test_sec2_a_repeated_rerun_names_the_same_source_event(
    firm: Firm, reviews: list[ScreeningInput], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(screening_card, "RERUN_WINDOW_SECONDS", 0)
    await firm.version("July statement.pdf")
    for _ in range(2):
        response = await firm.net.call("POST", f"{firm.card_path}/rerun", firm.manager)
        assert response.status_code == 202, response.text
    assert len(reviews) == 2
    assert reviews[0].event_id == reviews[1].event_id  # one workflow, one run per event


async def test_sec4_the_0154_trigger_functions_pin_their_search_path(firm: Firm) -> None:
    rows = await firm.seed.rows(
        "SELECT proname, proconfig FROM pg_proc WHERE proname = ANY($1::text[])",
        [
            "screening_results_batch_guard",
            "review_decisions_screening_kind",
            "screening_feedback_guard",
            "screening_rerun_requests_guard",
        ],
    )
    assert len(rows) == 4
    for row in rows:
        assert list(row["proconfig"] or []) == ["search_path=pg_catalog, public, pg_temp"], row


@pytest.mark.parametrize("kind", ["human", "system"])
async def test_sec5_only_an_agent_context_writes_a_per_version_proposal(
    firm: Firm, kind: Literal["human", "system"]
) -> None:
    run = await firm.run(firm.site.version_id)
    actor = TenantContext(firm.tenant_id, kind, str(firm.manager.user_id))
    with pytest.raises(DBAPIError, match="proposed by an agent"):
        async with tenant_session(actor) as session:
            await session.execute(
                text(
                    "INSERT INTO screening_results (tenant_id, engagement_id, "
                    "evidence_version_id, agent_run_id, action, confidence, rationale, "
                    "citations, unverified) VALUES (:t, :e, :v, :r, 'ready_for_review', 0.9, "
                    "'Fine', '[]', '[]')"
                ),
                {
                    "t": firm.tenant_id,
                    "e": firm.site.engagement_id,
                    "v": firm.site.version_id,
                    "r": run,
                },
            )


# --- P-06-T22: the card names its request and expected period (DEC-351) --------------------------


async def test_p06t22_the_card_carries_the_request_title_and_its_period(firm: Firm) -> None:
    card = await firm.card()
    assert isinstance(card["request_title"], str) and card["request_title"] != ""
    assert (card["period_start"], card["period_end"]) == (JUNE_1.isoformat(), SEP_18.isoformat())
