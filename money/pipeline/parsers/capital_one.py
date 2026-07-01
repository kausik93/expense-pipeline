"""Capital One export: split Debit / Credit columns (both positive magnitudes).

Debit = money out, Credit = money in. Canonical Amount = Credit - Debit, so a
purchase becomes negative and a payment/refund becomes positive.
"""
from __future__ import annotations

import pandas as pd

from .base import Parser, canonical


def _parse(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=False)
    df["Amount"] = df["Credit"].fillna(0) - df["Debit"].fillna(0)
    df = df.rename(columns={"Posted Date": "Date"})
    return canonical(df, "capital_one")


PARSER = Parser(
    name="capital_one",
    header=["Transaction Date", "Posted Date", "Card No.", "Description", "Category", "Debit", "Credit"],
    parse_fn=_parse,
)

PARSERS = [PARSER]
