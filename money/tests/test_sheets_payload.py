"""Tests _build_payload (formula ranges + layout) without touching the network.

Runs standalone: `python money/tests/test_sheets_payload.py`. Catches range-off
bugs in the SUMIF / SUM formulas, which would otherwise silently misreport
totals in the live sheet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from money.pipeline.sheets import _build_payload  # noqa: E402


CATEGORIES = ["Income", "Investments", "Food & Dining", "Misc."]


def _df(n: int) -> pd.DataFrame:
    dates = pd.date_range("2026-04-01", periods=n)
    return pd.DataFrame({
        "Date": dates,
        "Description": [f"txn{i}" for i in range(n)],
        "Amount": [float(i) for i in range(n)],
        "Account": ["A"] * n,
        "Category": ["Income"] * n,
    })


def main() -> int:
    failures = []

    # Case 1: 3 transactions, no extras
    txn_rows, block, block_start, txn_last = _build_payload(_df(3), CATEGORIES, [])
    if txn_last != 4: failures.append(f"txn_last expected 4, got {txn_last}")
    if block_start != 6: failures.append(f"block_start expected 6, got {block_start}")
    if len(txn_rows) != 4: failures.append(f"txn_rows expected 4 (header+3), got {len(txn_rows)}")
    if block[0] != ["Category", "Sum"]: failures.append(f"block header wrong: {block[0]}")
    # first category SUMIF: row 7 references B7, range E2:E4 / C2:C4
    if block[1] != ["Income", "=SUMIF(E2:E4, B7, C2:C4)"]:
        failures.append(f"first SUMIF wrong: {block[1]}")
    # No blank row between categories and totals (matches Nov 2025).
    # block layout: header + 4 categories + 2 totals = 7 rows.
    if len(block) != 7: failures.append(f"block length expected 7, got {len(block)}")
    if not block[-2][1].startswith("=SUM(C7:C10)"):
        failures.append(f"sub-total range wrong: {block[-2]}")
    if block[-1] != ["Sum of individual transactions", "=SUM(C2:C4)"]:
        failures.append(f"txn-total wrong: {block[-1]}")

    # Case 2: extras (UNKNOWN) are appended after canonical categories
    df2 = _df(2)
    df2.loc[1, "Category"] = "UNKNOWN"
    _, block2, _, _ = _build_payload(df2, CATEGORIES, ["UNKNOWN"])
    cats_only = [r[0] for r in block2[1:-2]]  # excludes header and the two totals
    if cats_only != CATEGORIES + ["UNKNOWN"]:
        failures.append(f"extras placement wrong: {cats_only}")

    if failures:
        print("FAILURES:")
        for f in failures: print("  -", f)
        return 1
    print("All sheets-payload checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
