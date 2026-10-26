"""The block renderer for firm email templates (R-01-T19; R-01 §4.1 `render.py`; C16 v1.1).

A version is a subject, a preheader, typed blocks and at most one call to action. Rendering fills
the key's whitelisted `{variables}` and gives an HTML part and a plain-text part, and it is pure:
the same content, values and width give byte-identical output (no clock, no ids, no ordering that
depends on a dict). Every filled value and every word of the template is HTML-escaped; the only
link is the button, whose address is the `{portal_link}` value (a secure link, P-08-T21): it is
written only when it opens the portal (`portal_link_allowed`), and `{portal_link}` may not
appear in any text (security review M3).

- `{name}` is a variable; a brace that is not part of one is refused (`TemplateInvalid`).
- A variable must be one the content's key registers, and every variable the content uses needs a
  value (`UnknownTemplateVariable`). Values are single-line, except a block variable
  (`open_items`), which is one item per line and appears only in an `item_list` block.
- The button goes before the first `note` or `footer` block, else after the last block.
- At 390 the layout is the same HTML with a narrower frame and a full-width button.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal
from urllib.parse import urlsplit

from abacus.kernel.config import settings
from abacus.modules.communications.templates import TemplateInvalid, UnknownTemplateVariable

BlockKind = Literal["heading", "paragraph", "item_list", "note", "footer"]
Width = Literal[600, 390]
BLOCK_KINDS: Final = ("heading", "paragraph", "item_list", "note", "footer")
_PLACEHOLDER: Final = re.compile(r"\{([a-z][a-z0-9_]{0,39})\}")
_BRACE: Final = re.compile(r"[{}]")
_LINK_CHARS: Final = re.compile(r"[^\s\"'<>\\]{1,2000}")
_LOCAL_LINKS: Final = ("local", "test")  # plain http to localhost only here (review M3)
LINK_VARIABLE: Final = "portal_link"
_BREAKS: Final = re.compile("[\r\x00\x85\u2028\u2029]")
_BARE_DOMAIN: Final = re.compile(
    r"(?i)\b[a-z0-9](?:[a-z0-9-]{0,62})(?:\.[a-z0-9-]{1,63})*\.[a-z]{2,24}\b"
)
# What a client's file or document title ends with: never a domain to defang.
_FILE_EXTENSIONS: Final = frozenset(
    {"pdf", "doc", "docx", "xls", "xlsx", "csv", "txt", "rtf", "jpg", "jpeg", "png", "gif"}
    | {"heic", "heif", "tif", "tiff", "zip", "xml", "json", "msg", "eml", "ppt", "pptx", "qbo"}
    | {"ofx", "qfx", "numbers", "pages", "key", "odt", "ods", "html", "htm"}
)
_BUTTON_BEFORE: Final = frozenset({"note", "footer"})
_FONT: Final = "font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"


@dataclass(frozen=True)
class Block:
    id: str
    kind: BlockKind
    text: str


@dataclass(frozen=True)
class TemplateContent:
    """What a version or a draft holds. `cta_target` names where the link opens; the link
    itself is the `{portal_link}` value."""

    subject: str
    preheader: str
    blocks: tuple[Block, ...]
    cta_label: str | None
    cta_target: str | None

    def to_json(self) -> dict[str, object]:
        return {
            "subject": self.subject,
            "preheader": self.preheader,
            "blocks": [{"id": b.id, "kind": b.kind, "text": b.text} for b in self.blocks],
            "cta_label": self.cta_label,
            "cta_target": self.cta_target,
        }

    @classmethod
    def from_json(cls, raw: Mapping[str, object]) -> TemplateContent:
        blocks_raw = raw.get("blocks")
        if not isinstance(blocks_raw, list):
            raise TemplateInvalid
        blocks: list[Block] = []
        for item in blocks_raw:  # pyright: ignore[reportUnknownVariableType] -- checked below
            if not isinstance(item, dict):
                raise TemplateInvalid
            b: dict[str, object] = item  # pyright: ignore[reportUnknownVariableType] -- a JSON object
            kind, block_id, text = b.get("kind"), b.get("id"), b.get("text")
            if kind not in BLOCK_KINDS or not isinstance(block_id, str):
                raise TemplateInvalid
            if not isinstance(text, str):
                raise TemplateInvalid
            blocks.append(Block(block_id, kind, text))
        subject, preheader = raw.get("subject"), raw.get("preheader", "")
        label, target = raw.get("cta_label"), raw.get("cta_target")
        if not isinstance(subject, str) or not isinstance(preheader, str):
            raise TemplateInvalid
        if not (label is None or isinstance(label, str)):
            raise TemplateInvalid
        if not (target is None or isinstance(target, str)):
            raise TemplateInvalid
        return cls(subject, preheader, tuple(blocks), label, target)


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    preheader: str
    html: str
    text: str


def canonical(key: str, locale: str, content: TemplateContent) -> bytes:
    """The bytes a version's content hash and seal cover."""
    return json.dumps(
        [key, locale, content.to_json()], separators=(",", ":"), sort_keys=True
    ).encode()


def content_sha256(key: str, locale: str, content: TemplateContent) -> str:
    return hashlib.sha256(canonical(key, locale, content)).hexdigest()


def used_variables(text: str) -> list[str]:
    """The variables `text` uses, in order; a stray brace is refused."""
    if _BRACE.search(_PLACEHOLDER.sub("", text)):
        raise TemplateInvalid
    return [m.group(1) for m in _PLACEHOLDER.finditer(text)]


def content_variables(content: TemplateContent) -> set[str]:
    texts = [content.subject, content.preheader, content.cta_label or ""]
    return {v for t in [*texts, *(b.text for b in content.blocks)] for v in used_variables(t)}


def _check_values(
    content: TemplateContent,
    values: Mapping[str, str],
    allowed: frozenset[str],
    block_variables: frozenset[str],
) -> None:
    if not set(values) <= allowed:
        raise UnknownTemplateVariable
    used = content_variables(content)
    if not used <= allowed or not used <= set(values):
        raise UnknownTemplateVariable
    if LINK_VARIABLE in used:
        raise TemplateInvalid  # the secure link goes only in the button (security review M3)
    for text in (content.subject, content.preheader, content.cta_label or ""):
        if set(used_variables(text)) & block_variables:
            raise TemplateInvalid
    for block in content.blocks:
        if block.kind != "item_list" and set(used_variables(block.text)) & block_variables:
            raise TemplateInvalid
    for name, value in values.items():
        if _BREAKS.search(value):  # the re-review: NUL, CR, NEL and the Unicode separators
            raise TemplateInvalid
        if name in block_variables:
            if any(not line.strip() for line in value.split("\n")):
                raise TemplateInvalid
        elif "\n" in value:
            raise TemplateInvalid


def portal_link_allowed(link: str) -> bool:
    """Security review M3: the button opens only the portal. https on the neutral portal domain
    (or one of its firm hosts) or the app's own https origin, with no query string and no
    credentials; plain http to localhost in the local and test environments only."""
    if not _LINK_CHARS.fullmatch(link):
        return False
    parts = urlsplit(link)
    if parts.query or parts.username or parts.password or not parts.hostname:
        return False
    host = parts.hostname
    config = settings()
    app = urlsplit(config.app_base_url)
    if parts.scheme == "https":
        if app.scheme == "https" and host == app.hostname:
            return True
        base = config.portal_base_domain
        return base is not None and (host == base or host.endswith(f".{base}"))
    return (
        parts.scheme == "http"
        and config.environment in _LOCAL_LINKS
        and host in ("localhost", "127.0.0.1")
    )


def defang(value: str) -> str:
    """A bare domain in a client-written value is shown with its dots broken ("evil-pay[.]com"),
    so no mail client makes it a link (the re-review M); a file name ("W-2.pdf") is left alone.
    Schemes, `www.` and addresses never get this far: `lint_values` refuses them."""

    def broken(match: re.Match[str]) -> str:
        found = match.group(0)
        if found.rsplit(".", 1)[-1].lower() in _FILE_EXTENSIONS:
            return found
        return found.replace(".", "[.]")

    return _BARE_DOMAIN.sub(broken, value)


def _fill(text: str, values: Mapping[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda m: defang(values[m.group(1)]), text)


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _html_block(block: Block, text: str) -> str:
    if block.kind == "item_list":
        items = "".join(
            f'<li style="margin:0 0 6px 0">{_escape(line.strip())}</li>'
            for line in text.split("\n")
            if line.strip()
        )
        return f'<ul style="margin:0 0 16px 0;padding:0 0 0 20px">{items}</ul>'
    body = "<br>".join(_escape(line) for line in text.split("\n"))
    if block.kind == "heading":
        return f'<h1 style="margin:0 0 16px 0;font-size:20px;font-weight:500">{body}</h1>'
    if block.kind == "note":
        return f'<p style="margin:0 0 12px 0;font-size:13px">{body}</p>'
    if block.kind == "footer":
        return f'<p style="margin:16px 0 0 0;font-size:12px">{body}</p>'
    return f'<p style="margin:0 0 16px 0;font-size:15px;line-height:22px">{body}</p>'


def _text_block(block: Block, text: str) -> str:
    if block.kind == "item_list":
        return "\n".join(f"- {line.strip()}" for line in text.split("\n") if line.strip())
    return text


def _button(label: str, link: str, width: Width) -> str:
    full = "display:block;width:100%;box-sizing:border-box"
    size = full if width == 390 else "display:inline-block"
    return (
        '<p style="margin:8px 0 24px 0">'
        f'<a href="{_escape(link)}" style="{size};padding:12px 20px;border:1px solid;'
        f'border-radius:6px;text-align:center;text-decoration:none;font-weight:500">'
        f"{_escape(label)}</a></p>"
    )


def render_email(
    content: TemplateContent,
    values: Mapping[str, str],
    *,
    allowed: frozenset[str],
    block_variables: frozenset[str],
    width: Width = 600,
) -> RenderedEmail:
    """Fill and render. Byte-identical for the same content, values and width."""
    _check_values(content, values, allowed, block_variables)
    subject = _fill(content.subject, values)
    preheader = _fill(content.preheader, values)
    link = values.get("portal_link")
    button: tuple[str, str] | None = None
    if content.cta_label is not None:
        if link is None or not portal_link_allowed(link):
            raise TemplateInvalid  # a button needs a secure link on the portal to open
        button = (_fill(content.cta_label, values), link)
    html_parts: list[str] = []
    text_parts: list[str] = []
    placed = button is None
    for block in content.blocks:
        if not placed and block.kind in _BUTTON_BEFORE and button is not None:
            html_parts.append(_button(button[0], button[1], width))
            text_parts.append(f"{button[0]}: {button[1]}")
            placed = True
        filled = _fill(block.text, values)
        html_parts.append(_html_block(block, filled))
        text_parts.append(_text_block(block, filled))
    if not placed and button is not None:
        html_parts.append(_button(button[0], button[1], width))
        text_parts.append(f"{button[0]}: {button[1]}")
    page = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_escape(subject)}</title></head>"
        '<body style="margin:0;padding:0">'
        f'<div style="display:none;max-height:0;overflow:hidden">{_escape(preheader)}</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td align="center" style="padding:24px 16px">'
        f'<table role="presentation" width="{width}" cellpadding="0" cellspacing="0" border="0" '
        f'style="width:100%;max-width:{width}px;{_FONT}">'
        f'<tr><td style="padding:0">{"".join(html_parts)}</td></tr>'
        "</table></td></tr></table></body></html>"
    )
    text = "\n\n".join(part for part in text_parts if part) + "\n"
    return RenderedEmail(subject, preheader, page, text)
