"""PII detection by code over the word layer (P-03-T13; SPEC-322 F4 AC4.1, AC4.8; P-03 §4.4;
ADR-050, DEC-52, DEC-60, DEC-322). PROTECTED.

`upload_processing` v5 (`patched("pii_scan")`) runs `pii_scan_upload` after the word layer. Code,
never a model, finds taxpayer IDs, bank and routing numbers and dates of birth on each page's
words; each becomes one `pii_regions` row (its box in page points, its kind, its last four digits
and its value **sealed** with the tenant's key, Restricted), and the source gets one
`pii_scan_runs` row listing the pages it scanned and the pages it could not (no text layer: a scan
or a photo until P-11's OCR). "Scanned and clean" and "not scannable" are therefore never confused,
and a page no run lists stays unreadable (`projection`: fail closed).

Rules (`detect`):
- **Label-anchored** (masked even if the number fails validity, because seeds are fictional): a
  candidate on the same line as, and right of, a label, or on the line just below it: SSN, ITIN
  and TIN labels with `ddd-dd-dddd` or nine digits; EIN labels with `dd-ddddddd` (or nine digits);
  account-number labels with an account (4 to 17 digits, dashes and a short letter prefix
  allowed); routing labels with nine digits; date-of-birth labels with a date.
- **Unlabelled** candidates must pass their rules: `ddd-dd-dddd` is an ITIN or SSN only when valid
  (`kernel.tin_patterns`); `dd-ddddddd` an EIN only with an assigned prefix; nine bare digits a
  routing number only when the ABA checksum holds.
- The kind of a TIN follows its shape and label: `dd-ddddddd` or an EIN label is `ein`; an ITIN
  label or a valid ITIN is `itin`; otherwise `ssn`.

Not here (and why it is safe): skipped entirely for a withdrawn version (DEC-298: as if it never
arrived) and for an active-content PDF (DEC-296: never read; it has no word layer either), and
for any source without a word layer (no run is written, so nothing reads as clean). Idempotent on
(source, `DETECTOR_VERSION`): the run row is unique, and a second run finds it and stops. Values
never leave this module except sealed; they are never logged and never cross a workflow payload.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.tin_patterns import scrub_tins, valid_ein, valid_itin, valid_ssn
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.evidence.citations.matching import WordLike
from abacus.modules.evidence.events import InboxFileExtracted, UploadChecksRecorded
from abacus.modules.evidence.masking import mask_token
from abacus.modules.evidence.models import EvidenceVersion, InboxFile
from abacus.modules.evidence.repository import (
    get_inbox_file,
    get_version,
    insert_pii_regions,
    insert_scan_run,
    is_withdrawn,
    latest_checks,
    newest_extraction,
    pages_of,
    scan_run_for,
)
from abacus.modules.evidence.words import WORDS_VERSION, read_page_layer
from abacus.modules.evidence.workflow_types import INBOX, VERSION, UploadInput
from abacus.modules.requests.api import items_of_version

_log = get_logger(__name__)
PORTAL_DROP: Final = "portal_drop"
_CURLY: Final = chr(0x2019)  # a curly apostrophe, as forms print "Payer's"

# d2 (P-03-T15 security review): scans the render-space, fail-closed word layer `w2`.
DETECTOR_VERSION: Final = "d2"
PiiKind = Literal["ssn", "itin", "ein", "bank_account", "routing_number", "dob"]
Box = tuple[float, float, float, float]

_SSN_FORM: Final = re.compile(r"^(\d{3})-(\d{2})-(\d{4})$")
_EIN_FORM: Final = re.compile(r"^(\d{2})-(\d{7})$")
_NINE: Final = re.compile(r"^\d{9}$")
_ACCOUNT: Final = re.compile(r"^(?:[A-Z]{2,4}-)?[0-9][0-9-]{2,24}[0-9]$")
_DATE: Final = re.compile(r"^(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2})$")
_EDGE: Final = re.compile(r"^[\s(\[{:;,.#*]+|[\s)\]}:;,.*]+$")

Family = Literal["tin", "ein", "account", "routing", "dob"]
# Labels as forms print them, lower-cased with curly apostrophes made straight. Order matters:
# the longest phrase of a line wins its family.
LABELS: Final[tuple[tuple[Family, str], ...]] = (
    ("ein", "employer identification number"),
    ("ein", "employer's identification number"),
    ("ein", "federal identification number"),
    ("ein", "payer's tin"),
    ("ein", "payer's federal identification number"),
    ("ein", "ein"),
    ("tin", "social security number"),
    ("tin", "social security no"),
    ("tin", "recipient's tin"),
    ("tin", "recipient's identification number"),
    ("tin", "taxpayer identification number"),
    ("tin", "partner's identifying number"),
    ("tin", "identifying number"),
    ("tin", "itin"),
    ("tin", "ssn"),
    ("tin", "tin"),
    ("routing", "routing number"),
    ("routing", "routing no"),
    ("routing", "routing transit number"),
    ("routing", "aba"),
    ("account", "account number"),
    ("account", "account no"),
    ("account", "acct no"),
    ("account", "account #"),
    ("dob", "date of birth"),
    ("dob", "birth date"),
    ("dob", "dob"),
)


@dataclass(frozen=True)
class Found:
    """One detected value. `value` is Restricted: it is sealed, never logged or returned."""

    page: int
    kind: PiiKind
    box: Box
    value: str
    last4: str | None
    label_anchored: bool


@dataclass(frozen=True)
class _Line:
    words: tuple[WordLike, ...]
    top: float
    bottom: float
    x0: float
    x1: float


def _token(text: str) -> str:
    plain = unicodedata.normalize("NFKC", text)
    return _EDGE.sub("", plain)


def _phrase(text: str) -> str:
    plain = unicodedata.normalize("NFKC", text).lower().replace(_CURLY, "'")
    return " ".join(plain.split())


def lines_of(words: Sequence[WordLike]) -> list[_Line]:
    """Words grouped into lines (a word joins a line its vertical centre falls within)."""
    lines: list[list[WordLike]] = []
    for word in sorted(words, key=lambda w: (round(w.top, 1), w.x0)):
        centre = (word.top + word.bottom) / 2
        for line in lines:
            if line[0].top - 1 <= centre <= line[0].bottom + 1:
                line.append(word)
                break
        else:
            lines.append([word])
    out: list[_Line] = []
    for line in lines:
        line.sort(key=lambda w: w.x0)
        out.append(
            _Line(
                tuple(line),
                min(w.top for w in line),
                max(w.bottom for w in line),
                min(w.x0 for w in line),
                max(w.x1 for w in line),
            )
        )
    out.sort(key=lambda line: line.top)
    return out


def _labels(line: _Line) -> list[tuple[Family, float, float]]:
    """The label families on a line, with each label's left and right edge."""
    words = list(line.words)
    found: list[tuple[Family, float, float]] = []
    taken: set[int] = set()
    for family, phrase in LABELS:
        size = len(phrase.split())
        for i in range(len(words) - size + 1):
            if any(j in taken for j in range(i, i + size)):
                continue
            span = words[i : i + size]
            text = _phrase(" ".join(w.text for w in span)).strip(" :#()")
            if text == phrase or (size == 1 and _phrase(span[0].text).strip(" :#()") == phrase):
                taken.update(range(i, i + size))
                found.append((family, span[0].x0, span[-1].x1))
    return found


def _aba(digits: str) -> bool:
    d = [int(c) for c in digits]
    return (3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + d[2] + d[5] + d[8]) % 10 == 0


def _digits(text: str) -> str:
    return "".join(c for c in text if c.isdigit())


def _tin_kind(digits: str, families: set[Family], ein_shape: bool) -> PiiKind:
    if ein_shape or ("ein" in families and "tin" not in families):
        return "ein"
    if valid_itin(digits):
        return "itin"
    return "ssn"


def _classify(text: str, families: set[Family]) -> tuple[PiiKind, str] | None:
    """A candidate token's kind and value, given the label families anchoring it (empty when
    unlabelled), or None when it is not PII by these rules."""
    if (found := _SSN_FORM.match(text)) is not None:
        digits = "".join(found.groups())
        if families & {"tin", "ein"}:
            return _tin_kind(digits, families, ein_shape=False), digits
        if valid_itin(digits):
            return "itin", digits
        return ("ssn", digits) if valid_ssn(digits) else None
    if (found := _EIN_FORM.match(text)) is not None:
        digits = "".join(found.groups())
        if families & {"tin", "ein"}:
            return "ein", digits
        return ("ein", digits) if valid_ein(digits) else None
    if _NINE.match(text):
        if "routing" in families:
            return "routing_number", text
        if families & {"tin", "ein"}:
            return _tin_kind(text, families, ein_shape=False), text
        if "account" in families:
            return "bank_account", text
        return ("routing_number", text) if _aba(text) else None
    if "account" in families and _ACCOUNT.match(text) and len(_digits(text)) >= 4:
        return "bank_account", text
    if "dob" in families and _DATE.match(text):
        return "dob", text
    return None


def _anchoring(line: _Line, above: _Line | None, word: WordLike) -> set[Family]:
    """The families whose labels anchor `word`: left of it on its line, or on the line above
    over the same columns (a form's box label sits above or left of its value)."""
    families: set[Family] = {f for f, _x0, x1 in _labels(line) if x1 <= word.x0 + 0.5}
    if above is not None and word.top - above.bottom <= 3 * max(word.bottom - word.top, 1.0):
        for family, x0, x1 in _labels(above):
            if x0 - 160 <= word.x0 <= x1 + 160:
                families.add(family)
    return families


def _box(words: Sequence[WordLike]) -> Box:
    return (
        round(min(w.x0 for w in words), 2),
        round(min(w.top for w in words), 2),
        round(max(w.x1 for w in words), 2),
        round(max(w.bottom for w in words), 2),
    )


def _candidates(line: _Line) -> list[tuple[str, tuple[WordLike, ...]]]:
    """Single tokens, and `ddd dd dddd` written as three tokens (joined with hyphens)."""
    words = line.words
    out: list[tuple[str, tuple[WordLike, ...]]] = [(_token(w.text), (w,)) for w in words]
    for i in range(len(words) - 2):
        parts = [_token(w.text) for w in words[i : i + 3]]
        if [len(p) for p in parts] == [3, 2, 4] and all(p.isdigit() for p in parts):
            out.append(("-".join(parts), tuple(words[i : i + 3])))
    return out


def detect(page_no: int, words: Sequence[WordLike]) -> list[Found]:
    """Every PII value on one page's words (pure; P-03 §4.4)."""
    lines = lines_of(words)
    found: list[Found] = []
    used: set[int] = set()
    for index, line in enumerate(lines):
        above = lines[index - 1] if index > 0 else None
        for text, span in _candidates(line):
            if not text or any(id(w) in used for w in span):
                continue
            families = _anchoring(line, above, span[0])
            classified = _classify(text, families)
            if classified is None:
                continue
            kind, value = classified
            digits = _digits(value)
            found.append(
                Found(
                    page_no,
                    kind,
                    _box(span),
                    value,
                    None if kind == "dob" or len(digits) < 2 else digits[-4:],
                    bool(families),
                )
            )
            used.update(id(w) for w in span)
    return found


# --- Rotated pages (P-03-T15 security review; DEC-369) ------------------------------------------


@dataclass(frozen=True)
class _Placed:
    text: str
    x0: float
    top: float
    x1: float
    bottom: float


def _turn(box: Box, rotation: int, width: float, height: float, *, back: bool) -> Box:
    """A box between render space (the page as shown, `width` x `height`) and the content's own
    upright frame. `back` maps upright to render space."""
    (x0, top, x1, bottom) = box
    corners = ((x0, top), (x1, bottom))
    out: list[tuple[float, float]] = []
    for u, v in corners:
        if rotation == 90:  # shown = (H0 - b, a), with H0 = width
            point = (width - v, u) if back else (v, width - u)
        elif rotation == 180:
            point = (width - u, height - v)
        elif rotation == 270:  # shown = (b, W0 - a), with W0 = height
            point = (v, height - u) if back else (height - v, u)
        else:
            point = (u, v)
        out.append(point)
    (ax, ay), (bx, by) = out
    return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def detect_on_page(
    page_no: int, words: Sequence[WordLike], rotation: int, width: float, height: float
) -> list[Found]:
    """`detect` on a page whose layer is in render space (`w2`): the words are turned back into
    the content's upright frame, where a form's lines read left to right, and each region is
    turned again into render space, where the masks are burned."""
    if rotation not in (90, 180, 270):
        return detect(page_no, words)
    upright = [
        _Placed(w.text, *_turn((w.x0, w.top, w.x1, w.bottom), rotation, width, height, back=False))
        for w in words
    ]
    found: list[Found] = []
    for f in detect(page_no, upright):
        x0, top, x1, bottom = _turn(f.box, rotation, width, height, back=True)
        box: Box = (round(x0, 2), round(top, 2), round(x1, 2), round(bottom, 2))
        found.append(Found(f.page, f.kind, box, f.value, f.last4, f.label_anchored))
    return found


# --- Spreadsheet cells (P-03-T15; P-03 §4.4 "spreadsheet cells get the same tokens") ----------

_CELL_TOKEN: Final = re.compile(r"\S+")
# A column labelled for bank accounts masks only longer numbers under it: a ledger's four- or
# five-digit account codes are not bank accounts (DEC-369).
_COLUMN_ACCOUNT_DIGITS: Final = 6


def _cell_families(text: str) -> set[Family]:
    """The label families a cell's text names (whole words, as `_labels` reads a line)."""
    words = [w.strip(" :#()") for w in _phrase(text).split()]
    found: set[Family] = set()
    for family, phrase in LABELS:
        parts = phrase.split()
        for i in range(len(words) - len(parts) + 1):
            if words[i : i + len(parts)] == parts:
                found.add(family)
                break
    return found


def _masked_cell(text: str, families: set[Family], column: set[Family]) -> str:
    """The cell with each token that is PII by `_classify` (given the anchoring families)
    replaced by its token; `column` holds the families that come only from a column header."""

    def replace(found: re.Match[str]) -> str:
        core = _token(found.group(0))
        classified = _classify(core, families)
        if classified is None:
            return found.group(0)
        kind, value = classified
        digits = _digits(value)
        if (
            kind == "bank_account"
            and "account" in column
            and "account" not in (families - column)
            and len(digits) < _COLUMN_ACCOUNT_DIGITS
        ):
            return found.group(0)
        return mask_token(kind, None if kind == "dob" or len(digits) < 2 else digits[-4:])

    return _CELL_TOKEN.sub(replace, text)


def masked_rows(rows: Sequence[Sequence[str]]) -> tuple[tuple[str, ...], ...]:
    """A sheet's rows as a reader may see them (pure; P-03 §4.4): a cell is anchored by a label in
    its own text, by the nearest label cell to its left in the row (until a non-label value), or
    by the nearest label cell above it in its column (a header); anchored cells are masked
    whatever their validity, unanchored ones only when valid (`_classify`), and every cell then
    goes through the kernel's TIN scrub as a backstop. The token is the one the page's masks
    carry (`masking.mask_token`)."""
    headers: dict[int, set[Family]] = {}
    out: list[tuple[str, ...]] = []
    for row in rows:
        left: set[Family] = set()
        masked: list[str] = []
        labels: dict[int, set[Family]] = {}
        for c, cell in enumerate(row):
            own = _cell_families(cell)
            column = headers.get(c, set())
            masked.append(scrub_tins(_masked_cell(cell, own | left | column, column - own - left)))
            if own:
                left, labels[c] = own, own
            elif cell.strip():
                left = set()
        headers.update(labels)
        out.append(tuple(masked))
    return tuple(out)


# --- The activity's body -----------------------------------------------------------------------


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "evidence.upload_processing")


def value_context(region_id: UUID) -> str:
    """The sealed value's binding: the region it belongs to (the reveal service opens it)."""
    return f"pii_regions.value_sealed:{region_id}"


async def _announce(
    session: AsyncSession, source: EvidenceVersion | InboxFile, version_id: UUID | None
) -> bool:
    """Whether this first scan re-announces the upload to agents (P-03-T15; DEC-369): it has
    page text (agent material waited for this scan, `processing.material_ready`) and there is
    something to announce: a version's recorded checks on a request, or a firm inbox file still
    waiting (a portal drop's sort announces its own). The caller only asks for a live upload
    (`UploadInput.announce`; the backfill passes False: review L1)."""
    extraction = await newest_extraction(
        session,
        evidence_version_id=version_id,
        inbox_file_id=None if version_id is not None else source.id,
    )
    if extraction is None or extraction.status != "extracted" or not extraction.page_count:
        return False
    if isinstance(source, InboxFile):
        return source.channel != PORTAL_DROP and source.status == "waiting"
    if not await latest_checks(session, source.id):
        return False
    return bool(await items_of_version(_system(source.tenant_id), source.id))


async def pii_scan_upload(given: UploadInput) -> int:
    """The `upload.pii_scan` activity's body: one upload's PII scan over its word layer; returns
    the regions found (0 when there is nothing to scan). Idempotent."""
    tenant_id, source_id = UUID(given.tenant_id), UUID(given.source_id)
    tenant = _system(tenant_id)
    version_id = source_id if given.kind == VERSION else None
    inbox_id = source_id if given.kind == INBOX else None
    async with tenant_session(tenant) as session:
        done = await scan_run_for(
            session,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            detector_version=DETECTOR_VERSION,
        )
        if done is not None:
            return done.region_count
        source = (
            await get_version(session, source_id)
            if version_id is not None
            else await get_inbox_file(session, source_id)
        )
        if source is None:
            if version_id is not None and await is_withdrawn(session, version_id):
                return 0  # DEC-298: nothing is derived from a withdrawn version
            raise NotFound("upload")
        extraction = await newest_extraction(
            session, evidence_version_id=version_id, inbox_file_id=inbox_id
        )
        if extraction is not None and extraction.reason == "active_content":
            return 0  # DEC-296: kept, never read
        pages = await pages_of(
            session,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            extractor_version=WORDS_VERSION,
        )
    if not pages:
        return 0  # no word layer: no run, so no page reads as scanned (fail closed)
    scanned: list[int] = []
    unscannable: list[int] = []
    found: list[Found] = []
    for page in pages:
        if not page.has_text_layer:
            unscannable.append(page.page_no)
            continue
        layer = await read_page_layer(tenant_id, page)
        found.extend(
            detect_on_page(
                page.page_no,
                layer.words,
                page.rotation,
                float(page.width_pt),
                float(page.height_pt),
            )
        )
        scanned.append(page.page_no)
    rows: list[dict[str, object]] = []
    for item in found:
        region_id = uuid.uuid4()
        rows.append(
            {
                "id": region_id,
                "tenant_id": tenant_id,
                "evidence_version_id": version_id,
                "inbox_file_id": inbox_id,
                "derivation_id": None,
                "page_no": item.page,
                "bbox": [Decimal(str(v)) for v in item.box],
                "kind": item.kind,
                "value_sealed": await seal(
                    tenant_id, item.value.encode(), value_context(region_id)
                ),
                "last4": item.last4,
                "label_anchored": item.label_anchored,
                "detector_version": DETECTOR_VERSION,
            }
        )
    async with uow(tenant) as tx:
        first = await insert_scan_run(
            tx.session,
            tenant_id=tenant_id,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            derivation_id=None,
            detector_version=DETECTOR_VERSION,
            pages_scanned=scanned,
            pages_not_scannable=unscannable,
            region_count=len(rows),
        )
        if first:
            await insert_pii_regions(tx.session, rows)
            if (
                given.announce
                and extraction is not None
                and await _announce(tx.session, source, version_id)
            ):
                # P-03-T15: agents read only masked material, which a document with page text
                # has from now on; the reviewer or matcher held back at extraction may follow.
                tx.emit(
                    UploadChecksRecorded(
                        engagement_id=source.engagement_id, evidence_version_id=source_id
                    )
                    if version_id is not None
                    else InboxFileExtracted(
                        engagement_id=source.engagement_id, inbox_file_id=source_id
                    )
                )
        tx.record(
            "upload.pii_scanned" if first else "upload.pii_scan_exists",
            target=Target("evidence_version" if version_id else "inbox_file", source_id),
            after=Ref(regions=len(rows), scanned=len(scanned), not_scannable=len(unscannable)),
        )
    _log.info(
        "upload.pii_scanned", kind=given.kind, regions=len(rows), not_scannable=len(unscannable)
    )
    return len(rows)


__all__ = [
    "DETECTOR_VERSION",
    "LABELS",
    "Found",
    "detect",
    "detect_on_page",
    "lines_of",
    "masked_rows",
    "pii_scan_upload",
    "value_context",
]
