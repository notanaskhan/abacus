"""The deterministic renderer (ADR-320; P-11-T02 spike, completed by P-11-T07 and T10).

DocBlocks go through code-owned layouts to HTML, WeasyPrint makes the PDF and python-docx the
DOCX. Nothing here fetches a URL, reads the clock or picks a system font: the same inputs give the
same bytes (`render_hash`). WeasyPrint needs Pango and HarfBuzz, which only the worker image
carries, so callers import `render.pdf` lazily, inside the isolated child.
"""

import os

from abacus.modules.reporting.render.assets import FONTCONFIG_FILE

# Before WeasyPrint loads Pango (render.pdf): fontconfig sees only the renderer's configuration,
# which lists no system font, in this process (the isolated child) and nowhere else.
os.environ["FONTCONFIG_FILE"] = str(FONTCONFIG_FILE)
