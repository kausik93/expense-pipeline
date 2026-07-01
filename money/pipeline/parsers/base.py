"""Parser registry primitives.

A Parser knows how to recognize one bank export format (by its header
fingerprint) and turn it into the canonical transaction frame. Recognition is
deliberately content-based, not filename-based: a brand-new card with a known
export format is parsed automatically; only a genuinely new *format* is an
"unknown" that needs a human to author a parser.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

import pandas as pd

# Canonical columns every parser must produce.
CANONICAL_COLUMNS = ["Date", "Description", "Amount"]


@dataclass(frozen=True)
class Parser:
    name: str
    # Exact header column list that identifies this format (used when detect is None).
    header: Optional[List[str]]
    parse_fn: Callable[[str], pd.DataFrame]
    # Optional custom detector for formats whose header is not the first CSV row
    # (e.g. Venmo). Receives (first_row_fields, raw_first_line).
    detect_fn: Optional[Callable[[List[str], str], bool]] = None

    def matches(self, first_row_fields: List[str], raw_first_line: str) -> bool:
        if self.detect_fn is not None:
            return self.detect_fn(first_row_fields, raw_first_line)
        return first_row_fields == self.header


def canonical(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Validate and coerce a parser's output into the canonical shape."""
    missing = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"parser '{name}' produced frame missing columns {missing}")
    out = df[CANONICAL_COLUMNS].copy()
    out["Date"] = pd.to_datetime(out["Date"])
    out["Description"] = out["Description"].astype(str).str.strip()
    out["Amount"] = pd.to_numeric(out["Amount"]).round(2)
    return out.reset_index(drop=True)
