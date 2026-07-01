"""Chase exports: credit cards (two header variants) and bank accounts.

Chase signs the Amount column the way we want already: negative = money out
(a purchase / debit), positive = money in (a payment / credit).
"""
from __future__ import annotations

import pandas as pd

from .base import Parser, canonical


def _parse_credit_card(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=False)
    df = df.rename(columns={"Post Date": "Date"})
    return canonical(df, "chase_credit_card")


def _parse_credit_card_with_card_col(path: str) -> pd.DataFrame:
    # Same as the standard card export but with a leading "Card" column
    # (a combined multi-card export). The Card column is redundant with the
    # filename for account resolution, so we just drop it.
    df = pd.read_csv(path, index_col=False)
    df = df.rename(columns={"Post Date": "Date"})
    return canonical(df, "chase_credit_card_with_card_col")


def _parse_bank_account(path: str) -> pd.DataFrame:
    # Bank exports have ragged trailing commas; index_col=False keeps columns aligned.
    df = pd.read_csv(path, index_col=False)
    df = df.rename(columns={"Posting Date": "Date"})
    return canonical(df, "chase_bank_account")


CREDIT_CARD = Parser(
    name="chase_credit_card",
    header=["Transaction Date", "Post Date", "Description", "Category", "Type", "Amount", "Memo"],
    parse_fn=_parse_credit_card,
)

CREDIT_CARD_WITH_CARD_COL = Parser(
    name="chase_credit_card_with_card_col",
    header=["Card", "Transaction Date", "Post Date", "Description", "Category", "Type", "Amount", "Memo"],
    parse_fn=_parse_credit_card_with_card_col,
)

BANK_ACCOUNT = Parser(
    name="chase_bank_account",
    header=["Details", "Posting Date", "Description", "Amount", "Type", "Balance", "Check or Slip #"],
    parse_fn=_parse_bank_account,
)

PARSERS = [CREDIT_CARD, CREDIT_CARD_WITH_CARD_COL, BANK_ACCOUNT]
