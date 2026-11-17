"""Support, help and status (G-04-T10; SPEC-680 AC-44 to AC-56; SHL-05, PLT-01; DEC-5417; amber).

**Chat** (AC-44 to AC-48): one open thread per firm user (OWN: the caller reads and writes only
their own), created by the first message; bodies are `confidential` and never logged, audited by
value, put in a notification or shown to a model (AC-49). 30 messages per 10 minutes per user.
Staff read the queue and reply in the firm's context as the staff member (`support`,
`staff:<id>`); a reply bumps `last_staff_message_at`. Availability is computed from the
`support_hours` setting (content): online inside a weekly window, with the median first response
over the last 7 days when at least 5 samples exist, else offline with the next opening.

**Help** (AC-50, AC-51): published articles through the definer readers, grouped, with the
caller's screen context first ("Suggested"); search by full text. Blocks are structured (schema
v1), never HTML.

**Status** (AC-53, AC-54): the core components and the firm's installed integrations, each the
worse of the open global incident and the firm's own integration health (`register_firm_health`,
W-01 fills it), plus the firm's data region.

Incidents and help-article publication are global writes through owner functions granted to
`abacus_ops` (0947): the operator command `abacus_tools.platform_console` runs them (two-person
publish: approver is never the drafter). The console's routes for them answer 501 until an
ops-credentialed path exists (ADR-156 keeps those credentials out of the API and worker).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, time, timedelta
from statistics import median
from typing import Final, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, platform_transaction, tenant_session
from abacus.kernel.errors import DomainRateLimited, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Staff, authorise_staff, names_of
from abacus.modules.platform.console_contract import (
    QueueConversationDetailOut,
    QueueConversationOut,
    QueueConversationsOut,
    QueueMessageOut,
)
from abacus.modules.platform.support_contract import (
    AvailabilityOut,
    ConversationOut,
    FirmStatusOut,
    HelpArticleOut,
    HelpArticlesOut,
    HelpArticleSummaryOut,
    HelpBlockOut,
    HelpGroupOut,
    StatusComponentOut,
    SupportMessageOut,
)

RATE_LIMIT: Final = 30
RATE_WINDOW: Final = timedelta(minutes=10)
MIN_SAMPLES: Final = 5
SUGGESTED: Final = "suggested"
REPLY: Final = "platform_support.reply"
_DAYS: Final = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_SEVERITY: Final = {
    "outage": "outage",
    "degraded": "needs_attention",
    "maintenance": "maintenance",
}
_RANK: Final = {"operational": 0, "maintenance": 1, "needs_attention": 2, "outage": 3}


class SupportRateLimited(DomainRateLimited):
    code = "rate_limited"


# --- the firm-health slot (W-01) -----------------------------------------------------------------

FirmHealth = Callable[[TenantContext], Awaitable[Mapping[str, str]]]
_HEALTH: list[FirmHealth] = []


def register_firm_health(source: FirmHealth) -> None:
    """W-01: the firm's installed integrations by key, each `operational` or `needs_attention`."""
    if source not in _HEALTH:
        _HEALTH.append(source)


# --- availability --------------------------------------------------------------------------------


def _open_windows(hours: Mapping[str, object], on: datetime) -> list[tuple[datetime, datetime]]:
    """The day's open windows in the hours' zone (`{"tz": .., "weekly": {"mon": [["08:00",
    "18:00"]], ..}}`)."""
    weekly = cast("Mapping[str, list[list[str]]]", hours.get("weekly") or {})
    out: list[tuple[datetime, datetime]] = []
    for start, end in weekly.get(_DAYS[on.weekday()], []):
        a, b = time.fromisoformat(start), time.fromisoformat(end)
        out.append(
            (on.replace(hour=a.hour, minute=a.minute, second=0, microsecond=0),
             on.replace(hour=b.hour, minute=b.minute, second=0, microsecond=0))
        )  # fmt: skip
    return out


def availability(
    hours: Mapping[str, object] | None, at: datetime, first_responses: Sequence[float]
) -> tuple[bool, int | None, datetime | None]:
    """(online, replies in minutes, next opening). No hours on file reads offline, no opening."""
    if not hours:
        return False, None, None
    zone = ZoneInfo(str(hours.get("tz") or "America/Chicago"))
    local = at.astimezone(zone)
    online = any(a <= local < b for a, b in _open_windows(hours, local))
    if online:
        minutes = round(median(first_responses)) if len(first_responses) >= MIN_SAMPLES else None
        return True, minutes, None
    for day in range(8):
        on = local + timedelta(days=day)
        for a, _ in sorted(_open_windows(hours, on)):
            if a > local:
                return False, None, a
    return False, None, None


async def _hours() -> Mapping[str, object] | None:
    async with platform_transaction("system:support") as conn:
        row = (
            await conn.execute(text("SELECT value FROM platform_setting_get('support_hours')"))
        ).first()
    return None if row is None else cast("Mapping[str, object]", row[0])


_FIRST_RESPONSES: Final = text(
    "SELECT EXTRACT(EPOCH FROM (s.created_at - f.created_at)) / 60 AS minutes "
    "FROM support_messages f JOIN LATERAL (SELECT created_at FROM support_messages x "
    "WHERE x.conversation_id = f.conversation_id AND x.author_kind = 'staff' "
    "AND x.created_at > f.created_at ORDER BY x.created_at LIMIT 1) s ON true "
    "WHERE f.author_kind = 'firm_user' AND f.created_at > :since"
)


# --- the firm's conversation (OWN) ---------------------------------------------------------------

_MINE: Final = text(
    "SELECT id FROM support_conversations WHERE user_id = :u AND status = 'open' LIMIT 1"
)
_MESSAGES: Final = text(
    "SELECT id, author_kind, author_user_id, staff_subject, body, related_article_slug, "
    "created_at FROM support_messages WHERE conversation_id = :c ORDER BY created_at, id"
)


def _staff_label(subject: str | None) -> str:
    first = (subject or "").split("@")[0].split(".")[0].strip() or "Support"
    return f"{first.capitalize()} at Accrued Support"


async def _message_out(rows: Sequence[RowMapping]) -> list[SupportMessageOut]:
    people = await names_of(
        sorted({cast(UUID, r["author_user_id"]) for r in rows if r["author_user_id"]}, key=str)
    )
    return [
        SupportMessageOut(
            id=r["id"],
            author_kind=r["author_kind"],
            author_display_name=(
                people.get(cast(UUID, r["author_user_id"]), "")
                if r["author_kind"] == "firm_user"
                else _staff_label(cast("str | None", r["staff_subject"]))
            ),
            body=str(r["body"]),
            related_article_slug=r["related_article_slug"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


async def conversation(ctx: AuthContext) -> ConversationOut:
    """SHL-05: the caller's one open thread, with availability; none until the first message."""
    async with tenant_session(ctx.tenant) as session:
        conversation_id = await session.scalar(_MINE, {"u": ctx.user_id})
        rows = (
            list((await session.execute(_MESSAGES, {"c": conversation_id})).mappings())
            if conversation_id is not None
            else []
        )
        samples = [
            float(r[0])
            for r in await session.execute(
                _FIRST_RESPONSES, {"since": system_now() - timedelta(days=7)}
            )
        ]
    online, minutes, next_open = availability(await _hours(), system_now(), samples)
    return ConversationOut(
        id=conversation_id,
        availability=AvailabilityOut(
            online=online, replies_in_minutes=minutes, next_open_at=next_open, reply_email=None
        ),
        messages=await _message_out(rows),
        session_cards=[],
        suggestions=[],
    )


async def send(ctx: AuthContext, body: str) -> SupportMessageOut:
    """AC-46: 1 to 4,000 characters; 30 per 10 minutes per user; the thread opens on the first."""
    text_in = body.strip()
    async with uow(ctx.tenant) as tx:
        recent = await tx.session.scalar(
            text(
                "SELECT count(*) FROM support_messages WHERE author_user_id = :u "
                "AND created_at > :since"
            ),
            {"u": ctx.user_id, "since": system_now() - RATE_WINDOW},
        )
        if int(recent or 0) >= RATE_LIMIT:
            raise SupportRateLimited(
                facts={"limit": RATE_LIMIT, "retry_after": int(RATE_WINDOW.total_seconds())}
            )
        conversation_id = await tx.session.scalar(_MINE, {"u": ctx.user_id})
        if conversation_id is None:
            conversation_id = await tx.session.scalar(
                text(
                    "INSERT INTO support_conversations (tenant_id, user_id) VALUES (:t, :u) "
                    "RETURNING id"
                ),
                {"t": ctx.tenant_id, "u": ctx.user_id},
            )
            tx.record(
                "support_conversation.opened",
                target=Target("support_conversation", cast(UUID, conversation_id)),
            )
        made = (
            (
                await tx.session.execute(
                    text(
                        "INSERT INTO support_messages (tenant_id, conversation_id, author_kind, "
                        "author_user_id, body) VALUES (:t, :c, 'firm_user', :u, :b) "
                        "RETURNING id, author_kind, author_user_id, staff_subject, body, "
                        "related_article_slug, created_at"
                    ),
                    {"t": ctx.tenant_id, "c": conversation_id, "u": ctx.user_id, "b": text_in},
                )
            )
            .mappings()
            .one()
        )
        await tx.session.execute(
            text(
                "UPDATE support_conversations SET last_firm_message_at = abacus_now() "
                "WHERE id = :c"
            ),
            {"c": conversation_id},
        )
        # Identifiers and a length only: never the body (DEC-60).
        tx.record(
            "support_message.sent",
            target=Target("support_conversation", cast(UUID, conversation_id)),
            after=Ref(message=made["id"], length=len(text_in)),
        )
    return (await _message_out([made]))[0]


# --- help ----------------------------------------------------------------------------------------


def _group_label(key: str) -> str:
    return "Suggested" if key == SUGGESTED else key.replace("_", " ").capitalize()


def help_groups(rows: Sequence[RowMapping], context: str | None) -> list[HelpGroupOut]:
    """Articles grouped by `group_key`; with a screen context, its articles first as Suggested."""
    groups: dict[str, list[HelpArticleSummaryOut]] = {}
    for r in rows:
        key = (
            SUGGESTED
            if context is not None and context in (r["context_screen_ids"] or [])
            else str(r["group_key"])
        )
        groups.setdefault(key, []).append(
            HelpArticleSummaryOut(
                slug=r["slug"],
                title=r["title"],
                summary=r["summary"],
                group_key=str(r["group_key"]),
                read_minutes=int(r["read_minutes"]),
            )
        )
    order = sorted(groups, key=lambda k: (k != SUGGESTED, k))
    return [HelpGroupOut(key=k, label=_group_label(k), articles=groups[k]) for k in order]


async def help_articles(context: str | None, q: str | None) -> HelpArticlesOut:
    async with platform_transaction("system:help") as conn:
        rows = list(
            (
                await conn.execute(
                    text("SELECT * FROM help_article_search(:q)")
                    if q is not None
                    else text("SELECT * FROM help_article_list(:c)"),
                    {"q": q} if q is not None else {"c": context},
                )
            ).mappings()
        )
    return HelpArticlesOut(groups=help_groups(rows, None if q else context), query=q)


def blocks_of(body: object) -> list[HelpBlockOut]:
    """Schema v1 blocks; anything else is dropped (content is never HTML)."""
    out: list[HelpBlockOut] = []
    for raw in cast("list[object]", body if isinstance(body, list) else []):
        if not isinstance(raw, dict):
            continue
        block = cast("dict[str, object]", raw)
        try:
            out.append(HelpBlockOut.model_validate(block))
        except ValueError:
            continue
    return out


async def help_article(slug: str) -> HelpArticleOut:
    async with platform_transaction("system:help") as conn:
        row = (
            (await conn.execute(text("SELECT * FROM help_article_get(:s)"), {"s": slug}))
            .mappings()
            .first()
        )
    if row is None:
        raise NotFound("help_article")
    return HelpArticleOut(
        slug=row["slug"],
        version=int(row["version"]),
        title=row["title"],
        read_minutes=int(row["read_minutes"]),
        blocks=blocks_of(row["body"]),
        published_at=row["published_at"],
    )


# --- status --------------------------------------------------------------------------------------


def worse(a: str, b: str) -> str:
    return a if _RANK[a] >= _RANK[b] else b


async def firm_status(ctx: AuthContext) -> FirmStatusOut:
    """AC-53, AC-54: core components and the firm's installed integrations."""
    async with platform_transaction("system:status") as conn:
        rows = list((await conn.execute(text("SELECT * FROM status_snapshot()"))).mappings())
        region = (
            await conn.execute(
                text(
                    "SELECT r.label FROM platform_regions_list() r "
                    "WHERE r.code = coalesce((SELECT d.region FROM "
                    "platform_directory_get(:t) d), 'us')"
                ),
                {"t": ctx.tenant_id},
            )
        ).scalar()
    own: dict[str, str] = {}
    for source in _HEALTH:
        for key, state in (await source(ctx.tenant)).items():
            own[key] = worse(own.get(key, "operational"), state)
    out: list[StatusComponentOut] = []
    for r in rows:
        if r["kind"] == "integration" and r["integration_key"] not in own:
            continue  # only the firm's own installs
        state = (
            _SEVERITY.get(str(r["severity"]), "operational") if r["severity"] else "operational"
        )
        if r["kind"] == "integration":
            state = worse(state, own.get(str(r["integration_key"]), "operational"))
        out.append(
            StatusComponentOut(
                key=r["key"],
                label=r["label"],
                kind=r["kind"],
                state=state,  # type: ignore[arg-type] -- one of ComponentState
                note=r["public_note"],
            )
        )
    return FirmStatusOut(components=out, region_label=str(region or "US"), history_url="/status")


# --- the staff queue (AC-47) ---------------------------------------------------------------------

_QUEUE: Final = text(
    "SELECT id, user_id, last_firm_message_at, last_staff_message_at, assigned_staff_subject "
    "FROM support_conversations WHERE status = 'open' "
    "ORDER BY last_firm_message_at DESC NULLS LAST"
)


async def _tenants(staff: Staff) -> list[RowMapping]:
    async with platform_transaction(f"staff:{staff.id}") as conn:
        return list(
            (
                await conn.execute(text("SELECT * FROM platform_directory_list(NULL, NULL, NULL)"))
            ).mappings()
        )


def _reader(tenant_id: UUID, staff: Staff) -> TenantContext:
    return TenantContext(tenant_id, "support", f"staff:{staff.id}")


async def conversations(staff: Staff) -> QueueConversationsOut:
    authorise_staff(REPLY, roles=staff.platform_roles, mfa_at=staff.mfa_at, staff_id=staff.id)
    items: list[QueueConversationOut] = []
    for d in await _tenants(staff):
        tenant_id = cast(UUID, d["tenant_id"])
        async with tenant_session(_reader(tenant_id, staff)) as session:
            rows = list((await session.execute(_QUEUE)).mappings())
        owners = await names_of(sorted({cast(UUID, r["user_id"]) for r in rows}, key=str))
        for r in rows:
            firm, ours = r["last_firm_message_at"], r["last_staff_message_at"]
            items.append(
                QueueConversationOut(
                    id=r["id"],
                    tenant_code=str(d["tenant_code"]),
                    firm_display_name=str(d["display_name"]),
                    owner_display_name=owners.get(cast(UUID, r["user_id"]), ""),
                    last_firm_message_at=firm,
                    last_staff_message_at=ours,
                    unanswered=firm is not None and (ours is None or ours < firm),
                    assigned_to=r["assigned_staff_subject"],
                )
            )
    counts = {
        "open": len(items),
        "unanswered": sum(1 for i in items if i.unanswered),
    }
    return QueueConversationsOut(items=items, counts=counts)


async def _locate(staff: Staff, conversation_id: UUID) -> tuple[RowMapping, UUID]:
    for d in await _tenants(staff):
        tenant_id = cast(UUID, d["tenant_id"])
        async with tenant_session(_reader(tenant_id, staff)) as session:
            found = await session.scalar(
                text("SELECT 1 FROM support_conversations WHERE id = :c"), {"c": conversation_id}
            )
        if found:
            return d, tenant_id
    raise NotFound("support_conversation")


async def detail(staff: Staff, conversation_id: UUID) -> QueueConversationDetailOut:
    authorise_staff(REPLY, roles=staff.platform_roles, mfa_at=staff.mfa_at, staff_id=staff.id)
    d, tenant_id = await _locate(staff, conversation_id)
    listed = next((i for i in (await conversations(staff)).items if i.id == conversation_id), None)
    async with tenant_session(_reader(tenant_id, staff)) as session:
        rows = list((await session.execute(_MESSAGES, {"c": conversation_id})).mappings())
    messages = await _message_out(rows)
    del d
    if listed is None:
        raise NotFound("support_conversation")
    return QueueConversationDetailOut(
        conversation=listed,
        messages=[
            QueueMessageOut(
                id=m.id,
                author_kind=m.author_kind,
                author_display_name=m.author_display_name,
                body=m.body,
                related_article_slug=m.related_article_slug,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


async def reply(
    staff: Staff, conversation_id: UUID, body: str, related_article_slug: str | None
) -> QueueMessageOut:
    """A staff reply in the firm's context as the staff member; bodies never leave the thread."""
    authorise_staff(REPLY, roles=staff.platform_roles, mfa_at=staff.mfa_at, staff_id=staff.id)
    _, tenant_id = await _locate(staff, conversation_id)
    async with uow(_reader(tenant_id, staff)) as tx:
        made = await tx.session.scalar(
            text(
                "INSERT INTO support_messages (tenant_id, conversation_id, author_kind, "
                "staff_subject, body, related_article_slug) VALUES (:t, :c, 'staff', :s, :b, "
                ":slug) RETURNING id"
            ),
            {"t": tenant_id, "c": conversation_id, "s": staff.subject[:200], "b": body.strip(),
             "slug": related_article_slug},
        )  # fmt: skip
        await tx.session.execute(
            text(
                "UPDATE support_conversations SET last_staff_message_at = abacus_now(), "
                "assigned_staff_subject = coalesce(assigned_staff_subject, :s) WHERE id = :c"
            ),
            {"s": staff.subject[:200], "c": conversation_id},
        )
        tx.record(
            "support_message.replied",
            target=Target("support_conversation", conversation_id),
            after=Ref(message=made, length=len(body.strip())),
        )
    found = await detail(staff, conversation_id)
    return next(m for m in found.messages if m.id == made)


__all__ = [
    "availability",
    "blocks_of",
    "conversation",
    "detail",
    "firm_status",
    "help_article",
    "help_articles",
    "help_groups",
    "conversations",
    "register_firm_health",
    "reply",
    "send",
    "worse",
]
