"""Deterministic chunking of knowledge documents (SPEC-009 AC-2). Pure: same text, same chunks.

Markdown splits on headings (`#` to `######`), each chunk carrying its heading path; then on
blank-line paragraphs, packed up to `MAX_CHARS`. A longer paragraph is cut at the last whitespace
before the limit, with `OVERLAP` characters repeated into the next piece. Plain text has no
headings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

MAX_CHARS: Final = 1_200
OVERLAP: Final = 150
MAX_HEADING_PATH: Final = 1_000
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


@dataclass(frozen=True)
class Chunk:
    position: int
    heading_path: str
    text: str


def _split_long(paragraph: str) -> list[str]:
    pieces: list[str] = []
    start = 0
    while start < len(paragraph):
        end = min(start + MAX_CHARS, len(paragraph))
        if end < len(paragraph):
            cut = max(paragraph.rfind(" ", start, end), paragraph.rfind("\n", start, end))
            if cut > start + OVERLAP:
                end = cut
        piece = paragraph[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(paragraph):
            break
        start = max(end - OVERLAP, start + 1)
    return pieces


def _pack(paragraphs: list[str]) -> list[str]:
    texts: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        if len(paragraph) > MAX_CHARS:
            if buffer:
                texts.append(buffer)
                buffer = ""
            texts.extend(_split_long(paragraph))
        elif buffer and len(buffer) + 2 + len(paragraph) > MAX_CHARS:
            texts.append(buffer)
            buffer = paragraph
        else:
            buffer = f"{buffer}\n\n{paragraph}" if buffer else paragraph
    if buffer:
        texts.append(buffer)
    return texts


def chunk_document(text: str, *, markdown: bool) -> list[Chunk]:
    sections: list[tuple[str, list[str]]] = [("", [])]
    headings: list[str] = []
    lines: list[str] = []

    def flush() -> None:
        paragraph = "\n".join(lines).strip()
        if paragraph:
            sections[-1][1].append(paragraph)
        lines.clear()

    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        heading = _HEADING.match(line) if markdown else None
        if heading is not None:
            flush()
            level = len(heading.group(1))
            headings[:] = [*headings[: level - 1], heading.group(2)]
            sections.append((" > ".join(headings)[:MAX_HEADING_PATH], []))
        elif not line.strip():
            flush()
        else:
            lines.append(line.rstrip())
    flush()
    chunks: list[Chunk] = []
    for path, paragraphs in sections:
        for piece in _pack(paragraphs):
            chunks.append(Chunk(len(chunks), path, piece))
    return chunks
