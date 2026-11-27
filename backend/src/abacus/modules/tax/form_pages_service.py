"""TAX-11's form pages (T-06-T44; TASK-8913; SPEC-702 F7; DEC-78; DEC-5915; amber).

The draft preview of a return's form, from the workbook's current approved checkpoint (or a named
one) and the firm's published `tax_form_face` template for the return's form and tax year (T-06-
T43). Every field's value is resolved by code from its binding and formatted for the face:

- `workbook_cell` (`06!C2`): the cell's value at the checkpoint;
- `tb_line` (`L1`, `K 1`, `M-2 9`): the net of sheet 03's mapped lines under that key, signed as
  the form prints it (credit-side lines negated); the Schedule L totals are code's sums of the
  reference set's sides (`L14` total assets, `L22` total liabilities and capital);
- `return_fact`: the entity's name and EIN (its last four, masked; none for an offshore reader;
  the full TIN never leaves the sealed store), the K-1 count, the profile's principal activity
  and business code, Analysis of Net Income (code's sum over 06 and 09 by partner kind), and
  what the approved engine summary carries (page one's lines, Schedule B's answers, items B and
  E). A fact no source carries prints blank, never a guess.

A TIN prints as `••-•••1234` (an EIN) or `•••-••-1234` (an SSN): the mask is burned into the
page, never a layer. Pages carry the "Draft — not for filing" watermark; nothing is filed or
transmitted from here. The PDF is drawn by C11's form-face renderer and is byte-stable for the
same checkpoint and template version (dates from the checkpoint, identifier from the content
hash); `form_page_renders` keeps one row per (checkpoint, template version, page) with its hash.

**Attached forms** (T-06-T49; DEC-6023): TAX-11's page list is the return's face pages, then its
attached forms in the handoff's order (`ATTACHED`: for a 1065, Form 8825, Form 4562, Schedule
M-3, Schedule C (M-3 filers) and Form 8916-A once total assets reach 10,000,000, the section 199A
statement, and the section 754 statement once an interest was transferred). Each attached form
is the firm's own published `tax_form_face` template for that form and year (content, loaded
through the import endpoint), its page and field keys prefixed with the form (`f8825_p1`). An
attached form with no published template is still listed, as a placeholder page with no fields:
TAX-11 shows the placeholder, never a blank; it is never rendered, cached or downloaded.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.tax.entity_depth_errors import FormTemplateMissing
from abacus.modules.tax.workbook_service import WORKBOOK

READ: Final = "form_preview.read"
DOWNLOAD: Final = "form_preview.download_draft"
ZERO: Final = Decimal(0)
Values = Mapping[str, Mapping[str, object] | None]


class CheckpointMissing(DomainConflict):
    """The return's workbook has no approved checkpoint to preview from."""

    code = "checkpoint_required"


@dataclass(frozen=True)
class Field:
    key: str
    page_key: str
    label: str
    box: tuple[float, float, float, float]
    format: str
    binding_kind: str
    binding_ref: str
    value: str | None


@dataclass(frozen=True)
class Attached:
    """One form TAX-11 lists after the face: its manifest form key, TAX-11's caption for its
    placeholder, and when the return carries it (`always`, `m3`: total assets reach M-3's
    threshold, `transfer`: an interest was transferred this year)."""

    form: str
    caption: str
    when: str = "always"

    @property
    def prefix(self) -> str:
        return "f" + self.form.replace("-", "_").replace(".", "_") + "_"


# The handoff's order (TAX-11 spec a: "Form 8825" · "Form 4562" · "Sch. M-3" · "Sch. C (M-3
# filers)" · "Form 8916-A" · "§199A stmt"), then the §754 statement a transfer needs (C31).
ATTACHED: Final[Mapping[str, tuple[Attached, ...]]] = {
    "1065": (
        Attached("8825", "Form 8825"),
        Attached("4562", "Form 4562"),
        Attached("1065-m3", "Sch. M-3", "m3"),
        Attached("1065-m3-c", "Sch. C (M-3 filers)", "m3"),
        Attached("8916-a", "Form 8916-A", "m3"),
        Attached("1065-199a", "§199A stmt"),
        Attached("1065-754", "§754 stmt", "transfer"),
    ),
}


@dataclass(frozen=True)
class Preview:
    return_id: UUID
    engagement_id: UUID
    checkpoint_id: UUID
    recorded_at: datetime
    template_version_id: UUID  # the face's
    title: str
    pages: tuple[tuple[str, str], ...]  # (page_key, title)
    fields: tuple[Field, ...]
    # T-06-T49: each attached form's pages and their template version (None: a placeholder).
    attached: tuple[tuple[str, UUID | None], ...] = ()

    def version_of(self, page_key: str) -> UUID | None:
        return dict(self.attached).get(page_key, self.template_version_id)

    def placeholder(self, page_key: str) -> bool:
        return self.version_of(page_key) is None

    @property
    def drawn(self) -> tuple[tuple[str, str], ...]:
        """The pages with a template: what the PDF carries, in order."""
        return tuple(p for p in self.pages if not self.placeholder(p[0]))

    @property
    def content_hash(self) -> str:
        body: dict[str, object] = {
            "checkpoint": str(self.checkpoint_id),
            "template_version": str(self.template_version_id),
            "fields": [[f.key, f.value] for f in self.fields],
        }
        versions = sorted({str(v) for _, v in self.attached if v is not None})
        if versions:  # T-06-T49: a face alone hashes as before
            body["attached"] = versions
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


# --- formatting (code; ADR-050) ------------------------------------------------------------------


def _decimal(raw: object) -> Decimal | None:
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def money(amount: Decimal | None, *, whole: bool) -> str | None:
    """Form style: thousands separators, negatives in parentheses, whole dollars by default."""
    if amount is None:
        return None
    value = amount.quantize(Decimal("1") if whole else Decimal("0.01"))
    shown = f"{abs(value):,}" if whole else f"{abs(value):,.2f}"
    return f"({shown})" if value < 0 else shown


def masked_tin(kind: str | None, last4: str | None) -> str | None:
    if not last4:
        return None
    return f"••-•••{last4}" if kind == "ein" else f"•••-••-{last4}"


def shown(fmt: str, raw: object) -> str | None:
    if fmt in ("money", "whole_dollars"):
        return money(_decimal(raw), whole=fmt == "whole_dollars")
    if fmt == "checkbox":
        return "X" if raw in (True, "true", "yes", "1", 1) else None
    if fmt == "percent":
        d = _decimal(raw)
        return None if d is None else f"{d.normalize():f}%"
    return None if raw in (None, "") else str(raw)


# --- resolution ---------------------------------------------------------------------------------


def _v(values: Values, key: str) -> object:
    cell = values.get(key)
    return None if cell is None else cell.get("v")


def mapped_lines(values: Values) -> dict[str, Decimal]:
    """Sheet 03's mapped lines summed by key (A key, C net)."""
    out: dict[str, Decimal] = {}
    n = 2
    while f"03!A{n}" in values:
        key = _v(values, f"03!A{n}")
        net = _decimal(_v(values, f"03!C{n}"))
        if key not in (None, "") and net is not None:
            out[str(key)] = out.get(str(key), ZERO) + net
        n += 1
    return out


CREDIT_SIDES: Final = frozenset({"liability", "capital", "income", "contra_asset"})


def tb_value(ref: str, lines: Mapping[str, Decimal], sides: Mapping[str, str]) -> Decimal | None:
    """A form-lines key's value as the form prints it. Sheet 03 carries signed nets (debits
    positive, credits negative), so a credit-side line (liability, capital, income, contra asset)
    prints its net negated; the Schedule L totals are code's: `L14` = Σ asset nets + Σ contra
    nets (assets less accumulated depreciation and allowances), `L22` = -Σ liability and capital
    nets. A key with no mapped line prints blank."""
    if ref in ("L14", "L22"):
        wanted = ("asset", "contra_asset") if ref == "L14" else ("liability", "capital")
        keys = [k for k, s in sides.items() if s in wanted]
        if not any(k in lines for k in keys):
            return None
        total = sum((lines.get(k, ZERO) for k in keys), ZERO)
        return total if ref == "L14" else -total
    if ref not in lines:
        return None
    return -lines[ref] if sides.get(ref) in CREDIT_SIDES else lines[ref]


# Analysis of Net Income line 2's columns by the partner's kind (Form 1065 instructions: an
# individual general partner is active, an individual limited partner passive; DEC-5915).
ANALYSIS_COLUMNS: Final = ("2a", "2b", "2c", "2d", "2e", "2f")


def analysis_column(partner_kind: str | None, entity_kind: str | None) -> str:
    if entity_kind == "corporation":
        return "2a"
    if entity_kind == "individual":
        return "2b" if partner_kind in ("gp", "member") else "2c"
    if entity_kind in ("partnership", "llc"):
        return "2d"
    if entity_kind == "exempt":
        return "2e"
    return "2f"


def analysis_facts(
    values: Values,
    recipients: list[tuple[UUID, str]],
    kinds: Mapping[str, tuple[str, str]],
) -> dict[str, Decimal]:
    """Analysis of Net Income from the checkpoint's 06 and 09 (`entity_schedules.analysis`, code's
    sum; ADR-050): line 1 and line 2's six columns, each recipient's share in its kind's column
    (`kinds`: display name → (partner kind, entity kind) from the partners table)."""
    from abacus.modules.tax import entity_schedules as es

    lines = es.schedule_k(
        cast("dict[str, dict[str, object]]", values), [pid for pid, _ in recipients], "federal"
    )
    found = es.analysis(lines)
    names = dict(recipients)
    out = {f"analysis.line_{c}": ZERO for c in ANALYSIS_COLUMNS}
    out["analysis.line_1"] = found.total
    for pid, amount in found.by_partner:
        kind, entity_kind = kinds.get(names.get(pid, ""), (None, None))
        out[f"analysis.line_{analysis_column(kind, entity_kind)}"] += amount
    return out


def engine_facts(form: str, lines: object) -> dict[str, object]:
    """Facts the approved engine summary carries (`return_engine_summaries.lines`, keyed
    `<form>.<line>`): page one's lines (`1065.1a` → `page_one.line_1a`), Schedule B's answers
    (`1065.B3` → `schedule_b.q3`) and the header items Accrued keeps nowhere else (`1065.item_b`
    the principal product, `1065.item_e` the date started). An entry's `value` wins over its
    `amount`; a fact the engine did not send prints blank (never a guess)."""
    out: dict[str, object] = {}
    prefix = f"{form}."
    for raw in cast("list[object]", lines or []):
        if not isinstance(raw, dict):
            continue
        entry = cast("dict[str, object]", raw)
        key = entry.get("line_key")
        if not isinstance(key, str) or not key.startswith(prefix):
            continue
        line = key[len(prefix) :]
        value = entry.get("value", entry.get("amount"))
        if line == "item_b":
            out["return.principal_product"] = value
        elif line == "item_e":
            out["entity.started_on"] = value
        elif line.startswith("B") and line[1:].isdigit():
            out[f"schedule_b.q{int(line[1:])}"] = value
        else:
            out[f"page_one.line_{line.lower()}"] = value
    return out


def resolve(
    manifest: Mapping[str, object],
    values: Values,
    sides: Mapping[str, str],
    facts: Mapping[str, object],
) -> tuple[Field, ...]:
    lines = mapped_lines(values)
    out: list[Field] = []
    for raw in cast("list[dict[str, object]]", manifest.get("fields") or []):
        binding = cast("dict[str, str]", raw["binding"])
        kind, ref, fmt = binding["kind"], binding["ref"], str(raw["format"])
        if kind == "workbook_cell":
            value = shown(fmt, _v(values, ref))
        elif kind == "tb_line":
            value = shown(fmt, tb_value(ref, lines, sides))
        elif fmt == "tin":
            value = cast("str | None", facts.get(ref))  # masked before it gets here
        else:
            value = shown(fmt, facts.get(ref))
        box = cast("list[float]", raw["box"])
        out.append(
            Field(
                str(raw["key"]), str(raw["page_key"]), str(raw["label"]),
                (box[0], box[1], box[2], box[3]), fmt, kind, ref, value,
            )
        )  # fmt: skip
    return tuple(out)


_RETURN: Final = text(
    "SELECT form, tax_year, client_entity_id FROM tax_returns WHERE work_item_id = :r"
)
_K1S: Final = text("SELECT count(*) FROM k1_recipients WHERE work_item_id = :r")
_PROFILE: Final = text(
    "SELECT principal_activity, business_code FROM entity_return_profiles WHERE work_item_id = :r"
)
_PARTNER_KINDS: Final = text(
    "SELECT display_name, kind, entity_kind FROM partners WHERE work_item_id = :r"
)
_SUMMARY: Final = text(
    "SELECT lines FROM return_engine_summaries WHERE work_item_id = :r AND kind <> 'pro_forma' "
    "AND approved_at <= :at ORDER BY approved_at DESC LIMIT 1"
)


async def _facts(
    ctx: AuthContext, return_id: UUID, entity: UUID, form: str, state_values: Values,
    recorded_at: datetime,
) -> dict[str, object]:  # fmt: skip
    """Every `return_fact` the face may bind, at the checkpoint (module docstring)."""
    from abacus.modules.identity.api import may_read_unmasked
    from abacus.modules.organisations.api import (
        client_of_entity,
        entity_name,
        entity_tin_kind,
        entity_tin_last4s,
    )
    from abacus.modules.tax import entity_schedules as es

    async with tenant_session(ctx.tenant) as session:
        k1s = int(await session.scalar(_K1S, {"r": return_id}) or 0)
        profile = (await session.execute(_PROFILE, {"r": return_id})).first()
        kinds = {
            str(r.display_name): (str(r.kind), str(r.entity_kind))
            for r in (await session.execute(_PARTNER_KINDS, {"r": return_id})).all()
        }
        summary = await session.scalar(_SUMMARY, {"r": return_id, "at": recorded_at})
    facts: dict[str, object] = engine_facts(form, summary)
    client = await client_of_entity(ctx.tenant, entity)
    last4s = sorted(await entity_tin_last4s(ctx.tenant, client, entity)) if client else []
    # An offshore reader gets no TIN digits at all (AC9.4); anyone else the last four, masked.
    unmasked = await may_read_unmasked(ctx)
    ein = (
        masked_tin(await entity_tin_kind(ctx.tenant, entity), last4s[0])
        if unmasked and len(last4s) == 1
        else None
    )
    facts.update(
        {
            "entity.name": await entity_name(ctx.tenant, entity),
            "entity.ein": ein,
            "return.k1_count": str(k1s),
            "return.principal_activity": None if profile is None else profile.principal_activity,
            "return.business_code": None if profile is None else profile.business_code,
        }
    )
    facts.update(analysis_facts(state_values, await es.recipients(ctx.tenant, return_id), kinds))
    return facts


async def _sides(form: str, tax_year: int) -> dict[str, str]:
    from abacus.kernel.clock import today
    from abacus.modules.platform.api import tax_form_lines_for

    try:
        found = await tax_form_lines_for(form, tax_year, as_of=await today())
    except LookupError:
        return {}
    return {str(r.key): str(getattr(r, "side", "") or "") for r in found.lines}


async def preview(ctx: AuthContext, return_id: UUID, checkpoint_id: UUID | None) -> Preview:
    """The return's preview at the checkpoint (module docstring). 409 `checkpoint_required`
    without an approved one, 409 `form_template_missing` without a published face."""
    from abacus.modules.methodology.api import published_form_face
    from abacus.modules.review.api import checkpoint_state
    from abacus.modules.tax.overview import load_return, return_resource

    loaded = await load_return(ctx, return_id)
    await authorise(ctx, READ, await return_resource(ctx, loaded))
    async with tenant_session(ctx.tenant) as session:
        ret = (await session.execute(_RETURN, {"r": return_id})).first()
    if ret is None:
        raise NotFound("tax_return")
    state = await checkpoint_state(ctx.tenant, WORKBOOK, return_id, checkpoint_id)
    if state is None:
        if checkpoint_id is not None:
            raise NotFound("checkpoint")
        raise CheckpointMissing(facts={"work_item_id": str(return_id)})
    form, year = str(ret.form), int(ret.tax_year)
    face = await published_form_face(ctx.tenant, form, year)
    if face is None or face.field_manifest is None:
        raise FormTemplateMissing(facts={"form": form, "tax_year": year})
    facts = await _facts(
        ctx, return_id, cast(UUID, ret.client_entity_id), form, state.values, state.recorded_at
    )
    manifest = face.field_manifest
    pages = _pages(manifest)
    fields = list(resolve(manifest, state.values, await _sides(form, year), facts))
    versions: list[tuple[str, UUID | None]] = []
    for att in await carried(ctx.tenant, form, return_id, state.values):
        attached = await published_form_face(ctx.tenant, att.form, year)
        if attached is None or attached.field_manifest is None:
            pages.append((f"{att.prefix}p1", att.caption))
            versions.append((f"{att.prefix}p1", None))
            continue
        mine = _pages(attached.field_manifest, att.prefix)
        pages += mine
        versions += [(key, attached.version_id) for key, _ in mine]
        fields += [
            replace(f, key=att.prefix + f.key, page_key=att.prefix + f.page_key)
            for f in resolve(
                attached.field_manifest, state.values, await _sides(att.form, year), facts
            )
        ]
    return Preview(
        return_id, loaded.facts.engagement_id, state.checkpoint_id, state.recorded_at,
        face.version_id, face.template_name or f"Form {form} (TY{year})", tuple(pages),
        tuple(fields), tuple(versions),
    )  # fmt: skip


def _pages(manifest: Mapping[str, object], prefix: str = "") -> list[tuple[str, str]]:
    return [
        (prefix + str(p["page_key"]), str(p["title"]))
        for p in sorted(
            cast("list[dict[str, object]]", manifest.get("pages") or []),
            key=lambda p: int(cast(int, p["page_no"])),
        )
    ]


_TRANSFERS: Final = text("SELECT count(*) FROM interest_transfers WHERE work_item_id = :r")


async def carried(
    tenant: TenantContext, form: str, return_id: UUID, values: Values
) -> list[Attached]:
    """The attached forms this return carries, in TAX-11's order (module docstring)."""
    from abacus.modules.tax.standards_checks import M3_ASSETS, total_assets

    found = ATTACHED.get(form, ())
    if not found:
        return []
    assets = total_assets(values)
    async with tenant_session(tenant) as session:
        transfers = int(await session.scalar(_TRANSFERS, {"r": return_id}) or 0)
    when = {"always": True, "m3": assets is not None and assets >= M3_ASSETS,
            "transfer": transfers > 0}  # fmt: skip
    return [a for a in found if when[a.when]]


class _Cached(Exception):
    """Every page of the preview was rendered already: nothing to write."""


async def _cache(ctx: AuthContext, found: Preview) -> None:
    """One `form_page_renders` row per drawn page for the (checkpoint, template version) pair,
    with the render hash; a pair already rendered is left as it is. The first render of any page
    records `form_preview.rendered` (T-06-T49: before, a first read wrote rows with no audit event
    and failed on the database; a read of rendered pages writes nothing)."""
    try:
        async with uow(ctx.tenant) as tx:
            written = 0
            for key, _ in found.drawn:
                row = await tx.session.execute(
                    text(
                        "INSERT INTO form_page_renders (tenant_id, engagement_id, work_item_id, "
                        "checkpoint_id, template_version_id, page_key, render_hash, status) "
                        "VALUES (:t, :e, :r, :c, :v, :p, :h, 'ready') ON CONFLICT (work_item_id, "
                        "checkpoint_id, template_version_id, page_key) DO NOTHING RETURNING id"
                    ),
                    {"t": ctx.tenant_id, "e": found.engagement_id, "r": found.return_id,
                     "c": found.checkpoint_id, "v": found.version_of(key), "p": key,
                     "h": found.content_hash},
                )  # fmt: skip
                written += 1 if row.first() is not None else 0
            if not written:
                raise _Cached
            tx.record(
                "form_preview.rendered",
                target=Target("tax_return", found.return_id),
                after=Ref(checkpoint=found.checkpoint_id, pages=written),
                scope=Scope(engagement_id=found.engagement_id, work_item_id=found.return_id),
            )
    except _Cached:
        return


def render(found: Preview) -> bytes:
    from abacus.modules.reporting.api import FaceField, FacePage, render_face_isolated

    return render_face_isolated(
        found.title,
        [FacePage(k, t) for k, t in found.drawn],
        [FaceField(f.page_key, f.label, f.box, f.value or "") for f in found.fields],
        as_of=found.recorded_at,
        content_hash=found.content_hash,
    )


async def pages(ctx: AuthContext, return_id: UUID, checkpoint_id: UUID | None) -> Preview:
    found = await preview(ctx, return_id, checkpoint_id)
    await _cache(ctx, found)
    return found


async def download_draft(ctx: AuthContext, return_id: UUID) -> bytes:
    """The watermarked PDF, by a person with fresh MFA (the matrix), audited (DEC-60)."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(DOWNLOAD, "role")
    from abacus.modules.tax.overview import load_return, return_resource

    loaded = await load_return(ctx, return_id)
    await authorise(ctx, DOWNLOAD, await return_resource(ctx, loaded))
    found = await preview(ctx, return_id, None)
    content = await asyncio.to_thread(render, found)
    async with uow(ctx.tenant) as tx:
        tx.record(
            "form_preview.downloaded",
            target=Target("tax_return", return_id),
            after=Ref(checkpoint=found.checkpoint_id, template_version=found.template_version_id),
            scope=Scope(engagement_id=found.engagement_id, work_item_id=return_id),
        )
    await _cache(ctx, found)
    return content


async def page_png(ctx: AuthContext, return_id: UUID, page_key: str) -> bytes:
    """One page as a PNG (TAX-11's page image), rasterised from the same PDF in the isolated
    child (kernel.pdf_pages)."""
    from abacus.kernel.pdf_pages import render_page_isolated

    found = await preview(ctx, return_id, None)
    keys = [k for k, _ in found.drawn]  # a placeholder has no image (TAX-11 draws it)
    if page_key not in keys:
        raise NotFound("form_page")
    pdf = await asyncio.to_thread(render, found)
    image = await asyncio.to_thread(render_page_isolated, pdf, keys.index(page_key) + 1)
    if image.problem is not None or not image.png:
        raise NotFound("form_page")
    return image.png


def fields_of(found: Preview, page_key: str) -> list[Field]:
    chosen = [f for f in found.fields if f.page_key == page_key]
    if not chosen:
        raise NotFound("form_page")
    return chosen


def trace(found: Preview, field_key: str) -> tuple[str | None, list[str]]:
    """SHL-09's trace: a workbook cell, or the TB-mapped form line, for one field."""
    f = next((x for x in found.fields if x.key == field_key), None)
    if f is None:
        raise NotFound("form_field")
    if f.binding_kind == "workbook_cell":
        return f.binding_ref, []
    if f.binding_kind == "tb_line":
        return None, [f.binding_ref]
    return None, []


@dataclass(frozen=True)
class Diagnostic:
    rule_key: str
    severity: str  # blocking | warning | clear (TAX-11's words; an open info reads as warning)
    issue_id: UUID | None
    page_key: str | None


async def diagnostics(
    tenant: TenantContext, return_id: UUID, checkpoint_id: UUID
) -> list[Diagnostic]:
    """The checkpoint's form diagnostics (one per rule; `form_diagnostics`), each on the page its
    facts name when they name one."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT rule_key, severity, status, issue_id, facts->>'page_key' AS page_key "
                    "FROM form_diagnostics WHERE work_item_id = :r AND checkpoint_id = :c "
                    "ORDER BY rule_key"
                ),
                {"r": return_id, "c": checkpoint_id},
            )
        ).all()
    return [
        Diagnostic(
            str(r.rule_key),
            "clear"
            if r.status == "clear"
            else ("blocking" if r.severity == "blocking" else "warning"),
            r.issue_id,
            r.page_key,
        )
        for r in rows
    ]


async def rendered_pages(tenant: TenantContext, found: Preview) -> frozenset[str]:
    """The pages already rendered for the preview's checkpoint, each at its template version."""
    async with tenant_session(tenant) as session:
        keys = await session.execute(
            text(
                "SELECT page_key, template_version_id FROM form_page_renders WHERE "
                "work_item_id = :r AND checkpoint_id = :c AND template_version_id = ANY(:v) "
                "AND status = 'ready'"
            ),
            {"r": found.return_id, "c": found.checkpoint_id,
             "v": sorted({cast(UUID, found.version_of(k)) for k, _ in found.drawn}, key=str)},
        )  # fmt: skip
        mine = {(k, found.version_of(k)) for k, _ in found.drawn}
        return frozenset(str(k[0]) for k in keys.all() if (k[0], k[1]) in mine)


@dataclass(frozen=True)
class K1Previews:
    items: tuple[tuple[UUID, str, Decimal], ...]  # (partner, name, box 2)
    box_2_total: Decimal
    schedule_k_line_2: Decimal

    @property
    def tally(self) -> str:
        return "tie" if self.box_2_total == self.schedule_k_line_2 else "off"


def k1_box_2(values: Values, partners: list[tuple[UUID, str]]) -> K1Previews:
    """TAX-11 c: each recipient's box 2 from sheet 09 (one column per recipient from B, in the
    recipients' order; rows match 06's), and 06's line 2 total, both at the checkpoint."""
    row = None
    n = 2
    while f"06!A{n}" in values:
        if str(_v(values, f"06!A{n}") or "").strip() == "2":
            row = n
            break
        n += 1
    line_2 = ZERO if row is None else (_decimal(_v(values, f"06!C{row}")) or ZERO)
    items: list[tuple[UUID, str, Decimal]] = []
    for i, (pid, name) in enumerate(partners):
        col = chr(ord("B") + i)
        amount = ZERO if row is None else (_decimal(_v(values, f"09!{col}{row}")) or ZERO)
        items.append((pid, name, amount))
    return K1Previews(tuple(items), sum((a for _p, _n, a in items), ZERO), line_2)


async def k1_previews(ctx: AuthContext, return_id: UUID) -> K1Previews:
    from abacus.modules.review.api import checkpoint_state
    from abacus.modules.tax import entity_schedules as es
    from abacus.modules.tax.overview import load_return, return_resource

    loaded = await load_return(ctx, return_id)
    await authorise(ctx, "k1_package.read", await return_resource(ctx, loaded))
    state = await checkpoint_state(ctx.tenant, WORKBOOK, return_id, None)
    if state is None:
        raise CheckpointMissing(facts={"work_item_id": str(return_id)})
    return k1_box_2(state.values, await es.recipients(ctx.tenant, return_id))


__all__ = [
    "CheckpointMissing",
    "Diagnostic",
    "Field",
    "K1Previews",
    "Preview",
    "diagnostics",
    "download_draft",
    "fields_of",
    "k1_box_2",
    "k1_previews",
    "mapped_lines",
    "masked_tin",
    "money",
    "page_png",
    "pages",
    "preview",
    "render",
    "rendered_pages",
    "resolve",
    "shown",
    "tb_value",
    "trace",
]
