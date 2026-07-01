"""Smoke + correctness checks for every parser against the sample fixtures.

Runs standalone (`python money/tests/test_parsers.py`) with no pytest needed.
Verifies each sample file is detected as the expected format, produces the
canonical columns, and yields sane signed amounts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from money.pipeline import parsers  # noqa: E402

SAMPLE = ROOT / "money" / "sample_data"

EXPECTED_FORMAT = {
    "Chase1111_Activity.CSV": "chase_credit_card",
    "Chase2222_Activity.CSV": "chase_credit_card",
    "Chase3333_Activity.CSV": "chase_credit_card",
    "Chase4444_Activity.CSV": "chase_credit_card",
    "Chase5555_Combined.CSV": "chase_credit_card_with_card_col",
    "Chase0000_Activity.CSV": "chase_bank_account",
    "Chase9999_Activity.CSV": "chase_bank_account",
    "capital_one_transactions.csv": "capital_one",
    "citi_year_to_date.CSV": "citi",
    "VenmoStatement.csv": "venmo",
}


def main() -> int:
    failures = []
    print(f"{'file':<52}{'format':<32}{'rows':>6}  date range / sum")
    for fname, expected in EXPECTED_FORMAT.items():
        path = SAMPLE / fname
        try:
            df, fmt = parsers.parse_file(str(path))
        except Exception as e:  # noqa: BLE001
            failures.append(f"{fname}: raised {e!r}")
            print(f"{fname:<52}ERROR: {e}")
            continue

        if fmt != expected:
            failures.append(f"{fname}: detected {fmt!r}, expected {expected!r}")
        if list(df.columns) != ["Date", "Description", "Amount"]:
            failures.append(f"{fname}: bad columns {list(df.columns)}")
        if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
            failures.append(f"{fname}: Date not datetime")
        if df["Amount"].isna().any():
            failures.append(f"{fname}: has NaN amounts")

        dmin, dmax = df["Date"].min(), df["Date"].max()
        print(f"{fname:<52}{fmt:<32}{len(df):>6}  "
              f"{dmin:%Y-%m-%d}..{dmax:%Y-%m-%d}  sum={df['Amount'].sum():,.2f}")

    print()
    if failures:
        print("FAILURES:")
        for f in failures:
            print("  -", f)
        return 1
    print("All parser checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
