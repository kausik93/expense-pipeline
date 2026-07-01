"""Pre-flight completeness check: are all the accounts we *expect* this month
actually present in the inbox?

The reconciliation guard proves nothing was dropped between parsing and
categorizing, but it is blind to a whole statement that never arrived. This
compares the accounts that produced a file against the expected-accounts
registry (config/expected_accounts.yaml), scoped to each card's active
[opened, closed] window, and returns the expected-but-absent ones.
"""
from __future__ import annotations

from typing import Dict, Iterable, List


def _period(ym: str) -> int:
    """'2026-04' (or '2026-4') -> a comparable month ordinal."""
    year, month = str(ym).split("-")
    return int(year) * 12 + int(month)


def missing_accounts(expected: List[Dict[str, str]], present: Iterable[str],
                     month: int, year: int) -> List[str]:
    """Names of expected accounts, active this month, with no file present."""
    present = set(present)
    now = year * 12 + month
    missing = []
    for acct in expected:
        opened = _period(acct["opened"]) if acct.get("opened") else None
        closed = _period(acct["closed"]) if acct.get("closed") else None
        if opened is not None and now < opened:
            continue  # not opened yet this month
        if closed is not None and now > closed:
            continue  # already closed this month
        if acct["name"] not in present:
            missing.append(acct["name"])
    return missing
