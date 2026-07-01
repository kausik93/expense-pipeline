"""Turn a raw transaction description into a stable merchant key.

The goal is that two charges from the same merchant collapse to the same key by
stripping the variable noise banks attach: order ids, store numbers, dates,
"WEB ID" trailers, Square/Toast prefixes, etc. The exact output is not meant to
be pretty — only *stable*, so categorization rules built from history keep
matching future charges. Both the bootstrap and the runtime categorizer call
this, so they must always agree.
"""
from __future__ import annotations

import re

_DATE = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
_DOTNUM = re.compile(r"\.{2,}\s*\d+")  # "...5329"
_ID_PHRASE = re.compile(
    r"\b(?:WEB|PPD|ORIG|CONF|REF|TRACE|ARN)\s*ID\b\s*:?\s*\S+", re.IGNORECASE
)
_LABEL = re.compile(
    r"\b(?:ORIG CO NAME|CO ENTRY DESCR|ENTRY DESCR|SEC|ORIG ID)\b\s*:?\s*",
    re.IGNORECASE,
)


def _clean_token(t: str) -> str:
    t = t.strip(".,:;#*-/\\()")
    if not t:
        return ""
    # strip leading/trailing digit runs: "CRUNCH114" -> "CRUNCH", "00028506" -> ""
    t = re.sub(r"^\d+", "", t)
    t = re.sub(r"\d+$", "", t)
    if len(t) <= 1:
        return ""
    # anything still carrying an interior digit is an id-like token (order codes,
    # "BC3EA7X11", "A156342029") -> drop it entirely
    if any(c.isdigit() for c in t):
        return ""
    return t


def merchant_key(description: str) -> str:
    s = str(description).upper()
    s = _ID_PHRASE.sub(" ", s)
    s = _LABEL.sub(" ", s)
    s = _DOTNUM.sub(" ", s)
    s = _DATE.sub(" ", s)
    s = re.sub(r"[^A-Z0-9.&]+", " ", s)  # keep . and & (APPLE.COM, AT&T)
    tokens = [_clean_token(t) for t in s.split()]
    return " ".join(t for t in tokens if t).strip()
