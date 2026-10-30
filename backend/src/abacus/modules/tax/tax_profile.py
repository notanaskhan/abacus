"""CLI-05's tax profile, tax's half (T-01-T43; T-01 §3.6, §4.2, §4.3; DEC-1651). RED.

Organisations owns the routes and their order of checks (`organisations.tax_profile`); every
function here is called after `live_entity` authorised the caller on the entity's client and the
`clients.tax_profile` flag is on. This module owns the records (migration 0550):

- **Authorizations** (8821, 2848, state): added on file with the scanned form (filed under Signed
  authorizations) and each designee's CAF number sealed with `kernel.crypto`; only the last four
  digits ever leave (`caf_last4`). Drafting an 8821 or 2848 through C7 waits for the firm's form
  templates on P-11's renderer (the request route stays a stub).
- **Elections**: one per entity, kind, jurisdiction and year, upserted with `seen_version`.
- **Transcripts**: a file the person staged (scanned before storage) is filed as `retrieved`
  evidence under Source documents, read as text (a PDF through the isolated extractor) and parsed
  by `compute.transcripts` (T-01-T45). A transcript cites an authorization on file for its entity's
  client that covers its year. Parse problems are stored as line numbers and codes, never text.
- **Comparisons**: against the return as filed, which is the return's latest approved engine
  import (`review.api.approved_values`, cause `engine_import`); its information returns are the
  fields `ir.<form>.<n>.payer` and `ir.<form>.<n>.amount` (DEC-1651). Code computes (ADR-050); the
  agent never runs this and writes no note in production.

Every write is one unit of work with its audit event (ids and counts only, never a figure, a
payer name or a CAF number: they are TRI or Restricted).
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final, Literal, cast
from uuid import UUID, uuid4

from abacus.kernel.clock import now
from abacus.kernel.crypto import seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.evidence.api import (
    file_retrieved_copy,
    file_signed_copy,
    pdf_text,
    read_staged,
    screen_and_stage,
)
from abacus.modules.identity.api import AuthContext, authorise, is_active_member, names_of
from abacus.modules.organisations.api import (
    AgreeingFormOut,
    AuthorizationForm,
    AuthorizationStatus,
    TaxAuthorizationDesigneeOut,
    TaxAuthorizationIn,
    TaxAuthorizationOut,
    TaxElectionIn,
    TaxElectionOut,
    TaxProfileBackend,
    TaxProfileFileOut,
    TranscriptComparisonIn,
    TranscriptComparisonOut,
    TranscriptLineDiffOut,
    TranscriptOut,
    TranscriptTransactionOut,
    TranscriptUploadIn,
    client_of_entity,
    register_tax_profile_backend,
)
from abacus.modules.review.api import approved_values
from abacus.modules.tax import tax_profile_repository as repo
from abacus.modules.tax.compute.transcripts import (
    COMPARE_VERSION,
    FiledItem,
    InformationReturn,
    LineStatus,
    ParsedTranscript,
    Problem,
    ProblemCode,
    TranscriptKind,
    parse_transcript,
)
from abacus.modules.tax.compute.transcripts import (
    compare as compare_transcript,
)

RowLike = Mapping[Any, Any]  # Any: a database row's or stored JSON's column values
ParseStatus = Literal["queued", "parsed", "failed"]
Result = Literal["agrees", "differences"]
RETURN_TARGET: Final = "tax_return"
ENGINE_IMPORT: Final = "engine_import"
TRANSCRIPT_SOURCE: Final = "irs_transcript"
# Information returns on the return as filed: `ir.<form slug>.<n>.payer|amount` (DEC-1651).
_FILED_KEY: Final = re.compile(
    r"^ir\.(?P<form>[a-z0-9_]{1,12})\.(?P<n>[0-9]{1,3})\.(?P<part>payer|amount)$"
)
_KIND_WORDS: Final[Mapping[str, str]] = {
    "wage_income": "Wage & Income transcript",
    "account": "Account transcript",
    "record_of_account": "Record of Account",
}
_KEY_CODES: Final = ("922", "150")  # the register shows the review first, else the filing


class TaxProfileStale(DomainConflict):
    code = "stale_version"


class TaxProfileFileUnavailable(DomainConflict):
    """The staged file is not the caller's own for this entity, or was already filed."""

    code = "tax_profile_file_unavailable"


class DesigneeNotMember(DomainInvalid):
    code = "designee_not_member"


class CafCountMismatch(DomainInvalid):
    """`designee_cafs`, when given, names one CAF number per designee, in the same order."""

    code = "caf_count_mismatch"


class AuthorizationNotOnFile(DomainConflict):
    """A transcript is pulled under an 8821 or 2848 on file for the client, covering its year."""

    code = "authorization_not_on_file"


class TranscriptNotComparable(DomainConflict):
    """Only a parsed Wage & Income transcript is compared with a return."""

    code = "transcript_not_comparable"


class ReturnMismatch(DomainConflict):
    """The return is not this client's for the transcript's tax year."""

    code = "return_mismatch"


class ReturnNotFiled(DomainConflict):
    """The return has no approved engine import yet: there is no return as filed to compare."""

    code = "return_not_filed"


# --- authorizations -----------------------------------------------------------------------------


def _authorization_out(row: RowLike, names: Mapping[UUID, str]) -> TaxAuthorizationOut:
    designees = [
        TaxAuthorizationDesigneeOut(
            user_id=UUID(str(d["user_id"])),
            name=names.get(UUID(str(d["user_id"])), ""),
            caf_last4=cast(str | None, d.get("caf_last4")),
        )
        for d in cast(list[dict[str, object]], row["designees"])
    ]
    return TaxAuthorizationOut(
        id=cast(UUID, row["id"]),
        form=cast(AuthorizationForm, row["form"]),
        state_form_code=cast(str | None, row["state_form_code"]),
        designees=designees,
        tax_matters=list(cast(list[str], row["tax_matters"])),
        tax_years=list(cast(list[int], row["tax_years"])),
        received_on=cast(date | None, row["received_on"]),
        expires_on=cast(date | None, row["expires_on"]),
        status=cast(AuthorizationStatus, row["status"]),
    )


async def _designee_names(rows: Sequence[RowLike]) -> dict[UUID, str]:
    ids = {
        UUID(str(d["user_id"]))
        for r in rows
        for d in cast(list[dict[str, object]], r["designees"])
    }
    return await names_of(sorted(ids)) if ids else {}


async def authorizations(ctx: AuthContext, entity_id: UUID) -> list[TaxAuthorizationOut]:
    async with tenant_session(ctx.tenant) as session:
        rows = await repo.authorizations(session, entity_id)
    names = await _designee_names(rows)
    return [_authorization_out(r, names) for r in rows]


async def add_authorization(
    ctx: AuthContext, entity_id: UUID, client_id: UUID, body: TaxAuthorizationIn
) -> TaxAuthorizationOut:
    """An authorization already on file: the scanned form filed under Signed authorizations, each
    designee a member of the firm, each CAF number sealed (last four kept)."""
    if body.designee_cafs is not None and len(body.designee_cafs) != len(body.designee_user_ids):
        raise CafCountMismatch(facts={"designees": len(body.designee_user_ids)})
    if body.form == "state" and body.state_form_code is None:
        raise DomainInvalid(facts={"field": "state_form_code"})
    for user_id in body.designee_user_ids:
        if not await is_active_member(ctx.tenant_id, user_id):
            raise DesigneeNotMember(facts={"user_id": str(user_id)})
    authorization_id = uuid4()
    designees: list[dict[str, str | None]] = []
    for n, user_id in enumerate(body.designee_user_ids):
        caf = None if body.designee_cafs is None else body.designee_cafs[n].replace("-", "")
        sealed = (
            None
            if caf is None
            else base64.b64encode(
                await seal(ctx.tenant_id, caf.encode(), _caf_binding(authorization_id, user_id))
            ).decode()
        )
        digits = None if caf is None else caf.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        designees.append(
            {
                "user_id": str(user_id),
                "caf_sealed": sealed,
                "caf_last4": None if digits is None else digits[-4:],
            }
        )
    form_label = {"8821": "Form 8821", "2848": "Form 2848"}.get(body.form, body.state_form_code)
    async with uow(ctx.tenant) as tx:
        staged = await repo.own_file_for_update(
            tx.session, {"id": body.upload_id, "user": ctx.user_id, "entity": entity_id}
        )
        if staged is None:
            raise TaxProfileFileUnavailable(facts={"upload_id": str(body.upload_id)})
        version_id = await file_signed_copy(
            tx,
            tenant_id=ctx.tenant_id,
            client_id=client_id,
            engagement_id=None,
            work_item_id=None,
            title=f"{form_label} on file",
            stored_key=str(staged["storage_key"]),
            stored_version_id=str(staged["storage_version_id"]),
            sha256=str(staged["sha256"]),
            size_bytes=int(cast(int, staged["size_bytes"])),
            media_type=str(staged["media_type"]),
            actor_kind="human",
            actor_id=str(ctx.user_id),
        )
        await repo.insert_authorization(
            tx.session,
            {
                "id": authorization_id,
                "tenant": ctx.tenant_id,
                "entity": entity_id,
                "form": body.form,
                "state_form_code": body.state_form_code,
                "designees": json.dumps(designees),
                "tax_matters": list(body.tax_matters),
                "forms_covered": [],
                "tax_years": sorted(set(body.tax_years)),
                "received_on": body.received_on,
                "expires_on": body.expires_on,
                "status": "on_file",
                "evidence_version_id": version_id,
                "created_by": ctx.user_id,
            },
        )
        await repo.consume_file(tx.session, body.upload_id, authorization_id)
        tx.record(
            "tax_authorization.added",
            target=Target("tax_authorization", authorization_id),
            after=Ref(designees=len(designees), evidence_version_id=version_id),
            scope=Scope(client_id=client_id),
        )
    async with tenant_session(ctx.tenant) as session:
        rows = [
            r for r in await repo.authorizations(session, entity_id) if r["id"] == authorization_id
        ]
    return _authorization_out(rows[0], await _designee_names(rows))


def _caf_binding(authorization_id: UUID, user_id: UUID) -> str:
    return f"tax_authorization:{authorization_id}:{user_id}:caf"


# --- elections ----------------------------------------------------------------------------------


async def elections(ctx: AuthContext, entity_id: UUID) -> list[TaxElectionOut]:
    async with tenant_session(ctx.tenant) as session:
        rows = await repo.elections(session, entity_id)
    return [
        TaxElectionOut(
            kind=str(r["kind"]),
            jurisdiction=cast(str | None, r["jurisdiction"]),
            tax_year=int(cast(int, r["tax_year"])),
            amount=cast(Decimal | None, r["amount"]),
            status_code=str(r["status_code"]),
            row_version=int(cast(int, r["row_version"])),
        )
        for r in rows
    ]


async def put_election(
    ctx: AuthContext, entity_id: UUID, kind: str, body: TaxElectionIn
) -> TaxElectionOut:
    """Insert the election, or update it when `seen_version` is its current version."""
    client_id = await client_of_entity(ctx.tenant, entity_id)
    key = {
        "entity": entity_id,
        "kind": kind,
        "jurisdiction": body.jurisdiction,
        "tax_year": body.tax_year,
    }
    async with uow(ctx.tenant) as tx:
        found = await repo.election_for_update(tx.session, key)
        if found is None:
            version = await repo.insert_election(
                tx.session,
                {
                    **key,
                    "tenant": ctx.tenant_id,
                    "amount": body.amount,
                    "status_code": body.status_code,
                    "user": ctx.user_id,
                },
            )
        else:
            moved = (
                None
                if body.seen_version is None
                else await repo.update_election(
                    tx.session,
                    {
                        "id": found["id"],
                        "seen": body.seen_version,
                        "amount": body.amount,
                        "status_code": body.status_code,
                        "user": ctx.user_id,
                    },
                )
            )
            if moved is None:
                raise TaxProfileStale(facts={"row_version": int(cast(int, found["row_version"]))})
            version = moved
        tx.record(
            "tax_election.updated",
            target=Target("client_entity", entity_id),
            after=Ref(tax_year=body.tax_year, row_version=version),
            scope=Scope(client_id=client_id),
        )
    return TaxElectionOut(
        kind=kind,
        jurisdiction=body.jurisdiction,
        tax_year=body.tax_year,
        amount=body.amount,
        status_code=body.status_code,
        row_version=version,
    )


# --- files and transcripts ----------------------------------------------------------------------


async def stage_file(
    ctx: AuthContext, entity_id: UUID, file_name: str, content: bytes
) -> TaxProfileFileOut:
    """Scanned before storage, refused closed (SPEC-029 AC-1); the uploader's own until filed."""
    screened = await screen_and_stage(ctx.tenant_id, content, file_name, None)
    file_id = uuid4()
    async with uow(ctx.tenant) as tx:
        await repo.insert_file(
            tx.session,
            {
                "id": file_id,
                "tenant": ctx.tenant_id,
                "entity": entity_id,
                "user": ctx.user_id,
                "name": screened.file_name,
                "media": screened.media_type,
                "size": screened.stored.size,
                "sha": screened.sha256,
                "key": screened.stored.key,
                "version": screened.stored.version_id,
            },
        )
        tx.record(
            "tax_profile_file.staged",
            target=Target("tax_profile_file", file_id),
            after=Ref(sha256=screened.sha256, size=screened.stored.size),
        )
    return TaxProfileFileOut(
        upload_id=file_id,
        file_name=screened.file_name,
        media_type=screened.media_type,
        size_bytes=screened.stored.size,
    )


def line_rows(
    tenant_id: UUID, transcript_id: UUID, parsed: ParsedTranscript
) -> list[dict[str, object]]:
    info_rows: list[dict[str, object]] = [
        {
            "tenant": tenant_id,
            "transcript_id": transcript_id,
            "line_no": r.line_no,
            "form": r.form,
            "payer_name": r.payer_name,
            "amount": r.amount,
            "tc_code": None,
            "tc_date": None,
        }
        for r in parsed.information_returns
    ]
    tc_rows: list[dict[str, object]] = [
        {
            "tenant": tenant_id,
            "transcript_id": transcript_id,
            "line_no": t.line_no,
            "form": None,
            "payer_name": None,
            "amount": t.amount,
            "tc_code": t.code,
            "tc_date": t.posted_on,
        }
        for t in parsed.transactions
    ]
    return info_rows + tc_rows


async def upload_transcript(
    ctx: AuthContext, entity_id: UUID, client_id: UUID, body: TranscriptUploadIn
) -> TranscriptOut:
    """File the staged transcript as retrieved evidence, parse it by code and keep its lines."""
    async with tenant_session(ctx.tenant) as session:
        cited = await repo.authorization(session, body.authorization_id)
    covered = (
        cited is not None
        and cited["status"] == "on_file"
        and cited["form"] in ("8821", "2848")
        and body.tax_year in cast(list[int], cited["tax_years"])
        and await client_of_entity(ctx.tenant, cast(UUID, cited["client_entity_id"])) == client_id
    )
    if not covered:
        raise AuthorizationNotOnFile(facts={"authorization_id": str(body.authorization_id)})
    transcript_id = uuid4()
    pulled_at = await now(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        staged = await repo.own_file_for_update(
            tx.session, {"id": body.upload_id, "user": ctx.user_id, "entity": entity_id}
        )
        if staged is None:
            raise TaxProfileFileUnavailable(facts={"upload_id": str(body.upload_id)})
        content = await read_staged(
            ctx.tenant_id,
            str(staged["storage_key"]),
            str(staged["storage_version_id"]),
            str(staged["sha256"]),
            int(cast(int, staged["size_bytes"])),
        )
        text_ = await asyncio.to_thread(pdf_text, content, str(staged["media_type"]))
        parsed = _parse(text_, body.kind, body.tax_year)
        version_id = await file_retrieved_copy(
            tx,
            tenant_id=ctx.tenant_id,
            client_id=client_id,
            title=f"{_KIND_WORDS[body.kind]} TY{body.tax_year}",
            source=TRANSCRIPT_SOURCE,
            pulled_at=pulled_at,
            stored_key=str(staged["storage_key"]),
            stored_version_id=str(staged["storage_version_id"]),
            sha256=str(staged["sha256"]),
            size_bytes=int(cast(int, staged["size_bytes"])),
            media_type=str(staged["media_type"]),
            actor_id=str(ctx.user_id),
        )
        await repo.insert_transcript(
            tx.session,
            {
                "id": transcript_id,
                "tenant": ctx.tenant_id,
                "entity": entity_id,
                "kind": body.kind,
                "tax_year": body.tax_year,
                "pulled_at": pulled_at,
                "user": ctx.user_id,
                "authorization_id": body.authorization_id,
                "evidence_version_id": version_id,
                "file_id": body.upload_id,
                "parse_status": "parsed" if parsed.parsed else "failed",
                "problems": json.dumps(
                    [{"line_no": p.line_no, "code": p.code} for p in parsed.problems]
                ),
                "account_balance": parsed.account_balance,
            },
        )
        if parsed.parsed:
            await repo.insert_lines(tx.session, line_rows(ctx.tenant_id, transcript_id, parsed))
        await repo.consume_file(tx.session, body.upload_id, transcript_id)
        tx.record(
            "transcript.uploaded",
            target=Target("transcript", transcript_id),
            after=Ref(
                tax_year=body.tax_year,
                parsed=int(parsed.parsed),
                lines=len(parsed.information_returns) + len(parsed.transactions),
                evidence_version_id=version_id,
            ),
            scope=Scope(client_id=client_id),
        )
    (out,) = [t for t in await transcripts(ctx, entity_id) if t.id == transcript_id]
    return out


def _parse(text_: str | None, kind: TranscriptKind, tax_year: int) -> ParsedTranscript:
    """The parser's result, failed (with a problem) when the file had no readable text or the
    transcript is for another year than the person said."""
    if text_ is None:
        return ParsedTranscript(kind=kind, tax_year=None, problems=(_problem("unreadable_file"),))
    parsed = parse_transcript(text_, kind)
    if parsed.parsed and parsed.tax_year != tax_year:
        return ParsedTranscript(
            kind=kind,
            tax_year=None,
            problems=(*parsed.problems, _problem("tax_year_mismatch")),
        )
    return parsed


def _problem(code: ProblemCode) -> Problem:
    return Problem(0, code)


async def transcripts(ctx: AuthContext, entity_id: UUID) -> list[TranscriptOut]:
    async with tenant_session(ctx.tenant) as session:
        rows = await repo.transcripts(session, entity_id)
        ids = [cast(UUID, r["id"]) for r in rows]
        lines = await repo.lines(session, ids)
        latest = {r["transcript_id"]: r for r in await repo.latest_comparisons(session, ids)}
    names = await names_of(sorted({cast(UUID, r["pulled_by"]) for r in rows})) if rows else {}
    key: dict[UUID, TranscriptTransactionOut] = {}
    for code in reversed(_KEY_CODES):  # 922 wins over 150
        for line in lines:
            if line["tc_code"] == code:
                key[cast(UUID, line["transcript_id"])] = TranscriptTransactionOut(
                    code=code, posted_on=cast(date, line["tc_date"])
                )
    out: list[TranscriptOut] = []
    for r in rows:
        comparison = latest.get(r["id"])
        differing = (
            None
            if comparison is None
            else sum(
                1
                for x in cast(list[dict[str, object]], comparison["lines"])
                if x["status"] != "agrees"
            )
        )
        out.append(
            TranscriptOut(
                id=cast(UUID, r["id"]),
                kind=cast(TranscriptKind, r["kind"]),
                tax_year=int(cast(int, r["tax_year"])),
                pulled_at=cast(datetime, r["pulled_at"]),
                parse_status=cast(ParseStatus, r["parse_status"]),
                pulled_by_name=names.get(cast(UUID, r["pulled_by"])),
                authorization_form=cast(AuthorizationForm, r["authorization_form"]),
                result=None if comparison is None else cast(Result, comparison["result"]),
                difference_count=differing,
                key_transaction=key.get(cast(UUID, r["id"])),
                account_balance=cast(Decimal | None, r["account_balance"]),
            )
        )
    return out


async def transcript_entity(ctx: AuthContext, transcript_id: UUID) -> UUID | None:
    async with tenant_session(ctx.tenant) as session:
        return await repo.entity_of_transcript(session, transcript_id)


# --- comparisons --------------------------------------------------------------------------------


def _form_of_slug(slug: str) -> str:
    """`1099_int` → `1099-INT`, `w_2` → `W-2`."""
    return slug.upper().replace("_", "-")


def filed_items(values: Mapping[str, RowLike | None]) -> list[FiledItem]:
    """The return as filed's information returns from its fields (DEC-1651): each `ir.<form>.<n>`
    pair with a payer and a decimal amount, in form and number order; a pair missing either half
    is not an information return."""
    pairs: dict[tuple[str, int], dict[str, object]] = {}
    for field_key, value in values.items():
        match = _FILED_KEY.match(field_key)
        if match is None or value is None or value.get("v") is None:
            continue
        pairs.setdefault((match["form"], int(match["n"])), {})[match["part"]] = value.get("v")
    items: list[FiledItem] = []
    for (slug, _), parts in sorted(pairs.items()):
        if "payer" not in parts or "amount" not in parts:
            continue
        items.append(
            FiledItem(_form_of_slug(slug), str(parts["payer"]), Decimal(str(parts["amount"])))
        )
    return items


def _stored_parsed(row: RowLike, lines: Sequence[RowLike]) -> ParsedTranscript:
    """The transcript as stored: its information returns' compared amounts (no re-parse)."""
    returns = tuple(
        InformationReturn(
            line_no=int(cast(int, line["line_no"])),
            form=str(line["form"]),
            payer_name=cast(str | None, line["payer_name"]),
            amount=cast(Decimal | None, line["amount"]),
            fields=(),
        )
        for line in lines
        if line["form"] is not None
    )
    return ParsedTranscript(
        kind=cast(TranscriptKind, row["kind"]),
        tax_year=int(cast(int, row["tax_year"])),
        information_returns=returns,
    )


async def compare(
    ctx: AuthContext, transcript_id: UUID, body: TranscriptComparisonIn
) -> TranscriptComparisonOut:
    async with tenant_session(ctx.tenant) as session:
        row = await repo.transcript(session, transcript_id)
        filed_return = await repo.tax_return(session, body.return_id)
        lines = await repo.lines(session, [transcript_id])
    if row is None:
        raise NotFound("transcript")
    if row["kind"] != "wage_income" or row["parse_status"] != "parsed":
        raise TranscriptNotComparable(facts={"transcript_id": str(transcript_id)})
    entity_id = cast(UUID, row["client_entity_id"])
    client_id = await client_of_entity(ctx.tenant, entity_id)
    if (
        filed_return is None
        or filed_return["tax_year"] != row["tax_year"]
        or await client_of_entity(ctx.tenant, cast(UUID, filed_return["client_entity_id"]))
        != client_id
    ):
        raise ReturnMismatch(facts={"return_id": str(body.return_id)})
    # The return's own engagement: a wall on it answers 404, even for a caller who may read the
    # client's tax profile (INV-3; the return's figures are TRI).
    engagement = await engagement_resource_of(
        ctx.tenant, cast(UUID, filed_return["engagement_id"])
    )
    await authorise(ctx, "tax_return.read", replace(engagement, work_item_id=body.return_id))
    as_filed = await approved_values(ctx.tenant, RETURN_TARGET, body.return_id, ENGINE_IMPORT)
    if as_filed is None:
        raise ReturnNotFiled(facts={"return_id": str(body.return_id)})
    tax_year = int(cast(int, row["tax_year"]))
    result = compare_transcript(_stored_parsed(row, lines), filed_items(as_filed.values), tax_year)
    stored_lines = [
        {
            "line_no": line.line_no,
            "form": line.form,
            "payer_name": line.payer_name,
            "transcript_amount": str(line.transcript_amount),
            "return_amount": None if line.return_amount is None else str(line.return_amount),
            "difference": str(line.difference),
            "status": line.status,
        }
        for line in result.lines
    ]
    agreeing = [{"form": form, "count": count} for form, count in result.agreeing]
    comparison_id = uuid4()
    async with uow(ctx.tenant) as tx:
        computed_at = await repo.insert_comparison(
            tx.session,
            {
                "id": comparison_id,
                "tenant": ctx.tenant_id,
                "transcript_id": transcript_id,
                "return_id": body.return_id,
                "checkpoint_id": as_filed.checkpoint_id,
                "result": result.result,
                "difference_total": result.difference_total,
                "lines": json.dumps(stored_lines),
                "agreeing": json.dumps(agreeing),
                "engine_version": COMPARE_VERSION,
                "user": ctx.user_id,
            },
        )
        tx.record(
            "transcript.compared",
            target=Target("transcript", transcript_id),
            after=Ref(
                comparison_id=comparison_id,
                return_id=body.return_id,
                checkpoint_id=as_filed.checkpoint_id,
                differing=len(result.differing),
            ),
            scope=Scope(client_id=client_id),
        )
    return _comparison_out(
        {
            "id": comparison_id,
            "transcript_id": transcript_id,
            "return_id": body.return_id,
            "checkpoint_id": as_filed.checkpoint_id,
            "result": result.result,
            "difference_total": result.difference_total,
            "lines": stored_lines,
            "agreeing": agreeing,
            "engine_version": COMPARE_VERSION,
            "computed_at": computed_at,
        }
    )


def _decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _comparison_out(row: RowLike) -> TranscriptComparisonOut:
    lines = cast(list[dict[str, object]], row["lines"])
    return TranscriptComparisonOut(
        id=cast(UUID, row["id"]),
        transcript_id=cast(UUID, row["transcript_id"]),
        return_id=cast(UUID, row["return_id"]),
        lines=[
            TranscriptLineDiffOut(
                form=str(x["form"]),
                payer_name=cast(str | None, x["payer_name"]),
                transcript_amount=Decimal(str(x["transcript_amount"])),
                return_amount=_decimal(x["return_amount"]),
                matched=x["return_amount"] is not None,
                line_no=int(cast(int, x["line_no"])),
                difference=_decimal(x["difference"]),
                status=cast(LineStatus, x["status"]),
            )
            for x in lines
        ],
        result=cast(Result, row["result"]),
        difference_total=_decimal(row["difference_total"]),
        agreeing=[
            AgreeingFormOut(form=str(a["form"]), count=int(cast(int, a["count"])))
            for a in cast(list[dict[str, object]], row["agreeing"])
        ],
        checkpoint_id=cast(UUID | None, row["checkpoint_id"]),
        engine_version=cast(str | None, row["engine_version"]),
        computed_at=cast(datetime, row["computed_at"]),
    )


async def comparison(ctx: AuthContext, transcript_id: UUID) -> TranscriptComparisonOut:
    """The latest comparison; its return amounts are the return's, so the return's engagement
    is checked as `compare` checks it (a wall answers 404)."""
    async with tenant_session(ctx.tenant) as session:
        found = await repo.latest_comparisons(session, [transcript_id])
        filed_return = (
            await repo.tax_return(session, cast(UUID, found[0]["return_id"])) if found else None
        )
    if not found or filed_return is None:
        raise NotFound("transcript_comparison")
    await _read_return(ctx, filed_return)
    return _comparison_out(found[0])


async def _read_return(ctx: AuthContext, filed_return: RowLike) -> None:
    """`tax_return.read` on the return's own engagement (INV-3; the return's figures are TRI)."""
    engagement = await engagement_resource_of(
        ctx.tenant, cast(UUID, filed_return["engagement_id"])
    )
    work_item_id = cast(UUID, filed_return["work_item_id"])
    await authorise(ctx, "tax_return.read", replace(engagement, work_item_id=work_item_id))


def register() -> None:
    """Tax's half of CLI-05, registered with organisations at import."""
    register_tax_profile_backend(
        TaxProfileBackend(
            authorizations=authorizations,
            add_authorization=add_authorization,
            elections=elections,
            put_election=put_election,
            stage_file=stage_file,
            upload_transcript=upload_transcript,
            transcripts=transcripts,
            compare=compare,
            comparison=comparison,
            transcript_entity=transcript_entity,
        )
    )
