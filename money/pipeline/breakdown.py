"""Per-category breakdown with a hard reconciliation guard.

Mirrors the spreadsheet's bottom block: every canonical category (alphabetical,
zeros included), then any extra buckets actually present (e.g. UNKNOWN), then
the two totals that must agree. If the sum of category totals ever diverges from
the sum of individual transactions, that is a bug and we refuse to proceed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import pandas as pd


class ReconciliationError(Exception):
    pass


@dataclass
class Breakdown:
    rows: List[Tuple[str, float]]  # (category, amount), display order
    total_subcategories: float
    total_transactions: float


def compute(df: pd.DataFrame, categories: List[str]) -> Breakdown:
    # Preserve the declared categories.yaml order — that is the order the user
    # uses in their sheet template (e.g. Nov 2025). Any out-of-list categories
    # (UNKNOWN, etc.) sort alphabetically at the end.
    sums = df.groupby("Category")["Amount"].sum().round(2).to_dict()
    extra = sorted(c for c in sums if c not in set(categories))

    rows: List[Tuple[str, float]] = [(c, round(sums.get(c, 0.0), 2)) for c in categories]
    rows += [(c, round(sums[c], 2)) for c in extra]

    total_sub = round(sum(v for _, v in rows), 2)
    total_txn = round(df["Amount"].sum(), 2)
    if abs(total_sub - total_txn) > 0.01:
        raise ReconciliationError(
            f"breakdown total {total_sub} != transaction total {total_txn}"
        )
    return Breakdown(rows=rows, total_subcategories=total_sub, total_transactions=total_txn)
