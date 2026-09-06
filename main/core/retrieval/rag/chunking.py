"""Text chunking. Fixed-size with overlap - the simplest thing that works.

WHY SO SIMPLE: this is a baseline document retriever, not a contribution of the
thesis. The research question is about conversational memory structure, not
about document chunking. Starting simple means that if a later, cleverer
chunker helps, you can say by how much, against this baseline. Starting clever
means you never know whether the cleverness was needed.

The overlap exists for one reason: a fixed-size cut lands mid-sentence roughly
always, and the sentence that got cut is often the one that answers the
question. Overlap means every sentence appears whole in at least one chunk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Split preferentially at these boundaries, in order of preference, so chunks
#: end somewhere a human would end them.
_BOUNDARIES = ["\n\n", "\n", ". ", " "]


@dataclass
class TextSpan:
    """A chunk of text with the page it came from, if known."""

    text: str
    page: int | None = None


def normalise_whitespace(text: str) -> str:
    """Collapse the whitespace mess that PDF extraction produces.

    PDF text layers give you hard line breaks mid-sentence, stray form feeds,
    and runs of spaces from justified text. Left alone, these leak into chunk
    text and then into prompts, wasting tokens and confusing the model about
    sentence boundaries.
    """
    text = text.replace("\x0c", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _best_split_point(text: str, target: int) -> int:
    """Find a natural break at or before ``target``, else fall back to ``target``.

    Searches within the last 20% of the window so a boundary is preferred, but
    never at the cost of producing a tiny chunk.
    """
    window_start = max(0, int(target * 0.8))
    for boundary in _BOUNDARIES:
        idx = text.rfind(boundary, window_start, target)
        if idx != -1:
            return idx + len(boundary)
    return target


def chunk_text(
    text: str,
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
    min_chunk: int = 100,
    page: int | None = None,
) -> list[TextSpan]:
    """Split ``text`` into overlapping chunks at natural boundaries.

    Chunks shorter than ``min_chunk`` are dropped, except a trailing remainder
    which is appended to the previous chunk instead - a 30-character orphan
    chunk is never useful on its own but might complete the one before it.
    """
    text = normalise_whitespace(text)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [TextSpan(text=text, page=page)] if len(text) >= min_chunk else []

    spans: list[TextSpan] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            end = start + _best_split_point(text[start:], chunk_size)
        piece = text[start:end].strip()

        if len(piece) >= min_chunk:
            spans.append(TextSpan(text=piece, page=page))
        elif piece and spans:
            spans[-1] = TextSpan(text=f"{spans[-1].text} {piece}", page=spans[-1].page)

        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return spans
