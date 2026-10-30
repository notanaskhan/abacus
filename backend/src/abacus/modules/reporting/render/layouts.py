"""The code-owned layouts (P-11 §4.4; ADR-320 §2; SPEC-520 AC-7, AC-11, AC-12).

Six layouts, one per family of paper: `letter`, `consent_7216`, `report`, `notice_response`,
`package` and `run_export`. Firm templates choose a layout by key; they never carry CSS. The
stylesheets follow the handoff's paper (T10 "Document on well": headings 16/500 and 13.5/500,
body 12/1.55, letterhead mark with the firm name 13.5/500 and a hair rule, ink #2b1f17) set in
points on Letter paper, in the vendored faces only (Arimo body, Gelasio letterhead and signature
lines, Geist Mono for trace figures).

- **Flow and fixed.** `flow` layouts paginate as text runs; `fixed` layouts (`package`,
  `run_export`) keep tables whole where they fit and start each top-level section on a new page.
- **Watermark** (AC-7): a draft stamps a diagonal "DRAFT" on every page and a template preview
  stamps "SAMPLE": 72 px in rgba(43,31,23,.06), as a fixed element WeasyPrint repeats per page.
  A final render has none.
- **Legend** (AC-11): a `legend` block becomes a running footer, printed on every page.
- **Consent** (AC-12): `consent_7216` sets no type below its minimum (12 pt, the floor counsel
  confirms for Rev. Proc. 2013-14, P-11 §11 OQ-7); `minimum_type_pt` is asserted by a test over
  the stylesheet itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

Flow = Literal["flow", "fixed"]
Mark = Literal["DRAFT", "SAMPLE"]

INK: Final = "#2b1f17"
WATERMARK: Final = "rgba(43,31,23,.06)"
LAYOUT_VERSION: Final = 1  # bumps when any stylesheet changes; part of `engine_version`

_BASE: Final = f"""
@page {{ size: Letter; margin: 1in 1in 1.1in; @bottom-center {{ content: element(legend); }} }}
html {{ color: {INK}; }}
body {{ font-family: "Arimo"; font-size: 12pt; line-height: 1.55; margin: 0; }}
h1 {{ font-family: "Arimo"; font-weight: 400; font-size: 16pt; margin: 0 0 12pt; }}
h2 {{ font-family: "Arimo"; font-weight: 400; font-size: 13.5pt; margin: 14pt 0 6pt; }}
h3, h4 {{ font-family: "Arimo"; font-weight: 400; font-size: 12pt; margin: 10pt 0 4pt; }}
p {{ margin: 0 0 8pt; }}
ul, ol {{ margin: 0 0 8pt 18pt; padding: 0; }}
li {{ margin: 0 0 3pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 0 0 10pt; font-size: 11pt; }}
th, td {{ border-bottom: 0.5pt solid #d9d6d1; padding: 3pt 4pt; text-align: left; }}
td.n, th.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
dl.kv {{ margin: 0 0 10pt; }}
dl.kv div {{ display: flex; justify-content: space-between; border-bottom: 0.5pt solid #ece9e4; }}
dl.kv dt, dl.kv dd {{ margin: 0; padding: 2pt 0; }}
.letterhead {{ border-bottom: 0.5pt solid #d9d6d1; padding: 0 0 8pt; margin: 0 0 16pt; }}
.letterhead .firm {{ font-family: "Gelasio"; font-weight: 500; font-size: 13.5pt; }}
.letterhead .address {{ font-size: 11.5pt; color: #7a6f66; }}
.signature {{ margin: 24pt 0 0; }}
.signature .line {{ border-top: 0.5pt solid {INK}; width: 3in; margin: 28pt 0 2pt; }}
.signature .who {{ font-family: "Gelasio"; font-size: 12pt; }}
.enclosures {{ margin: 16pt 0 0; font-size: 11.5pt; }}
.cite {{ font-size: 9pt; vertical-align: super; }}
.page-break {{ break-before: page; }}
.clause {{ margin: 0 0 8pt; }}
.legend {{ position: running(legend); font-size: 9pt; color: #7a6f66; text-align: center; }}
.figure {{ font-family: "Geist Mono"; }}
"""

_FIXED: Final = """
section.top { break-before: page; }
section.top:first-of-type { break-before: auto; }
table { break-inside: avoid; }
"""

_CONSENT: Final = """
body { font-size: 12pt; }
h1 { font-size: 16pt; }
h2, h3, h4 { font-size: 13.5pt; }
table, .enclosures, .letterhead .address, .legend, .cite { font-size: 12pt; }
"""

_EXPORT: Final = """
body { font-size: 11pt; }
td, th { font-family: "Geist Mono"; font-size: 10pt; }
"""


@dataclass(frozen=True)
class Layout:
    key: str
    flow: Flow
    letterhead: bool
    css: str
    minimum_type_pt: float | None = None


LAYOUTS: Final[dict[str, Layout]] = {
    "letter": Layout("letter", "flow", True, _BASE),
    "consent_7216": Layout("consent_7216", "flow", True, _BASE + _CONSENT, minimum_type_pt=12.0),
    "report": Layout("report", "flow", False, _BASE),
    "notice_response": Layout("notice_response", "flow", True, _BASE),
    "package": Layout("package", "fixed", False, _BASE + _FIXED),
    "run_export": Layout("run_export", "fixed", False, _BASE + _FIXED + _EXPORT),
}


def watermark_css(mark: Mark | None) -> str:
    """AC-7: the stamp, repeated on every page; nothing for a final render."""
    if mark is None:
        return ""
    return f"""
.watermark {{ position: fixed; top: 3.6in; left: 0; right: 0; text-align: center;
  font-family: "Arimo"; font-weight: 700; font-size: 72px; color: {WATERMARK};
  transform: rotate(-35deg); letter-spacing: 6px; }}
"""


_SIZE: Final = re.compile(r"font-size:\s*([0-9.]+)(pt|px)")


def smallest_type_pt(css: str) -> float:
    """The smallest font size a stylesheet sets, in points (px at 0.75 pt)."""
    sizes = [float(v) * (0.75 if unit == "px" else 1.0) for v, unit in _SIZE.findall(css)]
    return min(sizes) if sizes else 12.0


def stylesheet(layout: Layout, mark: Mark | None) -> str:
    """The layout's CSS with its watermark. For `consent_7216` the consent overrides follow the
    base, so the cascade leaves nothing below the minimum (the test reads the effective sizes)."""
    return layout.css + watermark_css(mark)
