"""Combine parsed statements into one month's normalized transaction list.

Parsing (how to read a file) is decided by header fingerprint; account identity
(which card a file is) is decided here, by matching the filename against
accounts.yaml. The two are intentionally separate so the common drift cases are
handled gracefully:
  - new card, known format  -> parses fine, flagged as an unresolved account
  - known card, new format  -> flagged as an unknown format (needs a parser)
Neither aborts the run; both are reported for follow-up.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from . import parsers
from .config import load_account_rules

CANONICAL_COLUMNS = ["Date", "Description", "Amount", "Account"]


@dataclass
class FileReport:
    filename: str
    format_name: str
    account: str
    rows_total: int
    rows_in_month: int


@dataclass
class IngestResult:
    transactions: pd.DataFrame  # Date, Description, Amount, Account (month-filtered, sorted)
    files: List[FileReport] = field(default_factory=list)
    unknown_formats: List[Tuple[str, List[str]]] = field(default_factory=list)
    unresolved_accounts: List[str] = field(default_factory=list)


def resolve_account(filename: str, rules: List[Dict[str, str]]) -> Optional[str]:
    name = filename.lower()
    for rule in rules:
        if rule["match"].lower() in name:
            return rule["name"]
    return None


def _csv_files(inbox: Path) -> List[Path]:
    return sorted(p for p in inbox.iterdir() if p.suffix.lower() == ".csv")


def ingest(inbox, month: int, year: int, account_rules=None) -> IngestResult:
    inbox = Path(inbox)
    rules = account_rules if account_rules is not None else load_account_rules()
    result = IngestResult(transactions=pd.DataFrame(columns=CANONICAL_COLUMNS))
    frames = []

    for path in _csv_files(inbox):
        try:
            df, fmt = parsers.parse_file(str(path))
        except parsers.UnknownFormatError as e:
            result.unknown_formats.append((path.name, e.header))
            continue

        account = resolve_account(path.name, rules)
        if account is None:
            result.unresolved_accounts.append(path.name)
            account = f"UNRESOLVED: {path.name}"

        in_month = df[(df["Date"].dt.month == month) & (df["Date"].dt.year == year)].copy()
        in_month["Account"] = account
        frames.append(in_month)
        result.files.append(FileReport(path.name, fmt, account, len(df), len(in_month)))

    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.sort_values("Date", kind="stable").reset_index(drop=True)
        result.transactions = combined[CANONICAL_COLUMNS]
    return result
