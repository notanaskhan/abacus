"""Output controls on model text (ADR-065; SPEC-006 AC-1, AC-2). PROTECTED.

Model text is stored sanitised and shown as plain text only. Links are the one thing plain text
can still carry out of the page, so every link whose host isn't in `output_link_allowlist`
(empty by default, SPEC-006 Q1) becomes `[link removed]`: bare URLs, `www.` hosts, markdown
links and images, and HTML anchors and images. An allowed link stays as plain text. Nothing is
ever fetched. Other markup is left alone: it is inert as plain text.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from abacus.kernel.config import settings

REMOVED = "[link removed]"
_MD_LINK = re.compile(r"!?\[[^\]\n]{0,500}\]\(\s*([^)\s]{1,2000})[^)]{0,500}\)")
_HTML_LINK = re.compile(
    r"<\s*(?:a|img|iframe|script|link|source)\b[^>]{0,2000}?(?:href|src)\s*=\s*['\"]?([^'\"\s>]{1,2000})[^>]{0,2000}>",
    re.IGNORECASE,
)
_URL = re.compile(r"\b(?:[a-z][a-z0-9+.-]{1,20}://|www\.)[^\s<>()\"']{1,2000}", re.IGNORECASE)


def _host(link: str) -> str:
    target = link if "://" in link else f"http://{link}"
    try:
        return (urlsplit(target).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _allowed(link: str) -> bool:
    host = _host(link)
    allow = {h.lower().rstrip(".") for h in settings().output_link_allowlist}
    return bool(host) and any(host == a or host.endswith("." + a) for a in allow)


def sanitise_text(text: str) -> str:
    """The text with every non-allowlisted link replaced by `[link removed]`."""

    def markup(match: re.Match[str]) -> str:
        return match.group(0) if _allowed(match.group(1)) else REMOVED

    def bare(match: re.Match[str]) -> str:
        return match.group(0) if _allowed(match.group(0)) else REMOVED

    text = _MD_LINK.sub(markup, text)
    text = _HTML_LINK.sub(markup, text)
    return _URL.sub(bare, text)
