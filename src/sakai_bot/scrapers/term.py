"""
Academic term parsing and comparison.

Sakai course titles end in a term token like "S2-2526" (semester 2 of the
2025/2026 academic year). This module extracts and compares those tokens so the
bot can auto-detect the current term without any calendar configuration.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

TERM_RE = re.compile(r"\bS(\d)-(\d{4})\b", re.IGNORECASE)


@dataclass(order=True, frozen=True)
class Term:
    """A parsed academic term, ordered oldest -> newest by (year_code, semester)."""

    year_code: int
    semester: int
    raw: str = field(compare=False)


def parse_term(text: str | None) -> Term | None:
    """Extract the first S<semester>-<yearcode> token from text, or None."""
    if not text:
        return None
    match = TERM_RE.search(text)
    if not match:
        return None
    return Term(
        year_code=int(match.group(2)),
        semester=int(match.group(1)),
        raw=match.group(0).upper(),
    )


def latest_term(terms: Iterable[Term | None]) -> Term | None:
    """Return the newest term, ignoring Nones; None if there are no terms."""
    present = [t for t in terms if t is not None]
    if not present:
        return None
    return max(present)
