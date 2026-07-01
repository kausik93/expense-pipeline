"""Held-out accuracy check: can the categorizer reproduce hand-labeled April?

Re-derives merchant rules from every tab EXCEPT Apr2026, then predicts a
category for each labeled April row and compares to what the sheet actually
says. This is an honest (out-of-sample) read on how often the deterministic
lookup agrees with the human, and which merchants it misses or disagrees on.

    python money/tests/validate_april.py

NOTE: this reads a personal historical workbook (bootstrap_merchants.DEFAULT_WORKBOOK,
i.e. money/sample_data/expenses_history.xlsx) that is NOT shipped with this repo.
It is kept here to document how the held-out accuracy figure in the README was
produced; point DEFAULT_WORKBOOK at your own categorized workbook to run it.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from money.pipeline.bootstrap_merchants import (  # noqa: E402
    DEFAULT_WORKBOOK, build_category_mapper, collect_votes, resolve_rules,
)
from money.pipeline.categorize import UNKNOWN, match_category  # noqa: E402
from money.pipeline.config import load_categories  # noqa: E402
from money.pipeline.text import merchant_key  # noqa: E402

TAB = "Apr2026"


def labeled_rows(workbook):
    map_cat = build_category_mapper(load_categories())
    df = pd.read_excel(workbook, sheet_name=TAB, engine="openpyxl")
    df = df[["Description", "Category"]].dropna()
    rows = []
    for _, r in df.iterrows():
        cat = map_cat(r["Category"])
        if cat is not None:
            rows.append((str(r["Description"]), cat))
    return rows


def main():
    workbook = DEFAULT_WORKBOOK
    votes, *_ = collect_votes(workbook, exclude={TAB})
    rules, _ = resolve_rules(votes)
    print(f"rules from all tabs except {TAB}: {len(rules)}")

    rows = labeled_rows(workbook)
    correct = wrong = unknown = 0
    mismatches = []
    for desc, actual in rows:
        pred = match_category(merchant_key(desc), rules) or UNKNOWN
        if pred == UNKNOWN:
            unknown += 1
        elif pred == actual:
            correct += 1
        else:
            wrong += 1
            mismatches.append((desc, actual, pred))

    n = len(rows)
    predicted = correct + wrong
    print(f"labeled April rows:        {n}")
    print(f"predicted (non-unknown):   {predicted}  ({100*predicted/n:.1f}%)")
    print(f"unknown (no rule):         {unknown}  ({100*unknown/n:.1f}%)")
    if predicted:
        print(f"agreement where predicted: {correct}/{predicted}  ({100*correct/predicted:.1f}%)")
    print(f"\nmismatches ({len(mismatches)}):")
    for desc, actual, pred in mismatches[:40]:
        print(f"  {desc[:48]:<48} sheet={actual:<18} pred={pred}")


if __name__ == "__main__":
    main()
