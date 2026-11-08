"""The representation letter (A-07-T24; TASK-6208; DEC-2808; A-07 F3; AU-C 580; G7).

The letter is composed from the firm's published C11 `representation_letter` template: the general
representations (the template body's paragraphs, 1 to 11) are locked; each specific one (12 to 15)
is a C11 clause keyed by its trigger and included when code finds the trigger's facts (a late
remittance found, certified investment information, going-concern doubt concluded, a related party
found). No wording lives here: a version stores which clauses are on, where each came from, the SUM
snapshot it attaches, and a person's edits (sealed) to a firm-editable paragraph.

- **Versions** are insert-only; every change (an include toggle, an edit) is a new working version.
  Only a clause is editable; a general representation answers 409 `paragraph_locked`. Edited text
  may carry no amount (no materiality figure in letter text; 422 `amount_in_letter`).
- **Approval** is the engagement partner's, human-only, with fresh MFA, on the version they saw
  (`seen_hash`); it locks that version.
- **Send** is refused until that approval exists (409 `letter_not_approved`); it records the letter
  dated as of the report date and hands the approved version to C7 under the partner's grant.
- **G7** on `envelope.completed`: the signature dated the report date records G7; any other date is
  `date_mismatch` and the screen offers Start re-date (a new version for the bring-down letter).

Nothing here is live until `audits.letters` (A-07-T33); A-07-T19's envelope source refuses sends
while the flag is off.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.engagements.api import assurance_item, get_ref
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.reporting.api import published_clauses
from abacus.modules.review.api import decided_cards

FAMILY: Final = "representation_letter"
GENERAL: Final = 11  # representations 1 to 11 are the template body's, locked
_AMOUNT: Final = re.compile(r"\$\s?\d|\d[\d,]*\.\d{2}\b|\b\d{1,3}(,\d{3})+\b")
Source = Literal["trigger", "person"]


class LetterInvalid(DomainInvalid):
    code = "representation_letter_invalid"


class AmountInLetter(DomainInvalid):
    """No amount (and so no materiality figure) in letter text (A-07 F3)."""

    code = "amount_in_letter"


class ParagraphLocked(DomainConflict):
    code = "paragraph_locked"


class LetterNotApproved(DomainConflict):
    """Send is refused before the engagement partner approves the version sent."""

    code = "letter_not_approved"


class StaleLetter(DomainConflict):
    code = "stale_version"


class NoTemplate(DomainConflict):
    code = "template_not_published"


# --- triggers ------------------------------------------------------------------------------------

type Trigger = Callable[[TenantContext, UUID], Awaitable[bool]]
_TRIGGERS: dict[str, Trigger] = {}


def register_rep_trigger(key: str, trigger: Trigger) -> None:
    found = _TRIGGERS.get(key)
    if found is not None and found is not trigger:
        raise ValueError(f"representation trigger {key!r} already registered")
    _TRIGGERS[key] = trigger


async def _scalar(tenant: TenantContext, sql: str, work_item_id: UUID) -> object:
    async with tenant_session(tenant) as session:
        return await session.scalar(text(sql), {"wi": work_item_id})


async def late_remittance(tenant: TenantContext, work_item_id: UUID) -> bool:
    return bool(
        await _scalar(
            tenant,
            "SELECT EXISTS (SELECT 1 FROM ebp_late_remittances WHERE work_item_id = :wi)",
            work_item_id,
        )
    )


async def certified_investments(tenant: TenantContext, work_item_id: UUID) -> bool:
    return (await assurance_item(tenant, work_item_id)).limited_scope_103a3c


async def related_party_found(tenant: TenantContext, work_item_id: UUID) -> bool:
    return bool(
        await _scalar(
            tenant,
            "SELECT EXISTS (SELECT 1 FROM related_parties WHERE work_item_id = :wi "
            "AND status IN ('evaluated', 'exception'))",
            work_item_id,
        )
    )


async def going_concern_doubt(tenant: TenantContext, work_item_id: UUID) -> bool:
    """The EP concluded substantial doubt (decided through C3; the option is the EP's)."""
    item = await assurance_item(tenant, work_item_id)
    card = await _scalar(
        tenant,
        "SELECT decision_card_id FROM going_concern_evaluations WHERE work_item_id = :wi",
        work_item_id,
    )
    if not isinstance(card, UUID):
        return False
    decided = await decided_cards(tenant, item.engagement_id)
    return any(c.card_id == card and c.option_key.startswith("doubt") for c in decided)


def register_rep_triggers() -> None:
    """Once, from `assurance.api`: the triggers assurance can read itself."""
    for key, trigger in (
        ("late_remittance", late_remittance),
        ("certified_investments", certified_investments),
        ("related_party_found", related_party_found),
        ("going_concern_doubt", going_concern_doubt),
    ):
        register_rep_trigger(key, trigger)


# --- composition ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Representation:
    n: int
    clause_id: str
    included: bool
    source: Source


def _canonical(
    template_version_id: UUID, reps: Sequence[Representation], sum_snapshot: UUID | None
) -> tuple[str, str]:
    body = json.dumps(
        {
            "template_version_id": str(template_version_id),
            "sum_snapshot_id": None if sum_snapshot is None else str(sum_snapshot),
            "representations": [
                {"n": r.n, "clause_id": r.clause_id, "included": r.included, "source": r.source}
                for r in reps
            ],
        },
        sort_keys=True,
    )
    return body, hashlib.sha256(body.encode()).hexdigest()


async def compose(
    tenant: TenantContext, work_item_id: UUID, clauses: Sequence[tuple[str, bool]]
) -> list[Representation]:
    """Each specific representation on when its trigger holds (a clause with no registered
    trigger keeps the template's default, so the firm's own clause is never dropped)."""
    out: list[Representation] = []
    for offset, (clause_id, default) in enumerate(clauses, start=1):
        trigger = _TRIGGERS.get(clause_id)
        on = default if trigger is None else await trigger(tenant, work_item_id)
        out.append(Representation(GENERAL + offset, clause_id, on, "trigger"))
    return out


_LATEST_SUM = text(
    "SELECT id FROM sum_snapshots WHERE work_item_id = :wi ORDER BY created_at DESC LIMIT 1"
)
_LETTER = text(
    "SELECT id, status, current_version_id, dated_as_of, version FROM representation_letters "
    "WHERE work_item_id = :wi FOR UPDATE"
)
_VERSION = text(
    "SELECT id, version_no, template_version_id, representations, sum_snapshot_id, content_hash, "
    "edited_paragraphs_sealed FROM representation_letter_versions WHERE id = :id"
)


async def _person(ctx: AuthContext, work_item_id: UUID, action: str) -> UUID:
    if ctx.client:
        raise NotFound("representation_letter")
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")
    item = await assurance_item(ctx.tenant, work_item_id)
    await authorise(ctx, action, (await get_ref(ctx, item.engagement_id)).resource())
    return item.engagement_id


async def _insert_version(
    tx: UnitOfWork,
    ctx: AuthContext,
    *,
    engagement_id: UUID,
    work_item_id: UUID,
    letter_id: UUID,
    template_version_id: UUID,
    reps: Sequence[Representation],
    sum_snapshot: UUID | None,
    edited: bytes | None,
) -> tuple[UUID, int, str]:
    body, digest = _canonical(template_version_id, reps, sum_snapshot)
    version_no = int(
        await tx.session.scalar(
            text(
                "SELECT coalesce(max(version_no), 0) + 1 FROM representation_letter_versions "
                "WHERE letter_id = :l"
            ),
            {"l": letter_id},
        )
        or 1
    )
    version_id = await tx.session.scalar(
        text(
            "INSERT INTO representation_letter_versions (tenant_id, engagement_id, work_item_id, "
            "letter_id, version_no, template_version_id, representations, "
            "edited_paragraphs_sealed, sum_snapshot_id, content_hash, created_by) VALUES (:t, :e, "
            ":wi, :l, :no, :tv, CAST(:reps AS jsonb), :edited, :sum, :hash, :by) RETURNING id"
        ),
        {
            "t": ctx.tenant_id,
            "e": engagement_id,
            "wi": work_item_id,
            "l": letter_id,
            "no": version_no,
            "tv": template_version_id,
            "reps": json.dumps(json.loads(body)["representations"]),
            "edited": edited,
            "sum": sum_snapshot,
            "hash": digest,
            "by": ctx.user_id,
        },
    )
    await tx.session.execute(
        text(
            "UPDATE representation_letters SET current_version_id = :v, status = 'draft', "
            "version = version + 1, updated_at = clock_timestamp() WHERE id = :l"
        ),
        {"v": version_id, "l": letter_id},
    )
    tx.record(
        "rep_letter.version_created",
        target=Target("representation_letter", letter_id),
        after=Ref(version_no=version_no, content_hash=digest),
        scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
    )
    return cast(UUID, version_id), version_no, digest


@dataclass(frozen=True)
class LetterVersion:
    letter_id: UUID
    version_id: UUID
    version_no: int
    content_hash: str
    representations: tuple[Representation, ...]


async def start_letter(ctx: AuthContext, work_item_id: UUID) -> LetterVersion:
    """Compose version 1 (or the next) from the published template and the facts."""
    engagement_id = await _person(ctx, work_item_id, "rep_letter.draft")
    template = await published_clauses(ctx.tenant, FAMILY)
    if template is None:
        raise NoTemplate(facts={"family": FAMILY})
    reps = await compose(ctx.tenant, work_item_id, template.clauses)
    async with tenant_session(ctx.tenant) as session:
        sum_snapshot = await session.scalar(_LATEST_SUM, {"wi": work_item_id})
    async with uow(ctx.tenant) as tx:
        letter = (await tx.session.execute(_LETTER, {"wi": work_item_id})).first()
        letter_id = (
            letter.id
            if letter is not None
            else await tx.session.scalar(
                text(
                    "INSERT INTO representation_letters (tenant_id, engagement_id, work_item_id, "
                    "template_id) VALUES (:t, :e, :wi, NULL) RETURNING id"
                ),
                {"t": ctx.tenant_id, "e": engagement_id, "wi": work_item_id},
            )
        )
        version_id, version_no, digest = await _insert_version(
            tx,
            ctx,
            engagement_id=engagement_id,
            work_item_id=work_item_id,
            letter_id=letter_id,
            template_version_id=template.version_id,
            reps=reps,
            sum_snapshot=sum_snapshot,
            edited=None,
        )
    return LetterVersion(letter_id, version_id, version_no, digest, tuple(reps))


def _reps(raw: object) -> list[Representation]:
    rows = cast("list[dict[str, object]]", raw if isinstance(raw, list) else json.loads(str(raw)))
    return [
        Representation(
            int(str(r["n"])), str(r["clause_id"]), bool(r["included"]), cast(Source, r["source"])
        )
        for r in rows
    ]


async def _current(tx: UnitOfWork, work_item_id: UUID) -> tuple[object, object]:
    letter = (await tx.session.execute(_LETTER, {"wi": work_item_id})).first()
    if letter is None or letter.current_version_id is None:
        raise NotFound("representation_letter")
    version = (await tx.session.execute(_VERSION, {"id": letter.current_version_id})).one()
    return letter, version


async def set_included(
    ctx: AuthContext, work_item_id: UUID, n: int, included: bool, seen_hash: str
) -> LetterVersion:
    """An include toggle is a new working version; a general representation is locked."""
    engagement_id = await _person(ctx, work_item_id, "rep_letter.draft")
    if n <= GENERAL:
        raise ParagraphLocked(facts={"n": n})
    async with uow(ctx.tenant) as tx:
        letter, version = await _current(tx, work_item_id)
        v = cast("_VersionRow", version)
        if v.content_hash != seen_hash:
            raise StaleLetter(facts={"seen_hash": seen_hash})
        reps = _reps(v.representations)
        if not any(r.n == n for r in reps):
            raise NotFound("representation")
        changed = [
            Representation(r.n, r.clause_id, included, "person") if r.n == n else r for r in reps
        ]
        version_id, version_no, digest = await _insert_version(
            tx,
            ctx,
            engagement_id=engagement_id,
            work_item_id=work_item_id,
            letter_id=cast("_LetterRow", letter).id,
            template_version_id=v.template_version_id,
            reps=changed,
            sum_snapshot=v.sum_snapshot_id,
            edited=v.edited_paragraphs_sealed,
        )
    return LetterVersion(
        cast("_LetterRow", letter).id, version_id, version_no, digest, tuple(changed)
    )


async def edit_paragraph(
    ctx: AuthContext, work_item_id: UUID, n: int, wording: str, seen_hash: str
) -> LetterVersion:
    """Edits only on a firm-editable paragraph (a clause), sealed; no amount in the text."""
    engagement_id = await _person(ctx, work_item_id, "rep_letter.draft")
    if n <= GENERAL:
        raise ParagraphLocked(facts={"n": n})
    if not wording.strip() or len(wording) > 2000:
        raise LetterInvalid(facts={"field": "text"})
    if _AMOUNT.search(wording):
        raise AmountInLetter(facts={"n": n})
    async with uow(ctx.tenant) as tx:
        letter, version = await _current(tx, work_item_id)
        v = cast("_VersionRow", version)
        if v.content_hash != seen_hash:
            raise StaleLetter(facts={"seen_hash": seen_hash})
        letter_id = cast("_LetterRow", letter).id
        edits = json.dumps({str(n): wording.strip()}, sort_keys=True)
        sealed = await seal(ctx.tenant_id, edits.encode(), f"representation_letter:{letter_id}")
        reps = _reps(v.representations)
        version_id, version_no, digest = await _insert_version(
            tx,
            ctx,
            engagement_id=engagement_id,
            work_item_id=work_item_id,
            letter_id=letter_id,
            template_version_id=v.template_version_id,
            reps=reps,
            sum_snapshot=v.sum_snapshot_id,
            edited=sealed,
        )
    return LetterVersion(letter_id, version_id, version_no, digest, tuple(reps))


async def request_approval(ctx: AuthContext, work_item_id: UUID) -> None:
    engagement_id = await _person(ctx, work_item_id, "rep_letter.request_approval")
    async with uow(ctx.tenant) as tx:
        letter, _version = await _current(tx, work_item_id)
        await tx.session.execute(
            text(
                "UPDATE representation_letters SET status = 'awaiting_partner_approval', "
                "version = version + 1, updated_at = clock_timestamp() WHERE id = :l"
            ),
            {"l": cast("_LetterRow", letter).id},
        )
        tx.record(
            "rep_letter.approval_requested",
            target=Target("representation_letter", cast("_LetterRow", letter).id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


async def approve(ctx: AuthContext, work_item_id: UUID, seen_hash: str) -> UUID:
    """The engagement partner's, human-only, fresh MFA (`rep_letter.approve`); locks the
    version they saw. Returns the approved version's id."""
    engagement_id = await _person(ctx, work_item_id, "rep_letter.approve")
    async with uow(ctx.tenant) as tx:
        letter, version = await _current(tx, work_item_id)
        v = cast("_VersionRow", version)
        if v.content_hash != seen_hash:
            raise StaleLetter(facts={"seen_hash": seen_hash})
        await tx.session.execute(
            text(
                "INSERT INTO representation_letter_approvals (tenant_id, engagement_id, "
                "work_item_id, version_id, approved_by, seen_hash, mfa_verified_at, actor_kind, "
                "actor_id) VALUES (:t, :e, :wi, :v, :by, :seen, clock_timestamp(), "
                "current_setting('app.actor_kind', true), current_setting('app.actor_id', true))"
            ),
            {
                "t": ctx.tenant_id,
                "e": engagement_id,
                "wi": work_item_id,
                "v": v.id,
                "by": ctx.user_id,
                "seen": seen_hash,
            },
        )
        await tx.session.execute(
            text(
                "UPDATE representation_letters SET status = 'approved', version = version + 1, "
                "updated_at = clock_timestamp() WHERE id = :l"
            ),
            {"l": cast("_LetterRow", letter).id},
        )
        tx.record(
            "rep_letter.approved",
            target=Target("representation_letter", cast("_LetterRow", letter).id),
            after=Ref(version=v.id, seen_hash=seen_hash),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return v.id


_APPROVED = text(
    "SELECT EXISTS (SELECT 1 FROM representation_letter_approvals WHERE version_id = :v)"
)


async def mark_sent(
    ctx: AuthContext, work_item_id: UUID, *, report_date: date, envelope_id: UUID
) -> None:
    """After C7 accepted the approved version (A-07-T33 wires the route to `create_draft` and
    the send under the partner's grant): the letter is dated as of the report date. Refused
    before the partner's approval of the current version."""
    engagement_id = await _person(ctx, work_item_id, "rep_letter.send")
    async with uow(ctx.tenant) as tx:
        letter, version = await _current(tx, work_item_id)
        v = cast("_VersionRow", version)
        if not bool(await tx.session.scalar(_APPROVED, {"v": v.id})):
            raise LetterNotApproved
        await tx.session.execute(
            text(
                "UPDATE representation_letters SET status = 'sent', envelope_id = :env, "
                "dated_as_of = :d, version = version + 1, updated_at = clock_timestamp() "
                "WHERE id = :l"
            ),
            {"env": envelope_id, "d": report_date, "l": cast("_LetterRow", letter).id},
        )
        tx.record(
            "rep_letter.sent",
            target=Target("representation_letter", cast("_LetterRow", letter).id),
            after=Ref(envelope=envelope_id, dated_as_of=report_date.isoformat()),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


async def ensure_approved(tenant: TenantContext, work_item_id: UUID) -> None:
    """The send's guard, for the route and C7's source check alike."""
    async with tenant_session(tenant) as session:
        letter = (
            await session.execute(
                text(
                    "SELECT current_version_id FROM representation_letters "
                    "WHERE work_item_id = :wi"
                ),
                {"wi": work_item_id},
            )
        ).first()
        approved = letter is not None and bool(
            await session.scalar(_APPROVED, {"v": letter.current_version_id})
        )
    if not approved:
        raise LetterNotApproved


@dataclass(frozen=True)
class G7Outcome:
    status: Literal["signed", "date_mismatch"]
    signed_on: date
    dated_as_of: date | None


def g7_outcome(signed_at: datetime, dated_as_of: date | None, firm_zone_date: date) -> G7Outcome:
    """Signed on the report date (in the firm's zone) meets G7; any other day is a mismatch,
    and the screen offers Start re-date. `firm_zone_date` is the signing instant's date in the
    firm's time zone (the caller converts)."""
    del signed_at
    if dated_as_of is not None and firm_zone_date == dated_as_of:
        return G7Outcome("signed", firm_zone_date, dated_as_of)
    return G7Outcome("date_mismatch", firm_zone_date, dated_as_of)


async def record_signature(
    tenant: TenantContext, envelope_id: UUID, signed_at: datetime, firm_zone_date: date
) -> G7Outcome:
    """`envelope.completed` for this letter's envelope: G7 or `date_mismatch` (system act on the
    envelope's completion; the signature is management's)."""
    async with uow(tenant) as tx:
        letter = (
            await tx.session.execute(
                text(
                    "SELECT id, engagement_id, work_item_id, dated_as_of FROM "
                    "representation_letters WHERE envelope_id = :env FOR UPDATE"
                ),
                {"env": envelope_id},
            )
        ).first()
        if letter is None:
            raise NotFound("representation_letter")
        outcome = g7_outcome(signed_at, letter.dated_as_of, firm_zone_date)
        await tx.session.execute(
            text(
                "UPDATE representation_letters SET status = :s, signed_on = :on, "
                "g7_met_at = CASE WHEN :s = 'signed' THEN clock_timestamp() ELSE NULL END, "
                "version = version + 1, updated_at = clock_timestamp() WHERE id = :l"
            ),
            {"s": outcome.status, "on": outcome.signed_on, "l": letter.id},
        )
        tx.record(
            "rep_letter.signed" if outcome.status == "signed" else "rep_letter.date_mismatch",
            target=Target("representation_letter", letter.id),
            after=Ref(signed_on=outcome.signed_on.isoformat()),
            scope=Scope(engagement_id=letter.engagement_id, work_item_id=letter.work_item_id),
        )
    return outcome


class _VersionRow:
    id: UUID
    version_no: int
    template_version_id: UUID
    representations: object
    sum_snapshot_id: UUID | None
    content_hash: str
    edited_paragraphs_sealed: bytes | None


class _LetterRow:
    id: UUID
    status: str
    current_version_id: UUID | None
    dated_as_of: date | None


__all__ = [
    "AmountInLetter",
    "G7Outcome",
    "LetterNotApproved",
    "LetterVersion",
    "ParagraphLocked",
    "Representation",
    "approve",
    "compose",
    "edit_paragraph",
    "ensure_approved",
    "g7_outcome",
    "mark_sent",
    "record_signature",
    "register_rep_trigger",
    "register_rep_triggers",
    "request_approval",
    "set_included",
    "start_letter",
]
