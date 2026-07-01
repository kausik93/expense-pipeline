"""Deterministic categorization against the merchants.yaml lookup.

A transaction's description is reduced to a merchant key, then matched against
the rules: an exact key match wins (it is always the most specific possible);
otherwise the longest rule key that appears as a whole-token run inside the
transaction key wins. No match -> UNKNOWN, which the run surfaces for the
interactive (LLM-suggested, human-confirmed) step. No LLM is involved here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from .config import load_merchants
from .text import merchant_key

UNKNOWN = "UNKNOWN"


def match_category(key: str, rules: Dict[str, str]) -> Optional[str]:
    if not key:
        return None
    if key in rules:  # exact == most specific possible
        return rules[key]
    padded = f" {key} "
    best_len, best_cat = 0, None
    for pattern, cat in rules.items():
        if len(pattern) > best_len and f" {pattern} " in padded:
            best_len, best_cat = len(pattern), cat
    return best_cat


@dataclass
class UnknownMerchant:
    key: str
    count: int
    total_amount: float
    example: str
    accounts: List[str]


def categorize(df: pd.DataFrame, rules: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    rules = load_merchants() if rules is None else rules
    out = df.copy()
    out["_key"] = out["Description"].apply(merchant_key)
    out["Category"] = [match_category(k, rules) or UNKNOWN for k in out["_key"]]
    return out


def unknown_merchants(categorized: pd.DataFrame) -> List[UnknownMerchant]:
    unknowns = categorized[categorized["Category"] == UNKNOWN]
    result = []
    for key, grp in unknowns.groupby("_key"):
        result.append(
            UnknownMerchant(
                key=key,
                count=len(grp),
                total_amount=round(grp["Amount"].sum(), 2),
                example=grp["Description"].iloc[0],
                accounts=sorted(grp["Account"].unique().tolist()),
            )
        )
    return sorted(result, key=lambda u: u.total_amount)
