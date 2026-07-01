"""Citi export (the "Year to date" download): Status / Debit / Credit / Member Name.

Citi puts no card identifier in the filename or the contents, so account
identity for Citi files comes purely from the filename (see accounts.yaml).
Observed sign convention: the Debit column holds positive purchase magnitudes
and the Credit column holds already-negative values for payments and statement
credits, so canonical Amount (spend negative, money-in positive) is the negated
sum of the two columns.
"""
from __future__ import annotations

import pandas as pd

from .base import Parser, canonical


def _parse(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=False)
    df["Amount"] = -(df["Debit"].fillna(0) + df["Credit"].fillna(0))
    return canonical(df, "citi")


PARSER = Parser(
    name="citi",
    header=["Status", "Date", "Description", "Debit", "Credit", "Member Name"],
    parse_fn=_parse,
)

PARSERS = [PARSER]
