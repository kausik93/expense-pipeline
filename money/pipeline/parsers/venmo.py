"""Venmo account statement.

Unlike the bank CSVs, Venmo's real header is on the third row (the file opens
with two banner rows), and amounts are formatted like ``- $61.00``. We preserve
Venmo's own sign and synthesize a human-readable description in the same
"<X> paid <Y>" shape the historical sheet uses, so categorization keys line up.
"""
from __future__ import annotations

import pandas as pd

from .base import Parser, canonical


def _detect(_first_row_fields, raw_first_line: str) -> bool:
    return raw_first_line.lstrip().startswith("Account Statement")


def _parse_amount(raw) -> float:
    s = str(raw).replace("$", "").replace(",", "").replace(" ", "")
    return float(s)


def _describe(row) -> str:
    t = row.get("Type")
    frm, to = str(row.get("From", "")).strip(), str(row.get("To", "")).strip()
    if t == "Payment":
        return f"{frm} paid {to}"
    if t == "Charge":
        return f"{to} paid {frm}"
    note = str(row.get("Note", "")).strip()
    return f"Venmo {t}: {frm} -> {to} {note}".strip()


def _parse(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, skiprows=2, index_col=False)
    df = df[df["ID"].notna() & df["Amount (total)"].notna()].copy()
    df["Date"] = df["Datetime"]
    df["Amount"] = df["Amount (total)"].apply(_parse_amount)
    df["Description"] = df.apply(_describe, axis=1)
    return canonical(df, "venmo")


PARSER = Parser(
    name="venmo",
    header=None,
    parse_fn=_parse,
    detect_fn=_detect,
)

PARSERS = [PARSER]
